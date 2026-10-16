# When Coupling Backfires: BBR-Induced L4S Degradation under DualPI2

This repository holds the data and scripts for the paper *When Coupling Backfires: Measuring and Modeling
BBR-Induced L4S Degradation under DualPI2*, by Fatih Berkay Sarpkaya, Fraida Fund and Shivendra Panwar (NYU Tandon
School of Engineering).

DualPI2 isolates L4S traffic in its own queue but couples the Classic queue's congestion signal into it. The
coupling assumes Reno-like Classic traffic. On the FABRIC testbed, we run TCP Prague against CUBIC, BBRv1 and BBRv2
through a Linux DualPI2 bottleneck. We find that BBR can drive the PI2 base probability p′ far above CUBIC levels.
Through coupling, that nearly starves Prague, even though L4S queueing delay stays below about 1 ms. A PI2 extension
of an existing BBRv1/BBRv2 fluid model explains the p′ operating regimes.

## Contents

| Folder | Contents | Paper |
|---|---|---|
| [`linux-experiments/`](linux-experiments/) | Testbed sweep: 5 Prague flows against 5 CUBIC, BBRv1 or BBRv2 flows, across capacity, base RTT and PI2 target, plus Classic-only runs. Raw logs, summary CSVs and figure scripts. | Figs. 2 and 3; the measured data in Figs. 4 and 5 |
| `fluid-model/` | The PI2-extended BBR fluid model (to be added) | Figs. 4 and 5 |

## Quick start

These commands need Python 3.9 or newer:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd linux-experiments/scripts
python summarize_coexistence.py   # raw logs -> results/*.csv
python plot_fig2.py               # Fig. 2 -> figures/fig2_prague_share.{pdf,png}
python plot_fig3.py               # Fig. 3 -> figures/fig3_pprime_vs_prague_share.{pdf,png}
```

The summary CSVs and figures are committed, so you can run the plotting scripts without the first step.
[`linux-experiments/README.md`](linux-experiments/README.md) describes the following:
- the testbed and its configuration;
- the file formats and naming scheme;
- the measurement window;
- the known data issues.
