"""Readers for the Linux experiment data in ../data.

Every data file is xz-compressed (`<original name>.xz`); these readers open the compressed files directly.
The data format is described in ../README.md.
"""
import json
import lzma
import re
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"

# Coexistence sweep (Prague + Classic, 180 s, trials 700-702)
COEX_L4S, COEX_CLASSIC, COEX_ROUTER = (DATA / f"dualpi2_sweep_{h}_180s" for h in ("tx_L4S", "tx_legacy", "router"))
# Classic-alone sweeps: BBRv1/BBRv2 180 s (trials 800-802), CUBIC 60 s (trials 900-902)
ALONE_CLASSIC_180, ALONE_ROUTER_180 = (DATA / f"pi2_sweep_classic_alone_{h}_180s" for h in ("tx_legacy", "router"))
ALONE_CLASSIC_60, ALONE_ROUTER_60 = (DATA / f"pi2_sweep_classic_alone_{h}" for h in ("tx_legacy", "router"))

# {cc_a}_{cc_b}_{n_bdp}_{btl}_{rtt}_{aqm}_{target}_{f0}_{ecn_l4s}_{ecn_classic}_{n_l4s}_{n_classic}_{f1}_{f2}_{trial}
NAME = re.compile(r"^(?P<cc_a>[a-z0-9]+)_(?P<cc_b>[a-z0-9]+)_(?P<n_bdp>[\d.]+)_(?P<btl>\d+)_(?P<rtt>\d+)"
                  r"_(?P<aqm>DualPI2|pi2)_(?P<target>\d+)_\d+_(?P<ecn_l4s>\d+)_(?P<ecn_classic>\d+)"
                  r"_(?P<n_l4s>\d+)_(?P<n_classic>\d+)_\d+_\d+_(?P<trial>\d+)"
                  r"(?P<kind>-result\.json|-ss\.txt|_dualpi2\.log)(?:\.xz)?$")
UINT32_MAX = 4294967295  # sentinel the router occasionally reports as a queue delay


def parse_name(name):
    """Configuration encoded in a data file name, or None if the name does not follow the scheme."""
    m = NAME.match(name)
    if not m:
        return None
    classic = m["cc_b"] if m["cc_a"] == "prague" else m["cc_a"]
    return {"cc": classic, "n_bdp": float(m["n_bdp"]), "btl_mbps": int(m["btl"]), "rtt_ms": int(m["rtt"]),
            "target_ms": int(m["target"]), "trial": int(m["trial"]), "aqm": m["aqm"], "kind": m["kind"],
            "stem": name[:m.start("kind")]}


def read_iperf(path):
    """iperf3 --json output of one sender."""
    with lzma.open(path, "rt") as fh:
        return json.load(fh)


def read_router_log(path):
    """DualPI2 statistics polled on the router, one row per poll (~0.1 s).

    Rows with an unparsable field (e.g. a truncated last line) are dropped. Queue-delay readings equal to 2^32 - 1
    are not delays but a race in the kernel's stats dump; they are set to NaN."""
    r = pd.read_csv(path, sep=r"\s+").apply(pd.to_numeric, errors="coerce").dropna()
    for col in ("delay_c_us", "delay_l_us"):
        r[col] = r[col].where(r[col] != UINT32_MAX)
    return r


BYTES_ACKED = re.compile(r"\bbytes_acked:(\d+)")


def read_ss(path, ports):
    """Timestamped `ss -ti` samples of one sender.

    Returns the time of the first line (iperf3 start) and {local port: array of (t, bytes_acked)} for the given
    local ports (the iperf3 data connections; the control connection is ignored)."""
    per, port, t_first = {p: [] for p in ports}, None, None
    with lzma.open(path, "rt") as fh:
        for line in fh:
            p = line.split()
            if not p:
                continue
            if t_first is None:
                t_first = float(p[0])
            if len(p) > 5 and p[1] == "tcp":  # "<t> tcp ESTAB <recv-q> <send-q> <local ip:port> <peer ip:port> ..."
                port = int(p[5].rsplit(":", 1)[1])
            elif port in per:  # "<t> <tab> <tcp_info of the socket above>"
                m = BYTES_ACKED.search(line)
                if m:
                    per[port].append((float(p[0]), float(m.group(1))))
    return t_first, {k: np.array(v).reshape(-1, 2) for k, v in per.items()}
