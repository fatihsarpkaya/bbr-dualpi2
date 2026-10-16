#!/usr/bin/env python3
"""
Analyze video streaming performance from MGEN TCPINFO log files.
================================================================

For each .log file (each scenario), computes:
  - Number of stalls (rebuffering events)
  - Total rebuffering time (seconds)
  - Rebuffer ratio (% of playtime spent rebuffering)
  - Chunks with rebuffering (% of delivered chunks played after a stall)
  - Chunks delivered, playtime, etc.

Requires TCPINFO lines with bytes_acked (cumulative bytes acknowledged).
Logs without bytes_acked are skipped with a warning.

For PRAGUE/UDP flows, use --receiver-json with a receiver stats file that has
time_since_start (us) and cum_bytes_rcvd (or cum_pkt_rcvd with --bytes-per-packet).

Usage:
  # Analyze all .log files in current directory
  python3 analyze_streaming.py --chunk-duration 2 --chunk-size 2500696

  # Chunk size from packets × bytes per packet (e.g. 1727 packets × 1448 bytes)
  python3 analyze_streaming.py --chunk-duration 2 --chunk-size-packets 1727 --bytes-per-packet 1448

  # Specify directory and output JSON
  python3 analyze_streaming.py -d ./logs --chunk-duration 2 --chunk-size 2500696 -o results.json

  # Explicit chunk count (e.g. 15 chunks for 30s video at 2s/chunk)
  python3 analyze_streaming.py file.log --chunk-duration 2 --chunk-size 2500696 --num-chunks 15

Notes:
  - Time origin: deadlines are relative to ON or CONNECT (fallback: first TCPINFO).
  - Bytes anchor: when t0=CONNECT, we prepend (0,0) so bytes_acked=0 at flow start; use absolute thresholds.
  - bytes_acked is extracted independently (field order in log can vary).
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path


# TCPINFO: match time, flow; bytes_acked searched independently (field order can vary)
TCPINFO_RE = re.compile(
    r"(?P<time>\d{2}:\d{2}:\d{2}\.\d+)\s+TCPINFO\s+"
    r"flow>(?P<flow>\d+)\s+"
)
BYTES_ACKED_RE = re.compile(r"bytes_acked>(?P<bytes_acked>\d+)")

ON_RE = re.compile(
    r"(?P<time>\d{2}:\d{2}:\d{2}\.\d+)\s+ON\s+flow>(?P<flow>\d+)\b"
)
CONNECT_RE = re.compile(
    r"(?P<time>\d{2}:\d{2}:\d{2}\.\d+)\s+CONNECT\s+flow>(?P<flow>\d+)\b"
)
OFF_RE = re.compile(
    r"(?P<time>\d{2}:\d{2}:\d{2}\.\d+)\s+OFF\s+flow>(?P<flow>\d+)\b"
)
SHUTDOWN_RE = re.compile(
    r"(?P<time>\d{2}:\d{2}:\d{2}\.\d+)\s+SHUTDOWN\s+flow>(?P<flow>\d+)\b"
)
# Filename: ..._t102_tx_L4S.log -> experiment key (t102 removed), trial 102
# Matches _t102_ or _t102 at end (e.g. test_t102.log)
TRIAL_RE = re.compile(r"_t(\d+)(?:_|$)")


def get_experiment_and_trial(path: str) -> tuple[str, int | None]:
    """
    Extract experiment key and trial number from filename.
    e.g. streaming-..._t102_tx_L4S.log -> (streaming-..._tx_L4S, 102)
    e.g. test_t102.log -> (test, 102)
    Files without _tN pattern get (stem, None).
    """
    stem = Path(path).stem
    m = TRIAL_RE.search(stem)
    if not m:
        return stem, None
    trial_num = int(m.group(1))
    exp_key = TRIAL_RE.sub("_", stem)
    exp_key = re.sub(r"_+", "_", exp_key).strip("_")
    return exp_key, trial_num


def parse_timestamp(ts: str) -> float:
    """Convert HH:MM:SS.ffffff to seconds since midnight."""
    parts = ts.split(":")
    h, m = int(parts[0]), int(parts[1])
    s = float(parts[2])
    return h * 3600 + m * 60 + s


def parse_receiver_json(
    path: str, bytes_per_packet: int = 1448
) -> list[tuple[float, int]]:
    """
    Parse receiver JSON (one JSON object per line).
    Expects time_since_start (us) and cum_bytes_rcvd, or cum_pkt_rcvd/pkt_rcvd.
    Returns list of (time_sec, cumulative_bytes).
    """
    samples: list[tuple[float, int]] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            t_us = int(obj.get("time_since_start", 0))
            t_sec = t_us / 1_000_000.0
            cum_bytes = obj.get("cum_bytes_rcvd")
            if cum_bytes is not None:
                samples.append((t_sec, int(cum_bytes)))
            else:
                cum_pkt = obj.get("cum_pkt_rcvd")  # pkt_rcvd is delta, not cumulative
                if cum_pkt is not None and isinstance(cum_pkt, (int, float)):
                    samples.append((t_sec, int(cum_pkt) * bytes_per_packet))
    return samples


def parse_log(path: str) -> tuple[dict[int, list[tuple[float, int]]], dict[int, float]]:
    """
    Parse MGEN log and return (data, flow_end_sec).
    data: per-flow lists of (time_sec, bytes_acked), time relative to CONNECT/ON.
    flow_end_sec: per-flow end time (OFF/SHUTDOWN) relative to t0, or last TCPINFO time.
    """
    # First pass: collect t0 and flow_end per flow
    t0_per_flow: dict[int, float] = {}
    flow_end_abs: dict[int, float] = {}  # absolute timestamp when flow ended
    with open(path) as f:
        for line in f:
            m_conn = CONNECT_RE.search(line)
            m_on = ON_RE.search(line)
            m_off = OFF_RE.search(line)
            m_shutdown = SHUTDOWN_RE.search(line)
            if m_conn:
                t0_per_flow[int(m_conn.group("flow"))] = parse_timestamp(
                    m_conn.group("time")
                )
            elif m_on and int(m_on.group("flow")) not in t0_per_flow:
                t0_per_flow[int(m_on.group("flow"))] = parse_timestamp(
                    m_on.group("time")
                )
            if m_off:
                flow_end_abs[int(m_off.group("flow"))] = parse_timestamp(
                    m_off.group("time")
                )
            elif m_shutdown and int(m_shutdown.group("flow")) not in flow_end_abs:
                flow_end_abs[int(m_shutdown.group("flow"))] = parse_timestamp(
                    m_shutdown.group("time")
                )

    # Second pass: parse TCPINFO
    data: dict[int, list[tuple[float, int]]] = defaultdict(list)
    first_tcpinfo_per_flow: dict[int, float] = {}
    with open(path) as f:
        for line in f:
            m = TCPINFO_RE.search(line)
            if not m:
                continue
            ba_match = BYTES_ACKED_RE.search(line)
            if not ba_match:
                continue
            bytes_acked = int(ba_match.group("bytes_acked"))
            flow = int(m.group("flow"))
            t = parse_timestamp(m.group("time"))
            if flow not in first_tcpinfo_per_flow:
                first_tcpinfo_per_flow[flow] = t
            t0 = t0_per_flow.get(flow, first_tcpinfo_per_flow[flow])
            data[flow].append((t - t0, bytes_acked))

    # Anchor bytes at 0 when t0 is CONNECT/ON
    for flow, samples in data.items():
        if flow in t0_per_flow and samples and samples[0][0] > 0:
            data[flow] = [(0.0, 0)] + samples

    # flow_end_sec: relative to t0
    flow_end_sec: dict[int, float] = {}
    for flow in data:
        t0 = t0_per_flow.get(flow, first_tcpinfo_per_flow.get(flow, 0))
        if flow in flow_end_abs:
            flow_end_sec[flow] = flow_end_abs[flow] - t0
        elif data[flow]:
            flow_end_sec[flow] = data[flow][-1][0]  # last sample time

    return dict(data), flow_end_sec


def interpolate_arrival(
    samples: list[tuple[float, int]], target_bytes: int
) -> float | None:
    """
    Find time (seconds) when bytes_acked first reaches target_bytes.
    Returns None if target never reached.
    """
    if not samples or samples[0][1] >= target_bytes:
        return samples[0][0] if samples else None
    for i in range(1, len(samples)):
        t0, b0 = samples[i - 1]
        t1, b1 = samples[i]
        if b1 >= target_bytes:
            if b1 == b0:
                return t1
            frac = (target_bytes - b0) / (b1 - b0)
            return t0 + frac * (t1 - t0)
    return None


def analyze_flow(
    samples: list[tuple[float, int]],
    chunk_size: int,
    chunk_duration: float,
    num_chunks_hint: int | None = None,
    flow_end_sec: float | None = None,
    initial_buffer: int = 1,
    startup_delay: float | None = None,
) -> dict:
    """
    Compute streaming metrics for one flow.
    Uses absolute bytes_acked; samples are anchored at (0,0) when t0=CONNECT.

    initial_buffer: number of chunks to buffer before playback starts and before
    resuming after a mid-stream stall (if enough pending chunks remain).
    startup_delay: if set, overrides the initial deadline (default:
    initial_buffer * chunk_duration).  Playback starts at
    max(startup_delay, arrival_of_initial_buffer_th_chunk).
    Chunk k is considered "requested" at time (k-1)*chunk_duration.
    At a stall on chunk k at time t, we count pending = chunks j where
    request_time(j) <= t and arrival(j) > t.  If pending >= initial_buffer,
    wait for initial_buffer chunks; otherwise wait for however many are pending.
    """
    if not samples:
        return {"error": "no samples"}

    total_bytes = samples[-1][1]

    if num_chunks_hint is not None:
        num_chunks = num_chunks_hint
    else:
        num_chunks = total_bytes // chunk_size
        if num_chunks == 0:
            return {
                "num_chunks": 0,
                "total_bytes": total_bytes,
                "error": "insufficient data for even one chunk",
            }

    # arrivals[i] = time when chunk (i+1) fully arrived (None if never)
    arrivals: list[float | None] = []
    for i in range(1, num_chunks + 1):
        t = interpolate_arrival(samples, i * chunk_size)
        arrivals.append(t)

    # request_time[i] = when chunk (i+1) is requested = i * chunk_duration
    # (chunk 1 requested at 0, chunk 2 at chunk_duration, ...)
    request_times = [i * chunk_duration for i in range(num_chunks)]

    # delivered_indices: indices into arrivals[] that are not None
    delivered_indices = [i for i, a in enumerate(arrivals) if a is not None]
    undelivered_count = num_chunks - len(delivered_indices)

    if not delivered_indices:
        return {
            "num_chunks": 0,
            "num_chunks_undelivered": num_chunks,
            "total_bytes": total_bytes,
            "error": "no chunks delivered",
        }

    delivered = [arrivals[i] for i in delivered_indices]

    # Playback model with rebuffer-to-target:
    #
    # STARTUP: wait until initial_buffer chunks are downloaded.
    #   Playback starts at max(initial_buffer * chunk_duration, arrival of chunk initial_buffer).
    #   The stall is attributed to the FIRST chunk only.
    #
    # MID-STREAM STALL at chunk k (0-indexed in delivered[]):
    #   deadline = start_chunk[k-1] + chunk_duration (= rebuffering start time)
    #   If delivered[k] > deadline → stall detected.
    #   Pending = chunks requested by deadline (request_times[j] <= deadline) that
    #   have not arrived by deadline (arrivals[j] is None or > deadline).
    #   Count over ALL chunks, not just delivered.
    #   wait_for = min(initial_buffer, max(pending_count, 1))
    #   Resume when the wait_for-th pending chunk arrives. If fewer arrive, wait
    #   until flow end.
    #   The stall duration is attributed to chunk k only.

    stalls: list[float] = []
    start_chunk: list[float] = []
    wait_for_per_chunk: list[int] = []  # actual wait_for for timeline display
    for i in range(len(delivered)):
        if i == 0:
            # STARTUP: need initial_buffer chunks before playback
            startup_count = min(initial_buffer, len(delivered))
            latest_arrival = max(delivered[j] for j in range(startup_count))
            deadline = startup_delay if startup_delay is not None else initial_buffer * chunk_duration
            resume_at = max(deadline, latest_arrival)
            stall = max(0.0, resume_at - deadline)
            start_chunk.append(resume_at)
            stalls.append(stall)
            wait_for_per_chunk.append(0)  # not used for startup
        else:
            deadline = start_chunk[i - 1] + chunk_duration
            if delivered[i] <= deadline:
                start_chunk.append(deadline)
                stalls.append(0.0)
                wait_for_per_chunk.append(0)
            else:
                # Stall detected: chunk i is not ready by its deadline (rebuffering start).
                # Count pending = chunks requested by deadline (request_times <= deadline)
                # that have not arrived by deadline. Count over ALL chunks, not just delivered.
                orig_idx_i = delivered_indices[i]
                pending_count = 0
                for j in range(orig_idx_i, num_chunks):
                    if request_times[j] <= deadline:
                        if arrivals[j] is None or arrivals[j] > deadline:
                            pending_count += 1
                    else:
                        break
                wait_for = min(initial_buffer, max(pending_count, 1))
                # Collect arrival times of pending chunks that do arrive
                pending_arrivals: list[float] = []
                for j in range(orig_idx_i, num_chunks):
                    if request_times[j] <= deadline:
                        if arrivals[j] is not None and arrivals[j] > deadline:
                            pending_arrivals.append(arrivals[j])
                    else:
                        break
                pending_arrivals.sort()
                if len(pending_arrivals) >= wait_for:
                    resume_at = pending_arrivals[wait_for - 1]
                    start_chunk.append(resume_at)
                else:
                    # Fewer than wait_for arrive; flow ends while waiting - do not play
                    resume_at = flow_end_sec if flow_end_sec is not None else (
                        pending_arrivals[-1] if pending_arrivals else delivered[i]
                    )
                    start_chunk.append(None)  # never played
                stall = resume_at - deadline
                stalls.append(stall)
                wait_for_per_chunk.append(wait_for)

    num_stalls = sum(1 for s in stalls if s > 0)
    num_chunks_with_rebuffering = num_stalls
    chunks_with_rebuffering_pct = (
        100.0 * num_chunks_with_rebuffering / len(delivered) if delivered else 0.0
    )
    # Chunks played after rebuffering: for each stall where we resumed, count wait_for chunks (Option B)
    # When flow ends while waiting (start_chunk[i] is None), we never played those chunks
    num_chunks_played_after_rebuffering = sum(
        wait_for_per_chunk[i]
        for i in range(len(stalls))
        if stalls[i] > 0 and start_chunk[i] is not None
    )
    total_stall = sum(stalls)
    # Last played chunk: find last non-None start_chunk (never-played chunks have None)
    last_played_idx = next((i for i in range(len(start_chunk) - 1, -1, -1) if start_chunk[i] is not None), -1)
    num_played = last_played_idx + 1
    total_playtime = num_played * chunk_duration
    # Startup stall: first initial_buffer chunks are played after that rebuffer
    if stalls and stalls[0] > 0:
        num_chunks_played_after_rebuffering += min(initial_buffer, num_played)
    chunks_played_after_rebuffering_pct = (
        100.0 * num_chunks_played_after_rebuffering / num_played if num_played > 0 else 0.0
    )
    stall_until_end = 0.0
    # Only add stall_until_end when we actually played the last delivered chunk and
    # are waiting for an undelivered one. If we never played the last delivered chunk
    # (flow ended while rebuffering), that stall is already in stalls[].
    if (undelivered_count > 0 and flow_end_sec is not None and delivered and last_played_idx >= 0
            and last_played_idx == len(delivered) - 1):
        last_playback_end = start_chunk[last_played_idx] + chunk_duration
        stall_until_end = max(0.0, flow_end_sec - last_playback_end)
        total_stall += stall_until_end
        if stall_until_end > 0:
            num_stalls += 1
    rebuffer_ratio_pct = 100.0 * total_stall / total_playtime if total_playtime > 0 else 0.0

    # Build timeline events
    events: list[tuple[float, str]] = [(0.0, "Flow start (CONNECT)")]
    for i in range(len(delivered)):
        events.append((delivered[i], f"Chunk {delivered_indices[i] + 1} downloaded"))
        if i == 0:
            startup_deadline = startup_delay if startup_delay is not None else initial_buffer * chunk_duration
            if stalls[0] > 0:
                events.append((startup_deadline,
                    f"Initial buffer deadline ({initial_buffer} chunks by {startup_deadline:.1f}s, "
                    f"buffering {stalls[0]:.2f}s)"))
            events.append((start_chunk[0],
                f"Playback starts (buffered {min(initial_buffer, len(delivered))} chunks)"))
        else:
            deadline = start_chunk[i - 1] + chunk_duration
            if stalls[i] > 0:
                events.append((deadline, f"Chunk {delivered_indices[i] + 1} needed by now"))
                w = wait_for_per_chunk[i] if i < len(wait_for_per_chunk) else initial_buffer
                rebuffer_ts = flow_end_sec if start_chunk[i] is None else start_chunk[i]
                events.append((rebuffer_ts,
                    f"Rebuffering {stalls[i]:.2f}s (waited for {w} chunk(s))"))
            if start_chunk[i] is not None:
                events.append((start_chunk[i], f"Chunk {delivered_indices[i] + 1} playback starts"))
    if undelivered_count > 0 and flow_end_sec is not None and delivered and last_played_idx >= 0:
        last_playback_end = start_chunk[last_played_idx] + chunk_duration
        next_chunk_idx = delivered_indices[last_played_idx] + 2
        events.append((last_playback_end, f"Chunk {delivered_indices[last_played_idx] + 1} playback finishes"))
        # Only add "Chunk Y needed by now" when we played the last delivered chunk (waiting for undelivered).
        # If we never played the next chunk, it was already added in the stall loop.
        if last_played_idx == len(delivered) - 1:
            events.append((last_playback_end, f"Chunk {next_chunk_idx} needed by now"))
        events.append((flow_end_sec, "Flow ends"))
        if stall_until_end > 0:
            events.append((flow_end_sec, f"Stall until end: {stall_until_end:.2f}s"))

    def _order(msg: str) -> int:
        if "downloaded" in msg:
            return 0
        if "Rebuffering" in msg:
            return 1
        if "playback" in msg.lower():
            return 2
        if "needed by now" in msg:
            return 3
        if "Flow ends" in msg:
            return 4
        if "Stall until end" in msg:
            return 5
        return -1

    events.sort(key=lambda x: (x[0], _order(x[1]), x[1]))
    timeline = [f"  t={t:.2f}s: {msg}" for t, msg in events]

    result: dict = {
        "num_chunks": len(delivered),
        "num_chunks_played": num_played,
        "total_bytes": total_bytes,
        "total_playtime_sec": total_playtime,
        "initial_buffer": initial_buffer,
        "num_stalls": num_stalls,
        "num_chunks_with_rebuffering": num_chunks_with_rebuffering,
        "chunks_with_rebuffering_pct": round(chunks_with_rebuffering_pct, 2),
        "num_chunks_played_after_rebuffering": num_chunks_played_after_rebuffering,
        "chunks_played_after_rebuffering_pct": round(chunks_played_after_rebuffering_pct, 2),
        "total_rebuffering_sec": total_stall,
        "rebuffer_ratio_pct": round(rebuffer_ratio_pct, 2),
        "arrivals_sec": [round(a, 3) for a in delivered],
        "stalls_sec": [round(s, 3) for s in stalls],
        "timeline": timeline,
    }
    if undelivered_count > 0:
        result["num_chunks_undelivered"] = undelivered_count
    return result


def analyze_file(
    path: str,
    chunk_size: int,
    chunk_duration: float,
    include_details: bool = False,
    receiver_json: str | None = None,
    bytes_per_packet: int = 1448,
    num_chunks: int | None = None,
    initial_buffer: int = 1,
    startup_delay: float | None = None,
) -> dict:
    """
    Analyze one log file. Returns per-flow results and a summary.
    If log has no bytes_acked, use receiver_json if provided.
    """
    flows, flow_end_sec = parse_log(path)
    if not flows and receiver_json and os.path.isfile(receiver_json):
        samples = parse_receiver_json(receiver_json, bytes_per_packet)
        if samples:
            flows = {1: samples}
        else:
            return {"file": path, "error": "receiver JSON has no valid samples"}
    if not flows:
        return {"file": path, "error": "no TCPINFO with bytes_acked found (use --receiver-json for PRAGUE)"}

    results: dict = {
        "file": path,
        "chunk_size_bytes": chunk_size,
        "chunk_duration_sec": chunk_duration,
        "flows": {},
    }

    for flow_id, samples in flows.items():
        end_sec = flow_end_sec.get(flow_id) if flow_end_sec else None
        r = analyze_flow(samples, chunk_size, chunk_duration, num_chunks_hint=num_chunks, flow_end_sec=end_sec, initial_buffer=initial_buffer, startup_delay=startup_delay)
        if "error" in r and "num_chunks" in r and r["num_chunks"] == 0:
            results["flows"][flow_id] = r
            continue
        if "error" in r:
            results["flows"][flow_id] = r
            continue
        out = {
            "num_chunks": r["num_chunks"],
            "num_chunks_played": r.get("num_chunks_played", r["num_chunks"]),
            "total_playtime_sec": r["total_playtime_sec"],
            "num_stalls": r["num_stalls"],
            "num_chunks_with_rebuffering": r.get("num_chunks_with_rebuffering", 0),
            "chunks_with_rebuffering_pct": r.get("chunks_with_rebuffering_pct", 0.0),
            "num_chunks_played_after_rebuffering": r.get("num_chunks_played_after_rebuffering", 0),
            "chunks_played_after_rebuffering_pct": r.get("chunks_played_after_rebuffering_pct", 0.0),
            "total_rebuffering_sec": r["total_rebuffering_sec"],
            "rebuffer_ratio_pct": r["rebuffer_ratio_pct"],
        }
        if r.get("num_chunks_undelivered", 0) > 0:
            out["num_chunks_undelivered"] = r["num_chunks_undelivered"]
        if include_details:
            out["arrivals_sec"] = r["arrivals_sec"]
            out["stalls_sec"] = r["stalls_sec"]
        if "timeline" in r:
            out["timeline"] = r["timeline"]
        results["flows"][flow_id] = out

    # Summary across flows (for multi-flow logs, aggregate)
    valid = [f for f in results["flows"].values() if "num_stalls" in f]
    if valid:
        total_chunks = sum(x["num_chunks"] for x in valid)
        total_chunks_played = sum(x.get("num_chunks_played", x["num_chunks"]) for x in valid)
        total_chunks_with_rebuffering = sum(x.get("num_chunks_with_rebuffering", 0) for x in valid)
        total_chunks_played_after_rebuffering = sum(
            x.get("num_chunks_played_after_rebuffering", 0) for x in valid
        )
        results["summary"] = {
            "num_flows": len(valid),
            "total_chunks": total_chunks,
            "total_chunks_played": total_chunks_played,
            "total_stalls": sum(x["num_stalls"] for x in valid),
            "total_rebuffering_sec": sum(x["total_rebuffering_sec"] for x in valid),
            "total_playtime_sec": sum(x["total_playtime_sec"] for x in valid),
            "rebuffer_ratio_pct": round(
                100.0
                * sum(x["total_rebuffering_sec"] for x in valid)
                / sum(x["total_playtime_sec"] for x in valid)
                if sum(x["total_playtime_sec"] for x in valid) > 0
                else 0,
                2,
            ),
            "chunks_with_rebuffering_pct": round(
                100.0 * total_chunks_with_rebuffering / total_chunks if total_chunks > 0 else 0.0,
                2,
            ),
            "chunks_played_after_rebuffering_pct": round(
                100.0 * total_chunks_played_after_rebuffering / total_chunks_played
                if total_chunks_played > 0 else 0.0,
                2,
            ),
        }
    else:
        results["summary"] = {"error": "no valid flows"}

    return results


def main():
    ap = argparse.ArgumentParser(
        description="Analyze video streaming performance from MGEN .log files"
    )
    ap.add_argument(
        "files",
        nargs="*",
        help="Log files to analyze (default: all .log in directory)",
    )
    ap.add_argument(
        "-d",
        "--directory",
        default=".",
        help="Directory to search for .log files (default: current)",
    )
    ap.add_argument(
        "--chunk-duration",
        type=float,
        required=True,
        help="Chunk duration in seconds (e.g. 2)",
    )
    ap.add_argument(
        "--chunk-size",
        type=int,
        help="Chunk size in bytes (e.g. 2500696)",
    )
    ap.add_argument(
        "--chunk-size-packets",
        type=int,
        help="Chunk size as number of packets (use with --bytes-per-packet)",
    )
    ap.add_argument(
        "--bytes-per-packet",
        type=int,
        default=1448,
        help="Bytes per packet (default 1448)",
    )
    ap.add_argument(
        "--num-chunks",
        type=int,
        help="Explicit number of chunks (e.g. 15 for 30s at 2s/chunk). Undelivered chunks marked as not delivered.",
    )
    ap.add_argument(
        "--receiver-json",
        help="Receiver JSON file (for PRAGUE when log has no bytes_acked)",
    )
    ap.add_argument(
        "--receiver-dir",
        help="Directory to find receiver JSON (look for {log_stem}_rx.json)",
    )
    ap.add_argument(
        "-o",
        "--output",
        help="Write results to JSON file",
    )
    ap.add_argument(
        "--details",
        action="store_true",
        help="Include per-chunk arrivals and stalls in output",
    )
    ap.add_argument(
        "--timeline",
        action="store_true",
        help="Print event timeline (chunk downloads, playback start, rebuffering)",
    )
    ap.add_argument(
        "--initial-buffer",
        type=int,
        default=1,
        help="Number of chunks to buffer before playback starts and before resuming "
        "after a mid-stream stall (default: 1). With 2, playback starts after 2 "
        "chunks are buffered, and mid-stream stalls also wait for 2 pending chunks "
        "when available.",
    )
    ap.add_argument(
        "--startup-delay",
        type=float,
        default=None,
        help="Override the initial playback deadline in seconds (default: "
        "initial_buffer * chunk_duration). Playback starts at "
        "max(startup_delay, arrival of initial_buffer-th chunk). "
        "Any extra wait beyond startup_delay counts as rebuffering.",
    )
    args = ap.parse_args()

    chunk_size: int | None = None
    if args.chunk_size is not None:
        chunk_size = args.chunk_size
    elif args.chunk_size_packets is not None:
        chunk_size = args.chunk_size_packets * args.bytes_per_packet
    else:
        print("Error: specify --chunk-size or --chunk-size-packets", file=sys.stderr)
        sys.exit(1)

    if chunk_size <= 0:
        print("Error: chunk size must be positive", file=sys.stderr)
        sys.exit(1)

    files: list[str] = list(args.files)
    if not files:
        d = Path(args.directory)
        files = sorted(str(p) for p in d.glob("*.log"))
        if not files:
            print(f"No .log files in {args.directory}", file=sys.stderr)
            sys.exit(1)

    all_results: list[dict] = []
    for i, path in enumerate(files):
        if not os.path.isfile(path):
            print(f"Warning: skipping non-file {path}", file=sys.stderr)
            continue
        receiver_path: str | None = None
        if args.receiver_json and i == 0:
            receiver_path = args.receiver_json
        elif args.receiver_dir:
            stem = Path(path).stem
            candidate = Path(args.receiver_dir) / f"{stem}_rx.json"
            if candidate.exists():
                receiver_path = str(candidate)
        r = analyze_file(
            path,
            chunk_size,
            args.chunk_duration,
            args.details,
            receiver_json=receiver_path,
            bytes_per_packet=args.bytes_per_packet,
            num_chunks=args.num_chunks,
            initial_buffer=args.initial_buffer,
            startup_delay=args.startup_delay,
        )
        all_results.append(r)

        # Pretty-print to stdout
        name = os.path.basename(path)
        print(f"\n=== {name} ===")
        if "error" in r and "flows" not in r:
            print(f"  Error: {r['error']}")
            continue
        for flow_id, fr in r.get("flows", {}).items():
            if "error" in fr:
                print(f"  Flow {flow_id}: {fr['error']}")
            else:
                undel = f", {fr['num_chunks_undelivered']} undelivered" if fr.get("num_chunks_undelivered") else ""
                played = fr.get("num_chunks_played", fr["num_chunks"])
                chunks_rebuf = fr.get("chunks_with_rebuffering_pct", 0)
                chunks_after_rebuf = fr.get("chunks_played_after_rebuffering_pct", 0)
                print(
                    f"  Flow {flow_id}: {fr['num_chunks']} delivered, {played} played{undel}, "
                    f"{fr['num_stalls']} stalls, "
                    f"{fr['total_rebuffering_sec']:.2f}s rebuffering, "
                    f"{fr['rebuffer_ratio_pct']}% rebuffer ratio, "
                    f"{chunks_rebuf}% chunks triggered rebuffering, "
                    f"{chunks_after_rebuf}% chunks played after rebuffering"
                )
                if args.timeline and "timeline" in fr:
                    print("  Timeline:")
                    for line in fr["timeline"]:
                        print(line)
        if "summary" in r and "error" not in r["summary"]:
            s = r["summary"]
            chunks_rebuf = s.get("chunks_with_rebuffering_pct", 0)
            chunks_after_rebuf = s.get("chunks_played_after_rebuffering_pct", 0)
            print(
                f"  Summary: {s['num_flows']} flow(s), "
                f"{s.get('total_chunks', '?')} delivered, {s.get('total_chunks_played', '?')} played, "
                f"{s['total_stalls']} stalls, "
                f"{s['total_rebuffering_sec']:.2f}s rebuffering, "
                f"{s['rebuffer_ratio_pct']}% rebuffer ratio, "
                f"{chunks_rebuf}% chunks triggered rebuffering, "
                f"{chunks_after_rebuf}% chunks played after rebuffering"
            )

    # Group results by experiment (same params, different trial number _t102_)
    experiments: dict[str, list[tuple[int | None, dict]]] = defaultdict(list)
    for r in all_results:
        path = r.get("file", "")
        exp_key, trial_num = get_experiment_and_trial(path)
        experiments[exp_key].append((trial_num, r))
    for exp_key in experiments:
        experiments[exp_key].sort(key=lambda x: (x[0] is None, x[0] or 0))

    # Aggregate per experiment: average per-trial first, then across trials
    aggregates: dict[str, dict] = {}
    for exp_key in sorted(experiments.keys()):
        trial_results = experiments[exp_key]
        per_trial_mean_rebuffer: list[float] = []
        per_trial_mean_stalls: list[float] = []
        per_trial_delivered_fraction: list[float] = []
        per_trial_chunks_rebuffering_pct: list[float] = []
        per_trial_chunks_played_after_rebuffering_pct: list[float] = []
        total_flows = 0
        for _trial_num, r in trial_results:
            flows_data = [f for f in r.get("flows", {}).values() if "total_rebuffering_sec" in f]
            if not flows_data:
                continue
            total_flows += len(flows_data)
            trial_rebuffer = sum(f["total_rebuffering_sec"] for f in flows_data)
            per_trial_mean_rebuffer.append(trial_rebuffer / len(flows_data))
            trial_stalls = sum(f["num_stalls"] for f in flows_data)
            per_trial_mean_stalls.append(trial_stalls / len(flows_data))
            trial_delivered = sum(f["num_chunks"] for f in flows_data)
            trial_played = sum(f.get("num_chunks_played", f["num_chunks"]) for f in flows_data)
            trial_requested = sum(
                f["num_chunks"] + f.get("num_chunks_undelivered", 0) for f in flows_data
            )
            frac = 100.0 * trial_delivered / trial_requested if trial_requested > 0 else 0.0
            per_trial_delivered_fraction.append(frac)
            trial_chunks_rebuf = sum(f.get("num_chunks_with_rebuffering", 0) for f in flows_data)
            trial_chunks_rebuf_pct = (
                100.0 * trial_chunks_rebuf / trial_delivered if trial_delivered > 0 else 0.0
            )
            per_trial_chunks_rebuffering_pct.append(trial_chunks_rebuf_pct)
            trial_chunks_after_rebuf = sum(
                f.get("num_chunks_played_after_rebuffering", 0) for f in flows_data
            )
            trial_chunks_after_rebuf_pct = (
                100.0 * trial_chunks_after_rebuf / trial_played if trial_played > 0 else 0.0
            )
            per_trial_chunks_played_after_rebuffering_pct.append(trial_chunks_after_rebuf_pct)
        if per_trial_mean_rebuffer:
            mean_rebuffer_per_flow = sum(per_trial_mean_rebuffer) / len(per_trial_mean_rebuffer)
            mean_stalls_per_flow = sum(per_trial_mean_stalls) / len(per_trial_mean_stalls)
            mean_delivered_fraction_pct = sum(per_trial_delivered_fraction) / len(per_trial_delivered_fraction)
            mean_chunks_rebuffering_pct = (
                sum(per_trial_chunks_rebuffering_pct) / len(per_trial_chunks_rebuffering_pct)
                if per_trial_chunks_rebuffering_pct
                else 0.0
            )
            mean_chunks_played_after_rebuffering_pct = (
                sum(per_trial_chunks_played_after_rebuffering_pct)
                / len(per_trial_chunks_played_after_rebuffering_pct)
                if per_trial_chunks_played_after_rebuffering_pct
                else 0.0
            )
            n_trials = len(per_trial_mean_rebuffer)
            aggregates[exp_key] = {
                "mean_rebuffer_per_flow_sec": round(mean_rebuffer_per_flow, 2),
                "mean_stalls_per_flow": round(mean_stalls_per_flow, 2),
                "mean_delivered_fraction_pct": round(mean_delivered_fraction_pct, 2),
                "mean_chunks_with_rebuffering_pct": round(mean_chunks_rebuffering_pct, 2),
                "mean_chunks_played_after_rebuffering_pct": round(
                    mean_chunks_played_after_rebuffering_pct, 2
                ),
                "total_flows": total_flows,
                "num_trials": n_trials,
            }
            print("\n--- Final results (mean per trial, then across trials) ---")
            print(f"  Experiment: {exp_key}")
            print(f"  Mean rebuffer time per flow (seconds): {mean_rebuffer_per_flow:.2f}")
            print(f"  Mean stalls per flow: {mean_stalls_per_flow:.2f}")
            print(f"  Mean delivered fraction (%): {mean_delivered_fraction_pct:.2f}")
            print(f"  Mean chunks triggered rebuffering (%): {mean_chunks_rebuffering_pct:.2f}")
            print(
                f"  Mean chunks played after rebuffering (%): "
                f"{mean_chunks_played_after_rebuffering_pct:.2f}"
            )
            print(f"  (n={total_flows} flows across {n_trials} trials)")

    if args.output:
        output_data: dict = {"trials": all_results, "experiments": dict(aggregates)}
        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2)
        print(f"\nResults written to {args.output}")


if __name__ == "__main__":
    main()
