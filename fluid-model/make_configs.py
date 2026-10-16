#!/usr/bin/env python3
"""Write the fluid-model configurations of the paper (Figures 4 and 5) to configs/.

Five Classic flows (CUBIC, BBRv1 or BBRv2) alone through a PI2 bottleneck, as in the Classic-only Linux runs:
100 Mbps, base RTT 10, 30 or 50 ms, 8-BDP buffer, PI2 target 5, 15, 25, 50 or 75 ms, 40 s with a 10 us step.
BBRv2 runs with seeds 1-3, since its initial ProbeBW phases are random; CUBIC and BBRv1 are deterministic.
The PI2 update interval and gains keep their Linux defaults (fluid_model/helpers.py).

configs/sensitivity/ holds the sensitivity runs of Section V-B (seed 1): the same scenarios with the BBRv1/BBRv2 cwnd
gain raised from 2 to 3, or the BBRv2 loss threshold lowered from 2 % to 0.5 %, and one unchanged configuration they
are compared with that is not in the main grid.
"""
import math
from pathlib import Path

MSS = 1514  # bytes, as in fluid_model/helpers.py
CCS = {'cubic': ('CUBIC', 'CUBIC'), 'bbr1': ('BBR', 'BBRv1'), 'bbr2': ('BBR2', 'BBRv2')}
SEEDS = {'cubic': [1], 'bbr1': [1], 'bbr2': [1, 2, 3]}
CAPACITY, N_BDP, FLOWS, DURATION = 100, 8, 5, 40   # Mbps, BDPs, flows, s
RTTS, TARGETS = (10, 30, 50), (5, 15, 25, 50, 75)  # ms
SOURCE_LATENCY = 0.1                               # ms
OUT = Path(__file__).resolve().parent / 'configs'

VARIANTS = {'cwndgain3': ('bbr_cwnd_gain', 3, 2, 'cwnd gain 3 instead of 2'),
            'lossthreshold0.005': ('bbr2_loss_threshold', 0.005, 0.02, 'loss threshold 0.5 % instead of 2 %')}
SENSITIVITY = ([('bbr1', rtt, thr, 'cwndgain3') for rtt, thr in
                ((10, 15), (10, 25), (10, 50), (30, 50), (30, 75), (50, 75), (50, 150))]
               + [('bbr2', 30, thr, 'cwndgain3') for thr in (50, 75)]
               + [('bbr2', 30, thr, 'lossthreshold0.005') for thr in (5, 15)]
               + [('bbr1', 50, 150, None)])  # unchanged, for comparison

TEMPLATE = """\
# {n} {label} flows alone through a PI2 bottleneck: {cap} Mbps, {rtt} ms base RTT, {nbdp}-BDP buffer, PI2 target {thr} ms{note}.
name: {name}

common_parameters:
  send_duration: {dur}  # s
  truncate_front: 0  # s
  truncate_back: 0  # s

varying_parameters:
  senders: [{n}]
  link_capacity: [{cap}]  # Mbps
  switch_buffer: [{sb!r}]  # in BDPs of link_latency: {buf} packets = {nbdp} BDPs of the {rtt} ms base RTT
  cc_combination:
    - [{cc}]
  link_latency: [{ll!r}]  # ms; base RTT = 2 * (link_latency + source latency)
  source_latency_range:
    - [{sl}, {sl}]  # ms
  qdisc: [PI2]
  pi2_target: [{thr_f!r}]  # ms
  seed: {seeds}
{extra}
model_parameters:
  computation_parameters:
    stp: 0.01  # ms
"""


def scenario(rtt):
    """Link latency (ms), switch_buffer and buffer (packets) for an exact base RTT and an n-BDP buffer.

    The model's buffer is int(switch_buffer * BDP of link_latency) packets (helpers.get_environment), so
    switch_buffer is chosen to give round(N_BDP * RTT * C) packets.
    """
    link_latency = rtt / 2 - SOURCE_LATENCY
    pkts_per_ms = CAPACITY * 1e6 / (MSS * 8 * 1000)
    link_bdp = math.ceil((CAPACITY / 8 * 1e6 * link_latency / 1000) / MSS)
    buf = int(round(N_BDP * rtt * pkts_per_ms))
    return link_latency, (buf + 0.5) / link_bdp, buf


def write(out, cc, rtt, thr, seeds, variant=None):
    model_cc, label = CCS[cc]
    ll, sb, buf = scenario(rtt)
    name = '%s_%dmbps_rtt%d_target%d' % (cc, CAPACITY, rtt, thr) + ('_' + variant if variant else '')
    note, extra = '', ''
    if variant:
        key, value, original, text = VARIANTS[variant]
        note, extra = '; ' + text, '  %s: [%r]  # original: %r\n' % (key, value, original)
    (out / (name + '.yaml')).write_text(TEMPLATE.format(
        n=FLOWS, label=label, cap=CAPACITY, rtt=rtt, nbdp=N_BDP, thr=thr, note=note, name=name, dur=DURATION,
        sb=sb, buf=buf, cc=model_cc, ll=ll, sl=SOURCE_LATENCY, thr_f=float(thr), seeds=seeds, extra=extra))


def main():
    (OUT / 'sensitivity').mkdir(parents=True, exist_ok=True)
    for cc in CCS:
        for rtt in RTTS:
            for thr in TARGETS:
                write(OUT, cc, rtt, thr, SEEDS[cc])
    for cc, rtt, thr, variant in SENSITIVITY:
        write(OUT / 'sensitivity', cc, rtt, thr, [1], variant)
    print('wrote %d configurations to %s' % (len(list(OUT.rglob('*.yaml'))), OUT))


if __name__ == '__main__':
    main()
