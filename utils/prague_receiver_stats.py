#!/usr/bin/env python3
"""
Aggregate UDP Prague receiver JSON files by scenario.

Run this on the receiver node (where udp_prague_receiver writes JSON files).
Parses *_rx_*_port*.json files, groups by scenario (app, cc, network, etc.),
and outputs mean rcvd_rate (goodput Mbps), RTT, mark_prob, loss_prob across
all flows and trials for each scenario.

Workflow:
  1. Upload this script to the receiver node (e.g. rxL4S)
  2. On receiver: cd ~/L4S_Project/udp_prague && python3 prague_receiver_stats.py -o prague_receiver_agg.json
  3. Download prague_receiver_agg.json to your local mgen/ directory
  4. Run: python3 collect_and_plot_mgen.py --prague-receiver-json prague_receiver_agg.json

Usage:
  # From directory containing JSON files (e.g. ~/L4S_Project/udp_prague)
  python3 prague_receiver_stats.py

  # Or specify directory
  python3 prague_receiver_stats.py /path/to/json/files

  # Output JSON for downstream use
  python3 prague_receiver_stats.py -o prague_receiver_agg.json
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict

# Filename built by build_exp_name() in the experiment driver:
#   {app_L4S}-{proto_L4S}_{app_legacy}-{proto_legacy}_{cc_L4S}_{cc_legacy}_{aqm}_{n_bdp}_{ecn}_{rtt}ms_{cap}Mbps_t{trial}_rx_{L4S|legacy}_port{port}.json
# Example: call-PRAGUE_updates-TCP_prague_cubic_DualPI2_8_45_30ms_100Mbps_t2_rx_L4S_port5105.json
PAT = re.compile(
    r"^([^-]+)-([^_]+)"                              # app_L4S, proto_L4S
    r"_([^-]+)-([^_]+)"                              # app_legacy, proto_legacy
    r"_([^_]+)_([^_]+)"                              # cc_L4S, cc_legacy
    r"_([^_]+)_([^_]+)_([^_]+)"                      # aqm, n_bdp, ecn
    r"_(\d+)ms_(\d+)Mbps"                            # rtt, cap
    r"_t(\d+)_rx_(L4S|legacy)_port(\d+)\.json$"      # trial, side, port
)


# Minimum rcvd_rate (Mbps) to consider a sample as "ON" for streaming.
# OFF periods have near-zero rate (~0.0006); ON periods have 1-3+ Mbps.
STREAMING_ON_THRESHOLD_MBPS = 0.1

# Video call: bucket samples into intervals for bad-interval metric.
# IMPORTANT: The effective granularity equals the receiver's report interval.
# - If receiver reports every 1 s (default -i 1000000): each sample is its own bucket,
#   so bad_interval_fraction is effectively "bad-sample fraction at 1 s granularity".
# - For true 100 ms bad-interval fraction: run receiver with -i 100000 (100 ms reports).
CALL_INTERVAL_US = 100_000  # 100 ms


def _get_rtt(obj: dict) -> float:
    """RTT or ATO (RFC8888) in ms."""
    return float(obj.get("RTT", obj.get("ATO", 0)))


def parse_file(
    filepath: str,
    skip_warmup: int = 2,
    app_L4S: str | None = None,
    streaming_on_threshold_mbps: float = STREAMING_ON_THRESHOLD_MBPS,
    target_rate_mbps: float = 5.0,
    rtt_threshold_ms: float = 150.0,
    bad_rate_threshold: float = 0.9,
) -> dict | None:
    """
    Parse a receiver JSON file. Each line is a JSON object.
    Returns dict with avg rcvd_rate_mbps, rtt_ms, mark_prob, loss_prob, n_samples.
    For call app: also mean_p95_rtt_ms, bad_interval_fraction, mean_achieved_rate_fraction_pct.
    Skips first skip_warmup samples (often near-zero during startup).
    For streaming (app_L4S=="streaming"), keeps only samples with rcvd_rate above threshold.
    """
    samples = []
    try:
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                t_us = int(obj.get("time_since_start", 0))
                samples.append({
                    "time_since_start_us": t_us,
                    "rcvd_rate": float(obj.get("rcvd_rate", 0)),
                    "rtt_ms": _get_rtt(obj),
                    "mark_prob": float(obj.get("mark_prob", 0)),
                    "loss_prob": float(obj.get("loss_prob", 0)),
                })
    except (json.JSONDecodeError, KeyError, ValueError):
        return None

    if len(samples) <= skip_warmup:
        return None

    samples = samples[skip_warmup:]

    # For streaming: keep only samples during ON periods (rcvd_rate above threshold)
    if app_L4S == "streaming":
        samples = [s for s in samples if s["rcvd_rate"] >= streaming_on_threshold_mbps]
        if not samples:
            return None

    rcvd = [s["rcvd_rate"] for s in samples]
    rtt = [s["rtt_ms"] for s in samples]
    mark = [s["mark_prob"] for s in samples]
    loss = [s["loss_prob"] for s in samples]
    n = len(samples)
    result: dict = {
        "rcvd_rate_mbps": sum(rcvd) / n,
        "rtt_ms": sum(rtt) / n,
        "mark_prob": sum(mark) / n,
        "loss_prob": sum(loss) / n,
        "n_samples": n,
    }

    # Video call: add mean_achieved_rate_fraction_pct, mean_p95_rtt_ms, bad_interval_fraction
    if app_L4S == "call":
        mean_rcvd = result["rcvd_rate_mbps"]
        result["mean_achieved_rate_fraction_pct"] = (
            100.0 * mean_rcvd / target_rate_mbps if target_rate_mbps > 0 else 0.0
        )
        sorted_rtt = sorted(rtt)
        idx_95 = int(0.95 * len(sorted_rtt)) if sorted_rtt else 0
        result["mean_p95_rtt_ms"] = sorted_rtt[idx_95] if sorted_rtt else 0.0
        # Bucket samples into 100 ms intervals
        buckets: dict[int, list[dict]] = defaultdict(list)
        for s in samples:
            bid = s["time_since_start_us"] // CALL_INTERVAL_US
            buckets[bid].append(s)
        bad_count = 0
        for bid, bucket_samples in buckets.items():
            mean_rate = sum(x["rcvd_rate"] for x in bucket_samples) / len(bucket_samples)
            mean_rtt_b = sum(x["rtt_ms"] for x in bucket_samples) / len(bucket_samples)
            if mean_rate < bad_rate_threshold * target_rate_mbps or mean_rtt_b > rtt_threshold_ms:
                bad_count += 1
        result["bad_interval_fraction"] = bad_count / len(buckets) if buckets else 0.0

    return result


def run(
    directory: str,
    skip_warmup: int,
    output_path: str | None,
    streaming_on_threshold_mbps: float = STREAMING_ON_THRESHOLD_MBPS,
    target_rate_mbps: float = 5.0,
    rtt_threshold_ms: float = 150.0,
    bad_rate_threshold: float = 0.9,
) -> dict:
    """
    Scan directory for receiver JSON files, group by scenario, aggregate.
    Returns dict: scenario_key -> {mean_goodput_mbps, std_goodput_mbps, mean_rtt_ms, ...}
    For call app: also target_rate_mbps, mean_achieved_rate_fraction_pct, mean_p95_rtt_ms, bad_interval_fraction_pct.
    """
    groups = defaultdict(list)  # scenario_key -> list of per-file stats

    for f in os.listdir(directory):
        if not f.endswith(".json") or "_rx_" not in f or "_port" not in f:
            continue
        m = PAT.match(f)
        if not m:
            continue

        (
            app_L4S,
            proto_L4S,
            app_legacy,
            proto_legacy,
            cc_L4S,
            cc_legacy,
            aqm,
            n_bdp,
            ecn,
            rtt,
            cap,
            trial,
            side,
            port,
        ) = m.groups()

        filepath = os.path.join(directory, f)
        stats = parse_file(
            filepath,
            skip_warmup,
            app_L4S=app_L4S,
            streaming_on_threshold_mbps=streaming_on_threshold_mbps,
            target_rate_mbps=target_rate_mbps,
            rtt_threshold_ms=rtt_threshold_ms,
            bad_rate_threshold=bad_rate_threshold,
        )
        if stats is None:
            continue

        # Group key: scenario (exclude trial, port). n_bdp and ecn are part of the
        # network condition, so different values produce distinct scenarios.
        key = (
            app_L4S,
            proto_L4S,
            app_legacy,
            proto_legacy,
            cc_L4S,
            cc_legacy,
            aqm,
            n_bdp,
            ecn,
            rtt,
            cap,
            side,
        )
        stats["port"] = int(port)
        stats["trial"] = int(trial)
        stats["app_L4S"] = app_L4S
        stats["proto_L4S"] = proto_L4S
        stats["app_legacy"] = app_legacy
        stats["proto_legacy"] = proto_legacy
        stats["cc_L4S"] = cc_L4S
        stats["cc_legacy"] = cc_legacy
        stats["aqm"] = aqm
        stats["n_bdp"] = n_bdp
        stats["ecn"] = ecn
        stats["rtt"] = rtt
        stats["cap"] = cap
        stats["side"] = side
        groups[key].append(stats)

    # Aggregate per scenario
    result = {}
    for key, files_stats in groups.items():
        n = len(files_stats)
        goodput_vals = [s["rcvd_rate_mbps"] for s in files_stats]
        rtt_vals = [s["rtt_ms"] for s in files_stats]
        mark_vals = [s["mark_prob"] for s in files_stats]
        loss_vals = [s["loss_prob"] for s in files_stats]

        mean_g = sum(goodput_vals) / n
        mean_r = sum(rtt_vals) / n
        mean_m = sum(mark_vals) / n
        mean_l = sum(loss_vals) / n

        std_g = (sum((x - mean_g) ** 2 for x in goodput_vals) / n) ** 0.5 if n > 1 else 0.0
        std_r = (sum((x - mean_r) ** 2 for x in rtt_vals) / n) ** 0.5 if n > 1 else 0.0
        std_m = (sum((x - mean_m) ** 2 for x in mark_vals) / n) ** 0.5 if n > 1 else 0.0
        std_l = (sum((x - mean_l) ** 2 for x in loss_vals) / n) ** 0.5 if n > 1 else 0.0

        (
            app_L4S,
            proto_L4S,
            app_legacy,
            proto_legacy,
            cc_L4S,
            cc_legacy,
            aqm,
            n_bdp,
            ecn,
            rtt,
            cap,
            side,
        ) = key
        scenario_str = (
            f"{app_L4S}-{proto_L4S}_{app_legacy}-{proto_legacy}"
            f"_{cc_L4S}_{cc_legacy}_{aqm}_{n_bdp}_{ecn}"
            f"_{rtt}ms_{cap}Mbps_rx_{side}"
        )

        # Group by trial for per-trial and per-flow stats
        trials_data: dict[int, list[dict]] = defaultdict(list)
        for s in files_stats:
            trials_data[s["trial"]].append(s)

        trials_list: list[dict] = []
        for trial_num in sorted(trials_data.keys()):
            trial_files = trials_data[trial_num]
            nf = len(trial_files)
            tg = sum(x["rcvd_rate_mbps"] for x in trial_files) / nf
            tr = sum(x["rtt_ms"] for x in trial_files) / nf
            tm = sum(x["mark_prob"] for x in trial_files) / nf
            tl = sum(x["loss_prob"] for x in trial_files) / nf
            trial_obj: dict = {
                "trial": trial_num,
                "n_flows": nf,
                "mean_goodput_mbps": round(tg, 3),
                "mean_rtt_ms": round(tr, 3),
                "mean_mark_prob": round(tm, 2),
                "mean_loss_prob": round(tl, 2),
                "flows": [
                    {
                        "port": x["port"],
                        "rcvd_rate_mbps": round(x["rcvd_rate_mbps"], 3),
                        "rtt_ms": round(x["rtt_ms"], 3),
                        "mark_prob": round(x["mark_prob"], 2),
                        "loss_prob": round(x["loss_prob"], 2),
                        "n_samples": x["n_samples"],
                    }
                    for x in sorted(trial_files, key=lambda f: f["port"])
                ],
            }
            if app_L4S == "call" and any("mean_achieved_rate_fraction_pct" in x for x in trial_files):
                frac_vals = [x["mean_achieved_rate_fraction_pct"] for x in trial_files]
                p95_vals = [x["mean_p95_rtt_ms"] for x in trial_files]
                bad_vals = [x["bad_interval_fraction"] for x in trial_files]
                trial_obj["mean_achieved_rate_fraction_pct"] = round(sum(frac_vals) / nf, 2)
                trial_obj["mean_p95_rtt_ms"] = round(sum(p95_vals) / nf, 2)
                trial_obj["bad_interval_fraction"] = round(sum(bad_vals) / nf, 4)
            trials_list.append(trial_obj)

        out: dict = {
            "scenario": scenario_str,
            "app_L4S": app_L4S,
            "proto_L4S": proto_L4S,
            "app_legacy": app_legacy,
            "proto_legacy": proto_legacy,
            "cc_L4S": cc_L4S,
            "cc_legacy": cc_legacy,
            "aqm": aqm,
            "n_bdp": n_bdp,
            "ecn": ecn,
            "rtt": rtt,
            "cap": cap,
            "side": side,
            "mean_goodput_mbps": mean_g,
            "std_goodput_mbps": std_g,
            "mean_rtt_ms": mean_r,
            "std_rtt_ms": std_r,
            "mean_mark_prob": mean_m,
            "std_mark_prob": std_m,
            "mean_loss_prob": mean_l,
            "std_loss_prob": std_l,
            "n_flows": n,
            "n_trials": len(trials_data),
            "trials": trials_list,
        }

        # Video call: add target_rate, mean_achieved_rate_fraction_pct, mean_p95_rtt_ms, bad_interval_fraction_pct
        # Average per-trial first, then across trials (each trial weighted equally)
        if app_L4S == "call" and any("mean_achieved_rate_fraction_pct" in s for s in files_stats):
            out["target_rate_mbps"] = target_rate_mbps
            per_trial_frac = [t["mean_achieved_rate_fraction_pct"] for t in trials_list if "mean_achieved_rate_fraction_pct" in t]
            per_trial_p95 = [t["mean_p95_rtt_ms"] for t in trials_list if "mean_p95_rtt_ms" in t]
            per_trial_bad = [t["bad_interval_fraction"] for t in trials_list if "bad_interval_fraction" in t]
            out["mean_achieved_rate_fraction_pct"] = round(
                sum(per_trial_frac) / len(per_trial_frac), 2
            ) if per_trial_frac else 0.0
            out["mean_p95_rtt_ms"] = round(
                sum(per_trial_p95) / len(per_trial_p95), 2
            ) if per_trial_p95 else 0.0
            out["bad_interval_fraction_pct"] = round(
                100.0 * sum(per_trial_bad) / len(per_trial_bad), 2
            ) if per_trial_bad else 0.0

        result[scenario_str] = out

    return result


def build_scenario_key(
    app_L4S: str,
    proto_L4S: str,
    app_legacy: str,
    proto_legacy: str,
    cc_L4S: str,
    cc_legacy: str,
    aqm: str,
    n_bdp: str,
    ecn: str,
    rtt: str,
    cap: str,
    side: str = "L4S",
) -> str:
    """Build scenario key matching run() output format."""
    return (
        f"{app_L4S}-{proto_L4S}_{app_legacy}-{proto_legacy}"
        f"_{cc_L4S}_{cc_legacy}_{aqm}_{n_bdp}_{ecn}"
        f"_{rtt}ms_{cap}Mbps_rx_{side}"
    )


def load_prague_receiver_stats(json_path: str) -> dict:
    """
    Load aggregated receiver stats from JSON file (from prague_receiver_stats.py -o).
    Returns dict: scenario_key -> {mean_goodput_mbps, std_goodput_mbps, mean_rtt_ms, ...}
    """
    with open(json_path) as f:
        return json.load(f)


def main():
    p = argparse.ArgumentParser(
        description="Aggregate UDP Prague receiver JSON files by scenario.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run in current directory (e.g. ~/L4S_Project/udp_prague)
  python3 prague_receiver_stats.py

  # Specify directory
  python3 prague_receiver_stats.py /path/to/json/files

  # Output to JSON file
  python3 prague_receiver_stats.py -o prague_receiver_agg.json
        """,
    )
    p.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory containing receiver JSON files (default: current dir)",
    )
    p.add_argument(
        "--skip-warmup",
        type=int,
        default=2,
        help="Skip first N samples per file (default: 2)",
    )
    p.add_argument(
        "--streaming-on-threshold-mbps",
        type=float,
        default=STREAMING_ON_THRESHOLD_MBPS,
        help="For streaming: keep only samples with rcvd_rate >= this (Mbps); OFF periods ~0.0006 (default: 0.1)",
    )
    p.add_argument(
        "--target-rate-mbps",
        type=float,
        default=5.0,
        help="For call: target rate in Mbps for achieved-rate fraction (default: 5.0)",
    )
    p.add_argument(
        "--rtt-threshold-ms",
        type=float,
        default=150.0,
        help="For call: RTT above this (ms) makes an interval 'bad' (default: 150)",
    )
    p.add_argument(
        "--bad-rate-threshold",
        type=float,
        default=0.9,
        help="For call: achieved rate below this fraction of target makes interval 'bad' (default: 0.9). "
        "Note: bad_interval granularity = receiver report interval; use -i 100000 on receiver for true 100ms.",
    )
    p.add_argument(
        "-o", "--output",
        default="",
        help="Write aggregated stats to JSON file",
    )
    p.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress human-readable output",
    )
    p.add_argument(
        "--no-per-flow",
        action="store_true",
        help="Suppress per-flow console output (per-trial summary still shown; JSON includes all)",
    )
    args = p.parse_args()

    if not os.path.isdir(args.directory):
        print(f"Error: not a directory: {args.directory}", file=sys.stderr)
        sys.exit(1)

    result = run(
        args.directory,
        args.skip_warmup,
        args.output,
        streaming_on_threshold_mbps=args.streaming_on_threshold_mbps,
        target_rate_mbps=args.target_rate_mbps,
        rtt_threshold_ms=args.rtt_threshold_ms,
        bad_rate_threshold=args.bad_rate_threshold,
    )

    if not result:
        if not args.quiet:
            print("No matching receiver JSON files found.", file=sys.stderr)
        sys.exit(1)

    if not args.quiet:
        print("=" * 70)
        print("UDP Prague receiver stats (rcvd_rate = goodput Mbps)")
        print("=" * 70)
        for scenario, s in sorted(result.items()):
            print(f"\n{scenario}:")
            print(f"  Goodput:  {s['mean_goodput_mbps']:.3f} ± {s['std_goodput_mbps']:.3f} Mbps")
            print(f"  RTT:      {s['mean_rtt_ms']:.3f} ± {s['std_rtt_ms']:.3f} ms")
            print(f"  Mark:     {s['mean_mark_prob']:.2f} ± {s['std_mark_prob']:.2f}%")
            print(f"  Loss:     {s['mean_loss_prob']:.2f} ± {s['std_loss_prob']:.2f}%")
            if "target_rate_mbps" in s:
                print(f"  [Call metrics] Target: {s['target_rate_mbps']} Mbps")
                print(f"  Mean achieved rate fraction: {s['mean_achieved_rate_fraction_pct']:.2f}%")
                print(f"  Mean p95 RTT: {s['mean_p95_rtt_ms']:.2f} ms")
                print(f"  Bad interval fraction: {s['bad_interval_fraction_pct']:.2f}%")
            print(f"  Flows:    {s['n_flows']}  Trials: {s['n_trials']}")
            if "trials" in s:
                print("  Per trial:")
                for t in s["trials"]:
                    call_extras = ""
                    if "mean_achieved_rate_fraction_pct" in t:
                        call_extras = f", achieved_rate_frac {t['mean_achieved_rate_fraction_pct']:.2f}%, p95_rtt {t['mean_p95_rtt_ms']:.2f} ms"
                    print(f"    Trial {t['trial']} ({t['n_flows']} flows): goodput {t['mean_goodput_mbps']:.3f} Mbps, RTT {t['mean_rtt_ms']:.3f} ms{call_extras}")
                    if not args.no_per_flow:
                        for fl in t["flows"]:
                            print(f"      port {fl['port']}: {fl['rcvd_rate_mbps']:.3f} Mbps, {fl['rtt_ms']:.3f} ms")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        if not args.quiet:
            print(f"\nWrote {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
