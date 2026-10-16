# When Coupling Backfires: BBR-Induced L4S Degradation under DualPI2

This repository contains the artifacts for the paper **"When Coupling Backfires: BBR-Induced L4S Degradation under DualPI2."**

## Abstract

Low Latency, Low Loss, Scalable Throughput (L4S) uses DualPI2 to separate L4S and Classic traffic into two queues while coupling their congestion signals. However, this coupling is designed for Reno-like Classic congestion controls, while widely deployed BBR behaves differently. Prior studies have observed severe TCP Prague throughput degradation with BBR under DualPI2, but the underlying mechanism remains insufficiently explained. Through controlled testbed experiments and an extension of an existing BBRv1/BBRv2 fluid model with PI2, we show that BBR can drive the PI2 base probability p′ far above CUBIC levels, producing strong coupled marking that can nearly starve Prague despite low L4S queueing delay. The model explains BBRv1's persistent high-p′ regime, BBRv2's lower, oscillating p′, and their dependence on the PI2 target relative to RTT. Our findings highlight the need for coupling mechanisms robust to heterogeneous Classic congestion controls.

This repository includes:

- [`experiment_fabric_linux.ipynb`](experiment_fabric_linux.ipynb), the FABRIC experiment notebook.
- [`utils/`](utils/), containing the DualPI2 logging script run on the router.
- [`Experiment_Data/`](Experiment_Data/), containing the motivation (Figure 1), main (Figures 2 and 3), and Classic-only (Figure 4) results.
- [`plotting-scripts/`](plotting-scripts/), containing the scripts that generate the figures.
- [`Plots/`](Plots/), containing the paper figures in PDF format.

## Reproducing the Figures

Use the provided experiment data to regenerate the paper figures:

```bash
pip install -r requirements.txt
cd plotting-scripts
python plot_fig1.py
python plot_fig2.py
python plot_fig3.py
```

The figures are written to `Plots/`. The raw logs in `Experiment_Data/` are xz-compressed; the scripts read them directly.

## Running the Experiments on FABRIC

You need a [FABRIC](https://fabric-testbed.net/) account, an active project with sufficient quota, configured SSH keys, and access to the FABRIC JupyterHub environment.

Open a terminal in FABRIC JupyterHub and run:

```bash
git clone https://github.com/fatihsarpkaya/bbr-dualpi2.git
cd bbr-dualpi2
```

Open `experiment_fabric_linux.ipynb` in JupyterLab and follow it section by section. Do not use **Run All**, because slice creation, kernel installation, node reboots, and experiment execution must finish in order. Before running the experiments, upload `utils/dualpi2_v2.sh` to the router's home directory; the notebook runs it there to log the DualPI2 statistics.

Delete the FABRIC slice after completing the experiments to release the reserved resources.
