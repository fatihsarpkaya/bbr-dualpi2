"""Load the main results (Figures 2 and 3): Prague throughput share and PI2 base probability p' per configuration.

Each 180 s run is measured over its last 60 s, ending at the last sample of the senders' ss traces. Prague throughput
is the increase of bytes_acked of the five Prague flows; p' is the mean of the router's prob_raw samples. Values are
averaged over the three trials. Raw logs are xz-compressed and read directly.
"""
import json
import lzma
import re
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "Experiment_Data" / "main-results"
L4S, CLASSIC, ROUTER = (DATA / f"dualpi2_sweep_{h}_180s" for h in ("tx_L4S", "tx_legacy", "router"))
NAME = re.compile(r"^prague_(?P<cc>[a-z0-9]+)_[\d.]+_(?P<btl>\d+)_(?P<rtt>\d+)_DualPI2_(?P<target>\d+)_.*_(?P<trial>\d+)"
                  r"-result\.json\.xz$")
BYTES_ACKED = re.compile(r"\bbytes_acked:(\d+)")
WINDOW = 60.0


def read_ss(path, ports):
    """Start time and {local port: array of (time, bytes_acked)} for the iperf3 data connections."""
    per, port, t_first = {p: [] for p in ports}, None, None
    with lzma.open(path, "rt") as fh:
        for line in fh:
            p = line.split()
            if not p:
                continue
            if t_first is None:
                t_first = float(p[0])
            if len(p) > 5 and p[1] == "tcp":
                port = int(p[5].rsplit(":", 1)[1])
            elif port in per:
                m = BYTES_ACKED.search(line)
                if m:
                    per[port].append((float(p[0]), float(m.group(1))))
    return t_first, {k: np.array(v).reshape(-1, 2) for k, v in per.items()}


def one_run(name):
    m = NAME.match(name)
    tail = name[len(f"prague_{m['cc']}_"):-len("-result.json.xz")]
    ports = lambda f: [c["local_port"] for c in json.load(lzma.open(f, "rt"))["start"]["connected"]]  # noqa: E731
    t0, prague = read_ss(L4S / f"prague_{m['cc']}_{tail}-ss.txt.xz", ports(L4S / name))
    _, classic = read_ss(CLASSIC / f"{m['cc']}_prague_{tail}-ss.txt.xz",
                         ports(CLASSIC / f"{m['cc']}_prague_{tail}-result.json.xz"))
    end = min(min(a[-1, 0] for a in flows.values() if len(a)) for flows in (prague, classic))
    end = min(end, t0 + 180)
    lo = end - WINDOW
    rate = 0.0
    for a in prague.values():
        w = a[(a[:, 0] >= lo) & (a[:, 0] <= end)]
        rate += (w[-1, 1] - w[0, 1]) * 8 / (w[-1, 0] - w[0, 0])
    router = pd.read_csv(ROUTER / f"prague_{m['cc']}_{tail}_dualpi2.log.xz", sep=r"\s+")
    router = router.apply(pd.to_numeric, errors="coerce").dropna()
    p = router.prob_raw[(router.timestamp >= lo) & (router.timestamp <= end)].mean()
    btl = int(m["btl"])
    return {"cc": m["cc"], "btl_mbps": btl, "rtt_ms": int(m["rtt"]), "target_ms": int(m["target"]),
            "trial": int(m["trial"]), "prague_share": rate / (btl * 1e6), "p": p}


def load():
    """One row per configuration: cc, btl_mbps, rtt_ms, target_ms, prague_share, p (means over trials)."""
    names = sorted(f.name for f in L4S.glob("prague_*-result.json.xz"))
    if len(names) != 270:
        raise SystemExit(f"expected 270 runs, found {len(names)}")
    with ProcessPoolExecutor() as ex:
        runs = pd.DataFrame(list(ex.map(one_run, names, chunksize=2)))
    # The router log of bbr2 / 100 Mbps / RTT 30 ms / target 5 ms / trial 700 ends at 22.6 s, so that configuration's
    # p' is the mean of the other two trials.
    return runs.groupby(["cc", "btl_mbps", "rtt_ms", "target_ms"])[["prague_share", "p"]].mean().reset_index()
