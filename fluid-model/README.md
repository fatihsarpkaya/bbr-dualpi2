# BBRv1/BBRv2 Fluid Model with a PI2 Bottleneck

This is the fluid model used in Section V. It is the BBRv1/BBRv2 fluid model of Scherrer et al. ([paper](https://dl.acm.org/doi/10.1145/3517745.3561420), [original repository](https://github.com/simonschdev/imc22-bbr-fluid-model)), extended with a PI2 bottleneck (`qdisc: PI2` in `fluid_model/compute_trace.py`) that uses the Linux DualPI2 update interval and gains. The BBRv1, BBRv2 and CUBIC sender models are unchanged, except for two optional parameters used in the sensitivity runs.

## Run the Code

```bash
pip install -r ../requirements.txt
python run_model.py -c configs/bbr1_100mbps_rtt30_target15.yaml   # one configuration
JOBS=4 ./run_all.sh                                                # all configurations
```

- [`configs/`](configs/) contains the configurations for Figures 4 and 5: five Classic flows at 100 Mbps with an 8-BDP buffer. The file names give the congestion control, base RTT and PI2 target. [`configs/sensitivity/`](configs/sensitivity/) contains the sensitivity runs of Section V-B.
- `run_all.sh` runs every configuration and then `extract_pprime.py`. That script writes the p′(t) traces used by the plotting scripts to `../Experiment_Data/fluid-model/`.

## Licensing

The original code is by Simon Scherrer and James Dermelj, Copyright 2023 ETH Zurich. It is licensed under the Apache License 2.0 ([`LICENSE`](LICENSE)), as are our modifications. Modified files are marked at the top.
