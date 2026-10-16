# Application experiments (paper Figure 1)

This folder holds the motivation experiment. Five Prague application flows share a 100 Mbps DualPI2 bottleneck with
five bulk Classic flows (CUBIC or BBRv1). It also contains the script that draws paper Figure 1 from the per-trial
results.

| Folder | Contents |
|---|---|
| [`data/`](data/) | Per-trial results of the three applications (JSON) |
| [`scripts/plot_fig1.py`](scripts/plot_fig1.py) | Draws Figure 1 from `data/` |
| [`figures/`](figures/) | Figure 1 (PDF and 300 dpi PNG) |

To regenerate the figure, run `python plot_fig1.py` from `scripts/`, using the environment in the repository root's
`requirements.txt`. The experiment notebook will be added later.

## Setup

These settings come from the experiment names and recorded fields, except the Classic flow count, which is from the
paper:

| | |
|---|---|
| Bottleneck | DualPI2, 100 Mbps, PI2 target 15 ms |
| Base RTT | 30 ms |
| L4S side | 5 Prague application flows (one application per experiment) |
| Classic side | 5 bulk TCP flows (`updates`), CUBIC or BBRv1 |
| Trials | 5 per experiment |

The three applications are:

| Application | Transport | Workload (as recorded) |
|---|---|---|
| Video streaming | TCP Prague | 2 s chunks of 2,500,696 B (10 Mbps per flow) |
| File transfer | TCP Prague | 104,858,368 B (100 MiB) per flow |
| Video call | UDP Prague | target rate 5 Mbps per call |

The data also contain the same experiments against BBRv3. The figure leaves them out; the paper notes similar
degradation with BBRv3.

## Data files

Experiment names follow
`<application>-<transport>_updates-TCP_prague_<Classic CC>_DualPI2_<PI2 target>_<RTT>ms_<capacity>Mbps`, with
`_t<trial>` before the host suffix in per-trial names.

| File | Structure | Value plotted |
|---|---|---|
| `video_streaming_results_large_buffer.json` | `trials[]`: one entry per trial (`file`), with per-flow results in `flows` and totals in `summary`. `experiments{}`: means per experiment. | (a) `summary.total_rebuffering_sec / summary.num_flows`: the rebuffering time per flow over the run |
| `file_transfer.json` | `trials[]`: `completion_times_sec` (one per flow), `mean_completion_time_sec`, flows completed. `experiments{}`: means. | (b) `mean_completion_time_sec` of each trial |
| `prague_receiver_agg-5-apps.json` | One entry per experiment, with means over trials and `trials[]`, measured at the L4S receivers: goodput, RTT, CE-marking and loss probability, and achieved rate | (c) `trials[].mean_achieved_rate_fraction_pct`: received rate as a percentage of the 5 Mbps target |

Each marker in Figure 1 is the median of the five trial values, and its error bar spans their minimum to maximum.

| Panel | vs CUBIC (median, min–max) | vs BBRv1 (median, min–max) |
|---|---|---|
| (a) Rebuffering per flow (s) | 0, 0–0 | 112.5, 112.4–112.7 |
| (b) Flow completion time (s) | 72.7, 72.3–75.6 | 1746, 1683–1765 |
| (c) Achieved rate (%) | 99.4, 99.3–99.6 | 7.9, 7.4–8.5 |
