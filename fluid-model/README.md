# BBRv1/BBRv2 Fluid Model with a PI2 Bottleneck

This is the fluid model of Section V. It is the BBRv1/BBRv2 fluid model of Scherrer et al., *Model-Based Insights on the Performance, Fairness, and Stability of BBR* (ACM IMC 2022; [original repository](https://github.com/simonschdev/imc22-bbr-fluid-model), commit `9ad01fa`). We added a PI2 bottleneck to it. The BBRv1, BBRv2 and CUBIC sender models are unchanged, apart from two optional parameters for the sensitivity runs.

## What we changed

- **PI2 bottleneck** (`qdisc: PI2`, in `fluid_model/compute_trace.py`). Every update interval, the base probability p' is updated from the queueing delay q/C and its change since the last update, then clipped to [0, 1]. Classic packets are dropped with probability (p')². The parameters are `pi2_target` (ms), `pi2_tupdate` (ms), `pi2_alpha` and `pi2_beta`. Their defaults match Linux DualPI2: 15 ms target, 16 ms update interval, α = 0.16 Hz and β = 3.2 Hz.
- **`seed`** (optional parameter). It fixes the only random draws in the model, BBRv2's initial ProbeBW phase offsets.
- **Sensitivity parameters** for Section V-B: `bbr_cwnd_gain`, the BBRv1/BBRv2 ProbeBW cwnd gain (default 2), and `bbr2_loss_threshold`, the drop probability above which BBRv2 reacts to loss (default 0.02). The defaults are the original constants.
- **Trace output.** The trace JSON now also contains p' (`pprime`, in %, like `p`), `pi2_target`, `seed`, `stp` and `t_index`.
- **`run_model.py`.** Trace plotting is now opt-in with `--plot-trace`, because it needs LaTeX. Each run's state is also freed before the next one starts.

The Mininet experiment suite and the plotting scripts of the original repository are not included.

## Running the Model

Python 3 with `numpy`, `PyYAML` and `matplotlib` (`pip install -r ../requirements.txt`).

```bash
cd fluid-model
python run_model.py -c configs/bbr1_100mbps_rtt30_target15.yaml   # one configuration
JOBS=4 ./run_all.sh                                                # every configuration, then extract_pprime.py
```

Each configuration in [`configs/`](configs/) has five Classic flows alone through the PI2 bottleneck: 100 Mbps, 8-BDP buffer, 40 s with a 10 µs step. The file names give the congestion control (`cubic`, `bbr1` or `bbr2`), the base RTT (10, 30 or 50 ms) and the PI2 target (5, 15, 25, 50 or 75 ms). BBRv2 configurations run seeds 1-3, one after another. [`make_configs.py`](make_configs.py) regenerates the configurations. It also shows how `link_latency` and `switch_buffer` give the exact base RTT and buffer size. To get other scenarios (for example 500 Mbps), change the constants at its top.

[`configs/sensitivity/`](configs/sensitivity/) holds the sensitivity runs of Section V-B (seed 1). These are 9 runs with cwnd gain 3 (BBRv1 and BBRv2) and 2 runs with a BBRv2 loss threshold of 0.5% (`..._cwndgain3`, `..._lossthreshold0.005`), plus one unchanged configuration outside the main grid that they are compared with. `run_all.sh` runs them as well. `python sensitivity.py` in `../plotting-scripts` prints the comparison.

Approximate cost of one 40-s run:

| Congestion control | Time per seed | Peak memory | Trace size per seed |
|---|---|---|---|
| CUBIC | 1.5 min | 5 GB | 30 MB |
| BBRv1 | 4.5 min | 10 GB | 60 MB |
| BBRv2 | 7 min | 14 GB | 80 MB |

A run writes its trace to `results/<name>/fluid_model/traces/` and its summary statistics to `results/<name>/fluid_model/`. [`extract_pprime.py`](extract_pprime.py) then writes p'(t) of each run, at 1-ms samples, to `../Experiment_Data/fluid-model/<name>_seed<k>.csv.xz`, with the sensitivity runs in its `sensitivity/` subfolder. The plotting scripts read these files.

## Licence

The original code is by Simon Scherrer and James Dermelj, Copyright 2023 ETH Zurich. It is licensed under the Apache License, Version 2.0 ([`LICENSE`](LICENSE)), as are our modifications. Modified files are marked at the top.
