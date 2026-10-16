"""Load the Classic-only results (Figure 4): DualPI2 with five Classic flows and no Prague flows, 100 Mbps, 8-BDP
buffer, base RTT 10/30/50 ms, PI2 target 5-75 ms.

180-s runs (BBRv1 and BBRv2, trials 800-802) are measured over their last 60 s as in main_results.py, with the Classic
sender in place of the Prague sender: the window ends at the earliest last sample of the five flows' ss traces (at most
180 s after the trace starts). 60-s runs (CUBIC, trials 900-902) give the CUBIC trace of Figure 4a, timed from the
start of the Classic iperf3 transfer. p' is the router's prob_raw. Raw logs are xz-compressed and read directly.
"""
import json
import lzma
from pathlib import Path

import numpy as np
import pandas as pd

from main_results import WINDOW, read_ss

DATA = Path(__file__).resolve().parent.parent / "Experiment_Data" / "classic-alone"
SENDER_180, ROUTER_180 = DATA / "pi2_sweep_classic_alone_tx_legacy_180s", DATA / "pi2_sweep_classic_alone_router_180s"
SENDER_60, ROUTER_60 = DATA / "pi2_sweep_classic_alone_tx_legacy", DATA / "pi2_sweep_classic_alone_router"
TRIALS_180, TRIALS_60 = (800, 801, 802), (900, 901, 902)


def tail(rtt, target, trial):
    return f"8.0_100_{rtt}_pi2_{target}_0_3_0_5_5_0_0_{trial}"


def read_router(path):
    """Timestamps and p' of a router log."""
    r = pd.read_csv(path, sep=r"\s+", float_precision="round_trip").apply(pd.to_numeric, errors="coerce").dropna()
    return r.timestamp.to_numpy(), r.prob_raw.to_numpy()


def run_180s(cc, rtt, target, trial):
    """Start t0 and end of the last-60-s window (both absolute), router timestamps and p' of a 180-s run."""
    t = tail(rtt, target, trial)
    ports = [c["local_port"] for c in
             json.load(lzma.open(SENDER_180 / f"{cc}_prague_{t}-result.json.xz", "rt"))["start"]["connected"]]
    t0, flows = read_ss(SENDER_180 / f"{cc}_prague_{t}-ss.txt.xz", ports)
    end = min(min(a[-1, 0] for a in flows.values() if len(a)), t0 + 180)
    return (t0, end, *read_router(ROUTER_180 / f"prague_{cc}_{t}_dualpi2.log.xz"))


def trace_180s(cc, rtt, target, trial):
    """p'(t) of a 180-s run: time from the start of its ss trace (s), p', and the end of the run's window (s)."""
    t0, end, ts, p = run_180s(cc, rtt, target, trial)
    return ts - t0, p, end - t0


def trace_60s(cc, rtt, target, trial):
    """p'(t) of a 60-s run: time from the start of the Classic iperf3 transfer (s) and p'."""
    t = tail(rtt, target, trial)
    t0 = json.load(lzma.open(SENDER_60 / f"{cc}_prague_{t}-result.json.xz", "rt"))["start"]["timestamp"]["timesecs"]
    ts, p = read_router(ROUTER_60 / f"prague_{cc}_{t}_dualpi2.log.xz")
    return ts - t0, p


def mean_pprime(cc, rtt, target):
    """Mean p' over the last 60 s of the three 180-s runs."""
    v = []
    for trial in TRIALS_180:
        _, end, ts, p = run_180s(cc, rtt, target, trial)
        v.append(p[(ts >= end - WINDOW) & (ts <= end)].mean())
    return float(np.mean(v))
