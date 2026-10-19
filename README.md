# When Coupling Backfires: BBR-Induced L4S Degradation under DualPI2

This repository contains the artifacts for the paper **"When Coupling Backfires: BBR-Induced L4S Degradation under DualPI2."**

## Abstract

Low Latency, Low Loss, Scalable Throughput (L4S) uses DualPI2 to separate low latency (e.g., TCP Prague) and Classic flows into two queues while coupling their congestion signals. However, this coupling is designed for Reno-like Classic congestion controls, while widely deployed BBR behaves differently. Prior studies observed severe Prague throughput degradation when BBR occupies the Classic queue under DualPI2, but the mechanism remains insufficiently explained. Through controlled testbed experiments and an extension of an existing BBRv1/BBRv2 fluid model with PI2, we show that BBR can drive the PI2 base probability p′ far above CUBIC levels, producing strong coupled marking that can nearly starve Prague despite low L4S queueing delay. The model explains BBRv1's persistent high-p′ regime, BBRv2's lower, oscillating p′, and their dependence on the PI2 target relative to RTT. Our findings highlight the need for coupling mechanisms supporting low latency flows across heterogeneous Classic congestion controls.

This repository includes:

- [`experiment_fabric_linux.ipynb`](experiment_fabric_linux.ipynb), the FABRIC experiment notebook for the main and Classic-only experiments.
- [`experiment_fabric_motivation.ipynb`](experiment_fabric_motivation.ipynb), the FABRIC experiment notebook for the motivation experiments (Figure 1).
- [`utils/`](utils/), containing the DualPI2 logging script run on the router and the analysis scripts of the motivation experiments.
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
python sensitivity.py   # Section V-B sensitivity results (printed table)
```

The figures are written to `Plots/`, with one file per subfigure for Figures 4 and 5. The raw logs in `Experiment_Data/` are xz-compressed; the scripts read them directly.

## Running the Fluid Model

The fluid-model results in `Experiment_Data/fluid-model/` can be regenerated without a testbed:

```bash
pip install -r requirements.txt
cd fluid-model
JOBS=4 ./run_all.sh
```

See [`fluid-model/README.md`](fluid-model/README.md) for details.

## Running the Experiments on FABRIC

You need a [FABRIC](https://fabric-testbed.net/) account, an active project with sufficient quota, configured SSH keys, and access to the FABRIC JupyterHub environment.

Open a terminal in FABRIC JupyterHub and run:

```bash
git clone https://github.com/fatihsarpkaya/bbr-dualpi2.git
cd bbr-dualpi2
```

Open the notebook in JupyterLab and follow it section by section: `experiment_fabric_linux.ipynb` for the main and Classic-only experiments, and `experiment_fabric_motivation.ipynb` for the motivation experiments. Do not use **Run All**, because slice creation, kernel installation, node reboots, and experiment execution must finish in order. Before running the main experiments, upload `utils/dualpi2_v2.sh` to the router's home directory; the notebook runs it there to log the DualPI2 statistics.

### Endpoint Software

The motivation experiments use `socat`, [MGEN](https://github.com/fatihsarpkaya/mgen), and [UDP Prague](https://github.com/fatihsarpkaya/udp_prague). Install them on `tx_L4S`, `tx_legacy`, `rx_L4S`, and `rx_legacy`:

```bash
sudo apt update
sudo apt install -y socat build-essential g++ libpcap-dev git

mkdir -p ~/L4S_Project
cd ~/L4S_Project
git clone --recursive https://github.com/fatihsarpkaya/mgen.git
git clone https://github.com/fatihsarpkaya/udp_prague.git

cd ~/L4S_Project/udp_prague
make lib_prague
make udp_prague_receiver

cd ~/L4S_Project/mgen/makefiles
make -f Makefile.linux mgen
```

These commands create the paths expected by the notebook:

- `/home/ubuntu/L4S_Project/mgen/makefiles/mgen`
- `/home/ubuntu/L4S_Project/udp_prague/udp_prague_receiver`

Delete the FABRIC slice after completing the experiments to release the reserved resources.
