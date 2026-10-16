"""Summarize the coexistence sweep: 270 runs of five Prague flows against five CUBIC, BBRv1 or BBRv2 flows (180 s).

Every quantity is measured over the last 60 s of a run:
  t0      = first line of the Prague sender's ss trace (iperf3 start)
  W_end   = min(last ss sample of the Prague sender, last ss sample of the Classic sender, t0 + 180 s); the ss
            loggers stop ~2 s before the transfer ends, so W_end ~ t0 + 178 s
  window  = [W_end - 60 s, W_end]
Throughput = increase of bytes_acked (ss) over the window, summed over a sender's five data connections, divided by
the time between the first and last sample: what the receivers acknowledged. Share = Prague throughput / capacity C.
Router quantities use the router log samples inside the same window: p' is the mean of `prob_raw`; marking fractions
are differences of the cumulative counters between the first and last sample.
Cross-check: iperf3's sender-side bytes over its last 60 one-second intervals.

Writes
  results/coexistence_runs.csv   one row per run
  results/coexistence_cells.csv  one row per configuration: means over its trials (missing values ignored)
and prints the integrity checks. Usage: python summarize_coexistence.py
"""
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from dataset import COEX_CLASSIC, COEX_L4S, COEX_ROUTER, parse_name, read_iperf, read_router_log, read_ss

OUT = Path(__file__).resolve().parent.parent / "results"
CCS, BTLS, RTTS, TARGETS, TRIALS = ("cubic", "bbr2", "bbr1"), (100, 500), (10, 30, 50), (5, 15, 25, 50, 75), \
    (700, 701, 702)
DURATION, WINDOW = 180.0, 60.0
KEY = ["cc", "btl_mbps", "rtt_ms", "target_ms"]


def window_rate(series, lo, hi):
    """Aggregate rate (bit/s) of the flows over [lo, hi], the largest gap between samples inside it, and the number
    of flows with at least two samples in it."""
    rate, gap, n_ok = 0.0, 0.0, 0
    for a in series.values():
        w = a[(a[:, 0] >= lo) & (a[:, 0] <= hi)]
        if len(w) < 2:
            continue
        n_ok += 1
        rate += (w[-1, 1] - w[0, 1]) * 8 / (w[-1, 0] - w[0, 0])
        gap = max(gap, np.diff(w[:, 0]).max(), w[0, 0] - lo, hi - w[-1, 0])
    return rate, gap, n_ok


def one(meta):
    cc, stem = meta["cc"], meta["stem"]
    tail = stem.split("_", 2)[2]  # the part after "prague_{cc}_"
    jl = read_iperf(COEX_L4S / f"prague_{cc}_{tail}-result.json.xz")
    jc = read_iperf(COEX_CLASSIC / f"{cc}_prague_{tail}-result.json.xz")
    t0, sl = read_ss(COEX_L4S / f"prague_{cc}_{tail}-ss.txt.xz", [c["local_port"] for c in jl["start"]["connected"]])
    _, sc = read_ss(COEX_CLASSIC / f"{cc}_prague_{tail}-ss.txt.xz", [c["local_port"] for c in jc["start"]["connected"]])
    end_l = min(a[-1, 0] for a in sl.values() if len(a))
    end_c = min(a[-1, 0] for a in sc.values() if len(a))
    w_end = min(end_l, end_c, t0 + DURATION)
    w_lo = w_end - WINDOW
    r_l, gap_l, n_l = window_rate(sl, w_lo, w_end)
    r_c, gap_c, n_c = window_rate(sc, w_lo, w_end)
    # iperf3 sender-side cross-check: the last 60 one-second intervals of the Prague client
    iv = [i["sum"] for i in jl["intervals"] if i["sum"]["start"] >= jl["start"]["test_start"]["duration"] - WINDOW]
    r_snd = sum(i["bytes"] for i in iv) * 8 / sum(i["seconds"] for i in iv)

    rt = read_router_log(COEX_ROUTER / f"prague_{cc}_{tail}_dualpi2.log.xz")
    w = rt[(rt.timestamp >= w_lo) & (rt.timestamp <= w_end)]
    if len(w) >= 2:
        d = w.iloc[-1] - w.iloc[0]
        ce_frac = d.ecn_mark / d.pkts_in_l if d.pkts_in_l > 0 else np.nan
        step_share = d.step_mark / d.ecn_mark if d.ecn_mark > 0 else np.nan
    else:
        ce_frac = step_share = np.nan
    btl = meta["btl_mbps"]
    return {**{k: meta[k] for k in (*KEY, "trial")},
            "window_start_s": w_lo - t0, "window_end_s": w_end - t0,
            "prague_mbps": r_l / 1e6, "classic_mbps": r_c / 1e6, "prague_share": r_l / (btl * 1e6),
            "utilization": (r_l + r_c) / (btl * 1e6), "prague_sender_mbps": r_snd / 1e6,
            "p_mean": w.prob_raw.mean(), "qdelay_c_mean_ms": w.delay_c_us.mean() / 1e3,
            "qdelay_l_mean_ms": w.delay_l_us.mean() / 1e3, "qdelay_l_p95_ms": w.delay_l_us.quantile(0.95) / 1e3,
            "l4s_ce_frac": ce_frac, "step_share_of_ce": step_share, "router_samples": len(w),
            # integrity-check fields
            "duration_prague_s": jl["start"]["test_start"]["duration"],
            "duration_classic_s": jc["start"]["test_start"]["duration"],
            "streams_prague": len(jl["end"]["streams"]), "streams_classic": len(jc["end"]["streams"]),
            "flows_in_window_prague": n_l, "flows_in_window_classic": n_c,
            "iperf_error": jl.get("error") or jc.get("error") or "",
            "max_gap_prague_s": gap_l, "max_gap_classic_s": gap_c,
            "router_start_s": rt.timestamp.iloc[0] - t0, "router_end_s": rt.timestamp.iloc[-1] - t0}


def main():
    metas = [m for f in sorted(COEX_L4S.glob("*-result.json.xz")) if (m := parse_name(f.name))]
    if len(metas) != len(list(COEX_L4S.glob("*-result.json.xz"))):
        raise SystemExit("a file name in data/dualpi2_sweep_tx_L4S_180s does not follow the naming scheme")
    expected = {(cc, b, r, t, k) for cc in CCS for b in BTLS for r in RTTS for t in TARGETS for k in TRIALS}
    found = {(m["cc"], m["btl_mbps"], m["rtt_ms"], m["target_ms"], m["trial"]) for m in metas}
    print(f"runs found: {len(metas)}; expected {len(expected)} "
          f"({len(CCS)} CCs x {len(BTLS)} capacities x {len(RTTS)} RTTs x {len(TARGETS)} targets x {len(TRIALS)} trials); "
          f"missing {sorted(expected - found) or 'none'}; unexpected {sorted(found - expected) or 'none'}; "
          f"buffer (BDP) {sorted({m['n_bdp'] for m in metas})}")

    with ProcessPoolExecutor() as ex:
        d = pd.DataFrame(list(ex.map(one, metas, chunksize=2)))
    d = d.sort_values([*KEY, "trial"]).reset_index(drop=True)

    q = lambda s, f="{:.2f}": f"{f.format(s.min())} / {f.format(s.median())} / {f.format(s.max())}"  # noqa: E731
    print("\nmin / median / max over all runs:")
    print(f"  window (s after t0): start {q(d.window_start_s)}, end {q(d.window_end_s)}")
    print(f"  largest ss sample gap in window (s): Prague {q(d.max_gap_prague_s, '{:.3f}')}, "
          f"Classic {q(d.max_gap_classic_s, '{:.3f}')}")
    print(f"  router samples in window: {q(d.router_samples, '{:.0f}')}")
    print(f"  link utilization in window: {q(d.utilization, '{:.3f}')}")
    bad = d[(d.duration_prague_s != DURATION) | (d.duration_classic_s != DURATION) | (d.streams_prague != 5) |
            (d.streams_classic != 5) | (d.flows_in_window_prague != 5) | (d.flows_in_window_classic != 5) |
            (d.iperf_error != "") | (d.window_end_s < 177) | (d.max_gap_prague_s > 1) | (d.max_gap_classic_s > 1) |
            (d.router_start_s > d.window_start_s) | (d.router_end_s < d.window_end_s)]
    print(f"runs failing a check: {len(bad)}")
    for r in bad.itertuples():
        print(f"  {r.cc} {r.btl_mbps} Mbps, RTT {r.rtt_ms} ms, target {r.target_ms} ms, trial {r.trial}: "
              f"router log covers {r.router_start_s:.1f}..{r.router_end_s:.1f} s, window "
              f"{r.window_start_s:.1f}..{r.window_end_s:.1f} s, iperf3 error '{r.iperf_error}'")
    dev = (d.prague_sender_mbps - d.prague_mbps) / d.btl_mbps
    print(f"cross-check, iperf3 sender-side minus receiver-acknowledged Prague throughput, in units of C: "
          f"median {dev.median():+.4f}, range {dev.min():+.4f} .. {dev.max():+.4f}")

    OUT.mkdir(exist_ok=True)
    d.to_csv(OUT / "coexistence_runs.csv", index=False)
    agg = {"trials": ("trial", "count"), "p_trials": ("p_mean", "count"),
           "prague_share": ("prague_share", "mean"), "prague_share_sd": ("prague_share", "std"),
           "prague_share_min": ("prague_share", "min"), "prague_share_max": ("prague_share", "max")}
    agg.update({c: (c, "mean") for c in ("prague_mbps", "classic_mbps", "utilization", "p_mean", "qdelay_c_mean_ms",
                                         "qdelay_l_mean_ms", "qdelay_l_p95_ms", "l4s_ce_frac", "step_share_of_ce")})
    cells = d.groupby(KEY).agg(**agg).reset_index()
    cells.to_csv(OUT / "coexistence_cells.csv", index=False)
    print(f"\nconfigurations: {len(cells)}; trials per configuration {sorted(int(t) for t in cells.trials.unique())}; "
          f"largest trial range of the Prague share {(cells.prague_share_max - cells.prague_share_min).max():.3f}")
    for r in cells[cells.p_trials < cells.trials].itertuples():
        print(f"note: p' and router quantities for {r.cc} {r.btl_mbps} Mbps, RTT {r.rtt_ms} ms, target "
              f"{r.target_ms} ms average {r.p_trials} of {r.trials} trials")
    print(f"wrote {OUT.name}/coexistence_runs.csv and {OUT.name}/coexistence_cells.csv")


if __name__ == "__main__":
    main()
