# When Coupling Backfires: BBR-Induced L4S Degradation under DualPI2

This repository contains the artifacts for the paper **"When Coupling Backfires: BBR-Induced L4S Degradation under DualPI2."**

## Abstract

Low Latency, Low Loss, Scalable Throughput (L4S) uses DualPI2 to separate L4S and Classic traffic into two queues while coupling their congestion signals. However, this coupling is designed for Reno-like Classic congestion controls, while widely deployed BBR behaves differently. Prior studies have observed severe TCP Prague throughput degradation with BBR under DualPI2, but the underlying mechanism remains insufficiently explained. Through controlled testbed experiments and an extension of an existing BBRv1/BBRv2 fluid model with PI2, we show that BBR can drive the PI2 base probability p′ far above CUBIC levels, producing strong coupled marking that can nearly starve Prague despite low L4S queueing delay. The model explains BBRv1's persistent high-p′ regime, BBRv2's lower, oscillating p′, and their dependence on the PI2 target relative to RTT. Our findings highlight the need for coupling mechanisms robust to heterogeneous congestion control algorithms.

This repository includes:

- [`experiment_fabric_linux.ipynb`](experiment_fabric_linux.ipynb), the FABRIC experiment notebook.
- [`utils/`](utils/), containing the DualPI2 logging script run on the router.
- [`fluid-model/`](fluid-model/), containing the BBRv1/BBRv2 fluid model of Scherrer et al. with our PI2 extension, and the configurations of our model runs.
- [`Experiment_Data/`](Experiment_Data/), containing the motivation (Figure 1), main (Figures 2, 3, and 5), Classic-only (Figure 4), and fluid-model (Figures 4 and 5) results.
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
python plot_fig4.py
python plot_fig5.py
python sensitivity.py   # the fluid-model sensitivity runs of Section V-B, as a table
```

The figures are written to `Plots/`, with one file per subfigure for Figures 4 and 5. The raw logs in `Experiment_Data/` are xz-compressed; the scripts read them directly.

## Running the Fluid Model

The fluid-model results in `Experiment_Data/fluid-model/` can be regenerated with Python alone; no testbed is needed:

```bash
pip install -r requirements.txt
cd fluid-model
python run_model.py -c configs/bbr1_100mbps_rtt30_target15.yaml   # one configuration
JOBS=4 ./run_all.sh                                                # all configurations
```

[`fluid-model/README.md`](fluid-model/README.md) describes the model, our changes, the configurations, and their running time and memory.

## Running the Experiments on FABRIC

You need a [FABRIC](https://fabric-testbed.net/) account, an active project with sufficient quota, configured SSH keys, and access to the FABRIC JupyterHub environment.

Open a terminal in FABRIC JupyterHub and run:

```bash
git clone https://github.com/fatihsarpkaya/bbr-dualpi2.git
cd bbr-dualpi2
```

Open `experiment_fabric_linux.ipynb` in JupyterLab and follow it section by section. Do not use **Run All**, because slice creation, kernel installation, node reboots, and experiment execution must finish in order. Before running the experiments, upload `utils/dualpi2_v2.sh` to the router's home directory; the notebook runs it there to log the DualPI2 statistics.

Delete the FABRIC slice after completing the experiments to release the reserved resources.
