#!/usr/bin/env python3
"""
Analyze file transfer completion times from MGEN TCPINFO log files.
================================================================

For each .log file, computes flow completion time as the earliest of:
  - bytes_acked reaching target (count × bytes_per_packet)
  - SHUTDOWN event
  - OFF event

Reports individual and average completion times per file, per experiment
(grouped by trial _t102_), with per-trial then across-trials averaging.

Requires TCPINFO lines with bytes_acked, and/or SHUTDOWN/OFF events.
Time origin: ON or CONNECT per flow.

Usage:
  # Analyze all .log files in current directory
  python3 analyze_file_transfer.py --count 72416 --bytes-per-packet 1448

  # Or specify total bytes directly
  python3 analyze_file_transfer.py --target-bytes 104858368

  # Specify directory and output JSON
  python3 analyze_file_transfer.py -d . --count 72416 --bytes-per-packet 1448 -o results.json
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path


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
SHUTDOWN_RE = re.compile(
    r"(?P<time>\d{2}:\d{2}:\d{2}\.\d+)\s+SHUTDOWN\s+flow>(?P<flow>\d+)\b"
)
OFF_RE = re.compile(
    r"(?P<time>\d{2}:\d{2}:\d{2}\.\d+)\s+OFF\s+flow>(?P<flow>\d+)\b"
)
TRIAL_RE = re.compile(r"_t(\d+)(?:_|$)")


def get_experiment_and_trial(path: str) -> tuple[str, int | None]:
    stem = Path(path).stem
    m = TRIAL_RE.search(stem)
    if not m:
        return stem, None
    trial_num = int(m.group(1))
    exp_key = TRIAL_RE.sub("_", stem)
    exp_key = re.sub(r"_+", "_", exp_key).strip("_")
    return exp_key, trial_num


def parse_timestamp(ts: str) -> float:
    parts = ts.split(":")
    h, m = int(parts[0]), int(parts[1])
    s = float(parts[2])
    return h * 3600 + m * 60 + s


def parse_log(path: str) -> tuple[dict[int, list[tuple[float, int]]], dict[int, float], dict[int, float]]:
    """Parse MGEN log. Returns (bytes_acked samples, shutdown_sec, off_sec) per flow, relative to ON/CONNECT."""
    t0_per_flow: dict[int, float] = {}
    first_tcpinfo_per_flow: dict[int, float] = {}
    with open(path) as f:
        for line in f:
            m_conn = CONNECT_RE.search(line)
            m_on = ON_RE.search(line)
            if m_conn:
                t0_per_flow[int(m_conn.group("flow"))] = parse_timestamp(m_conn.group("time"))
            elif m_on and int(m_on.group("flow")) not in t0_per_flow:
                t0_per_flow[int(m_on.group("flow"))] = parse_timestamp(m_on.group("time"))
            m = TCPINFO_RE.search(line)
            if m and int(m.group("flow")) not in first_tcpinfo_per_flow:
                first_tcpinfo_per_flow[int(m.group("flow"))] = parse_timestamp(m.group("time"))

    def t0(flow: int) -> float:
        return t0_per_flow.get(flow, first_tcpinfo_per_flow.get(flow, 0.0))

    data: dict[int, list[tuple[float, int]]] = defaultdict(list)
    shutdown_sec: dict[int, float] = {}
    off_sec: dict[int, float] = {}
    with open(path) as f:
        for line in f:
            m_shut = SHUTDOWN_RE.search(line)
            m_off = OFF_RE.search(line)
            if m_shut:
                flow = int(m_shut.group("flow"))
                t = parse_timestamp(m_shut.group("time"))
                shutdown_sec[flow] = t - t0(flow)
                continue
            if m_off:
                flow = int(m_off.group("flow"))
                t = parse_timestamp(m_off.group("time"))
                off_sec[flow] = t - t0(flow)
                continue
            m = TCPINFO_RE.search(line)
            if not m:
                continue
            ba_match = BYTES_ACKED_RE.search(line)
            if not ba_match:
                continue
            bytes_acked = int(ba_match.group("bytes_acked"))
            flow = int(m.group("flow"))
            t = parse_timestamp(m.group("time"))
            data[flow].append((t - t0(flow), bytes_acked))

    for flow, samples in data.items():
        if flow in t0_per_flow and samples and samples[0][0] > 0:
            data[flow] = [(0.0, 0)] + samples

    return dict(data), shutdown_sec, off_sec


def interpolate_completion(
    samples: list[tuple[float, int]], target_bytes: int
) -> float | None:
    """Time (sec) when bytes_acked first reaches target_bytes. None if never reached."""
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


def analyze_file(path: str, target_bytes: int) -> dict | None:
    """Analyze one log file. Returns per-flow completion times (sec) or None.
    Completion time = earliest of: bytes_acked reaching target, SHUTDOWN, OFF."""
    data, shutdown_sec, off_sec = parse_log(path)
    if not data:
        return None
    flows: dict[int, dict] = {}
    for flow_id, samples in data.items():
        candidates: list[float] = []
        ct_bytes = interpolate_completion(samples, target_bytes)
        if ct_bytes is not None:
            candidates.append(ct_bytes)
        if flow_id in shutdown_sec:
            candidates.append(shutdown_sec[flow_id])
        if flow_id in off_sec:
            candidates.append(off_sec[flow_id])
        if candidates:
            ct = min(candidates)
            flows[flow_id] = {"completion_time_sec": round(ct, 2)}
        else:
            flows[flow_id] = {"completion_time_sec": None, "error": "no completion event"}
    completion_times = [f["completion_time_sec"] for f in flows.values() if f["completion_time_sec"] is not None]
    mean_ct = sum(completion_times) / len(completion_times) if completion_times else None
    return {
        "file": path,
        "target_bytes": target_bytes,
        "flows": flows,
        "completion_times_sec": [round(t, 2) for t in completion_times],
        "mean_completion_time_sec": round(mean_ct, 2) if mean_ct is not None else None,
        "n_flows_completed": len(completion_times),
        "n_flows_total": len(flows),
    }


def run(
    directory: str,
    target_bytes: int,
    output_path: str | None,
) -> dict:
    """Scan directory for .log files, group by experiment, aggregate."""
    files = sorted(Path(directory).glob("*.log"))
    all_results: list[dict] = []
    for p in files:
        path = str(p)
        r = analyze_file(path, target_bytes)
        if r is None or not r["flows"]:
            continue
        all_results.append(r)

    # Group by experiment
    experiments: dict[str, list[tuple[int | None, dict]]] = defaultdict(list)
    for r in all_results:
        path = r.get("file", "")
        exp_key, trial_num = get_experiment_and_trial(path)
        experiments[exp_key].append((trial_num, r))
    for exp_key in experiments:
        experiments[exp_key].sort(key=lambda x: (x[0] is None, x[0] or 0))

    # Aggregate per experiment: per-trial mean, then across trials
    aggregates: dict[str, dict] = {}
    for exp_key in sorted(experiments.keys()):
        trial_results = experiments[exp_key]
        per_trial_mean: list[float] = []
        total_flows = 0
        for _trial_num, r in trial_results:
            ct_vals = [f["completion_time_sec"] for f in r["flows"].values() if f.get("completion_time_sec") is not None]
            if not ct_vals:
                continue
            total_flows += len(ct_vals)
            per_trial_mean.append(sum(ct_vals) / len(ct_vals))
        if per_trial_mean:
            mean_completion_sec = sum(per_trial_mean) / len(per_trial_mean)
            n_trials = len(per_trial_mean)
            aggregates[exp_key] = {
                "mean_flow_completion_time_sec": round(mean_completion_sec, 2),
                "total_flows": total_flows,
                "num_trials": n_trials,
            }

    return {
        "trials": all_results,
        "experiments": aggregates,
    }


def main():
    ap = argparse.ArgumentParser(
        description="Analyze file transfer completion times from MGEN log files.",
    )
    ap.add_argument(
        "-d", "--directory",
        default=".",
        help="Directory containing .log files (default: current)",
    )
    ap.add_argument(
        "--count",
        type=int,
        help="Number of packets per flow (use with --bytes-per-packet)",
    )
    ap.add_argument(
        "--bytes-per-packet",
        type=int,
        default=1448,
        help="Bytes per packet (default: 1448)",
    )
    ap.add_argument(
        "--target-bytes",
        type=int,
        help="Total bytes per flow (alternative to --count × --bytes-per-packet)",
    )
    ap.add_argument(
        "-o", "--output",
        help="Write results to JSON file",
    )
    args = ap.parse_args()

    target_bytes: int | None = None
    if args.target_bytes is not None:
        target_bytes = args.target_bytes
    elif args.count is not None:
        target_bytes = args.count * args.bytes_per_packet
    else:
        print("Error: specify --target-bytes or --count (with --bytes-per-packet)", file=sys.stderr)
        sys.exit(1)

    if target_bytes <= 0:
        print("Error: target bytes must be positive", file=sys.stderr)
        sys.exit(1)

    d = Path(args.directory)
    if not d.is_dir():
        print(f"Error: not a directory: {args.directory}", file=sys.stderr)
        sys.exit(1)

    result = run(str(d), target_bytes, args.output)

    if not result["trials"]:
        print("No .log files with valid TCPINFO found.", file=sys.stderr)
        sys.exit(1)

    for r in result["trials"]:
        name = os.path.basename(r["file"])
        print(f"\n=== {name} ===")
        for flow_id, fr in sorted(r["flows"].items()):
            ct = fr.get("completion_time_sec")
            if ct is not None:
                print(f"  Flow {flow_id}: {ct:.2f}s")
            else:
                print(f"  Flow {flow_id}: {fr.get('error', 'not completed')}")
        if r["mean_completion_time_sec"] is not None:
            print(f"  Mean: {r['mean_completion_time_sec']:.2f}s ({r['n_flows_completed']}/{r['n_flows_total']} flows)")

    print("\n--- Experiment summaries (mean FCT per trial, then across trials) ---")
    for exp_key, agg in sorted(result["experiments"].items()):
        print(f"  {exp_key}: mean FCT = {agg['mean_flow_completion_time_sec']:.2f}s (n={agg['total_flows']} flows, {agg['num_trials']} trials)")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nResults written to {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
