"""Load the fluid-model results (Figures 4 and 5): p'(t) of five Classic flows alone through the PI2-extended fluid
model, 100 Mbps, 8-BDP buffer, base RTT 10/30/50 ms, PI2 target 5-75 ms. Each run lasts 40 s and is sampled every 1 ms
(see fluid-model/). BBRv2 has three seeds, as its initial ProbeBW phases are random; CUBIC and BBRv1 are deterministic.
Means are taken over 20-40 s, after the initial transient, and averaged over the seeds.
"""
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "Experiment_Data" / "fluid-model"
SEEDS = {"cubic": (1,), "bbr1": (1,), "bbr2": (1, 2, 3)}
T0, T1 = 20.0, 40.0


def trace(cc, rtt, target, seed, variant=None):
    """Time (s) and p' of one run; variant names a sensitivity run, e.g. 'cwndgain3' (files in sensitivity/)."""
    name = f"{cc}_100mbps_rtt{rtt}_target{target}{'_' + variant if variant else ''}_seed{seed}.csv.xz"
    path = DATA / name if (DATA / name).exists() else DATA / "sensitivity" / name
    d = pd.read_csv(path, float_precision="round_trip")
    return d.time_ms.to_numpy() / 1000, d.pprime.to_numpy()


def window_mean(t, p):
    return p[(t >= T0) & (t < T1)].mean()


def mean_pprime(cc, rtt, target):
    """Mean p' over 20-40 s, averaged over the seeds."""
    return float(np.mean([window_mean(*trace(cc, rtt, target, s)) for s in SEEDS[cc]]))
