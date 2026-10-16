# Linux experiments

These are testbed measurements of TCP Prague sharing a Linux DualPI2 bottleneck with CUBIC, BBRv1 or BBRv2 flows,
together with the Classic-only runs used for comparison with the fluid model. Each folder contains the following:

| Folder | Contents |
|---|---|
| [`data/`](data/) | Raw logs of every run, xz-compressed (1,755 files, 361 MB; 3.5 GB uncompressed) |
| [`scripts/`](scripts/) | Data readers, the run summary, and the scripts for paper Figures 2 and 3 |
| [`results/`](results/) | Summary CSVs written by `scripts/summarize_coexistence.py` |
| [`figures/`](figures/) | Paper Figures 2 and 3 (PDF and 300 dpi PNG) |
| [`fabric/`](fabric/) | The FABRIC notebook that builds the testbed and runs the sweep, and the router's DualPI2 statistics poller |

## Reproducing the figures

Run these commands from the repository root:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd linux-experiments/scripts
python summarize_coexistence.py   # data/ -> results/coexistence_{runs,cells}.csv  (~5 s on 10 cores)
python plot_fig2.py               # -> figures/fig2_prague_share.{pdf,png}
python plot_fig3.py               # -> figures/fig3_pprime_vs_prague_share.{pdf,png}
```

The summary script also prints its integrity checks, listed under [Known data issues](#known-data-issues). The
figures use Times New Roman when it is installed; otherwise matplotlib falls back to Times or DejaVu Serif.

| Paper figure | Script | Data it plots |
|---|---|---|
| Fig. 2: Prague throughput share, all 90 configurations | `plot_fig2.py` | `results/coexistence_cells.csv`: `prague_share` |
| Fig. 3: measured p′ vs Prague share, 100 Mbps | `plot_fig3.py` | the same file, 100 Mbps rows: `p_mean` (x) and `prague_share` (y) |

## Testbed

The testbed runs on [FABRIC](https://fabric-testbed.net/). Every node is an Ubuntu 22.04 VM with 4 cores and 32 GB of
RAM. The topology is a dumbbell of six nodes:

```
tx_L4S    ─┐                                     ┌─ rx_L4S
           ├─ delay (netem) ── router (DualPI2) ─┤
tx_legacy ─┘                                     └─ rx_legacy
```

[`fabric/experiment_fabric_linux.ipynb`](fabric/experiment_fabric_linux.ipynb) reserves this slice, installs the
kernels, configures every node and runs the sweep.

| Node | Kernel | Congestion control |
|---|---|---|
| `tx_L4S` | `6.6.114-a76b708b2-l4steam-116` (L4STeam `l4steam-6.6.y`) | TCP Prague, AccECN (`tcp_ecn=3`), ECT(1) |
| `tx_legacy` | `6.4.0+` (google/bbr `v3` branch) | CUBIC (`cubic`), BBRv1 (`bbr1`, the v6.4 `tcp_bbr.c` under another name) |
| `tx_legacy` | `5.13.12` (google/bbr `v2alpha` branch) | BBRv2 (`bbr2`) |
| `router`, L4S receiver | L4STeam Linux 6.6 | `dualpi2` qdisc on the router |

The sender kernel strings are as recorded in each run's iperf3 JSON.

Each node is configured as follows:
- **Router.** The bottleneck is an HTB class at capacity C with `dualpi2` as its child qdisc. Only two parameters are
  set:
  - `limit`: a buffer of 8 BDP in 1500-byte packets, rounded up.
  - `target`: the PI2 delay target.

  Everything else is at its default: step threshold 1 ms, coupling factor k = 2, PI2 update interval 16 ms, and
  Classic protection 10% (90/10 WRR when both queues are backlogged).
- **Path.** The `delay` node adds half the base RTT with netem on each of its two interfaces. GRO, LRO, GSO and TSO
  are off on every interface, and every interface uses a 1500-byte MTU.
- **ECN.** Classic senders run with ECN disabled, so the Classic queue drops packets and every CE mark lands on L4S
  packets. Prague's RTT-independence reference (`prague_rtt_target`) is 25 ms.
- **Traffic.** Each sender runs one iperf3 3.19.1 client with 5 parallel flows (`-P 5 -C <cc> -J`), which gives 5
  Prague flows against 5 Classic flows.
- **Logging.**
  - Both senders log `ss -eipn` every ~0.13 s, timestamped by `ts`.
  - The router polls `tc -s qdisc` every ~0.11 s with [`fabric/dualpi2_v2.sh`](fabric/dualpi2_v2.sh). The notebook
    runs it from the router's home directory, so copy it there first.
  - The 60 s CUBIC runs used an earlier poller that wrote only the first six columns.

## Sweeps

| Sweep | Folders in `data/` | Classic CC | Capacity | Base RTT | PI2 target | Duration | Trials | Runs |
|---|---|---|---|---|---|---|---|---|
| Coexistence (Prague + Classic) | `dualpi2_sweep_{tx_L4S,tx_legacy,router}_180s` | CUBIC, BBRv1, BBRv2 | 100, 500 Mbps | 10, 30, 50 ms | 5, 15, 25, 50, 75 ms | 180 s | 700–702 | 270 |
| Classic alone, BBR | `pi2_sweep_classic_alone_{tx_legacy,router}_180s` | BBRv1, BBRv2 | 100 Mbps | 10, 30, 50 ms | 5, 15, 25, 50, 75 ms | 180 s | 800–802 | 90 |
| Classic alone, CUBIC | `pi2_sweep_classic_alone_{tx_legacy,router}` | CUBIC | 100 Mbps | 10, 30, 50 ms | 5, 15, 25, 50, 75 ms | 60 s | 900–902 | 45 |

Every run uses an 8-BDP buffer. Only the CUBIC runs of the 60 s Classic-alone sweep are included; its BBR runs are
superseded by the 180 s sweep.

The notebook's `exp_factors` cell shows one batch (100 Mbps, trials 1–3); the data were collected in several batches.
- **Coexistence runs:** capacities of 100 and 500 Mbps, trials 700–702.
- **Classic-alone runs:** `aqm = 'pi2'`, trials 800–802 (BBR, 180 s) and 900–902 (CUBIC, 60 s). No Prague client
  ran in these.

The Classic-alone file names still contain `prague` and `5_5`, but no Prague flows ran. There are no `tx_L4S` files,
and the router's L4S packet counter (`pkts_in_l`) is 0 in all 135 router logs. Their AQM label is `pi2` rather than
`DualPI2`, but the router ran the same `dualpi2` qdisc with the same `target` and `limit` settings. With no L4S
traffic, only its PI2 (Classic) part is active.

## Data files

Folder names are the directory names on the FABRIC hosts. File names are unchanged, with `.xz` appended. The scripts
read the compressed files directly; to unpack one, run `xz -dk <file>.xz`.

Each run has a name that encodes its configuration, for example `prague_bbr1_8.0_100_30_DualPI2_15_0_3_0_5_5_0_0_700`:

| # | Field | Example | Values in this dataset |
|---|---|---|---|
| 1 | first CC: the sender this file belongs to | `prague` | `prague` on `tx_L4S` and the router; the Classic CC on `tx_legacy` |
| 2 | the other sender's CC | `bbr1` | `cubic`, `bbr1`, `bbr2` or `prague` |
| 3 | buffer, in BDP | `8.0` | `8.0` |
| 4 | bottleneck capacity C (Mbps) | `100` | `100`, `500` |
| 5 | base RTT (ms) | `30` | `10`, `30`, `50` |
| 6 | AQM label | `DualPI2` | `DualPI2` (coexistence), `pi2` (Classic alone) |
| 7 | PI2 delay target (ms) | `15` | `5` … `75` |
| 8 | Prague classic-ECN fallback | `0` | `0` (off) |
| 9 | `tcp_ecn` on the L4S receiver | `3` | `3` (AccECN) |
| 10 | `tcp_ecn` on the Classic receiver | `0` | `0` (off) |
| 11, 12 | flows per sender: L4S, Classic | `5_5` | `5_5` |
| 13, 14 | DualPI2 WRR weight override (L, C) | `0_0` | `0_0` (module defaults) |
| 15 | trial | `700` | see [Sweeps](#sweeps) |

The `tx_legacy` files swap fields 1 and 2 (`bbr1_prague_…`). The router log uses the `tx_L4S` name
(`prague_bbr1_…_dualpi2.log`), including in the Classic-alone sweeps.

### Sender files (`tx_L4S`, `tx_legacy`)

- **`<name>-result.json`.** The iperf3 `--json` output, with sender-side intervals of 1 s.
  - `start.connected[].local_port` identifies the five data connections.
  - `end.sum_received` is the receiver-side total for the whole run.
- **`<name>-ss.txt`.** Repeated `ss -eipn` snapshots. Each socket takes two lines:
  - `<unix time> tcp ESTAB <recv-q> <send-q> <local addr:port> <peer addr:port> …`
  - `<unix time> <tab> <tcp_info>`, carrying `cwnd`, `rtt`, `mss`, `bytes_acked`, `delivery_rate`, `bbr:(…)`, and so on.

  The iperf3 control connection also appears in these snapshots, so select the data connections by their local port.

### Router files (`router`)

`<name>_dualpi2.log` is whitespace-separated, has a header line, and has one row per poll:

| Column | Meaning |
|---|---|
| `timestamp` | Unix time of the poll (router clock) |
| `prob_raw` | PI2 base probability p′ |
| `pkts_in_c`, `pkts_in_l` | packets enqueued to the Classic / L4S queue (cumulative) |
| `delay_c_us`, `delay_l_us` | Classic / L4S queueing delay at the poll (µs) |
| `ecn_mark` | CE marks set by the qdisc (cumulative); with ECN off for Classic, these are all L4S marks |
| `step_mark` | the subset of `ecn_mark` set by the L4S step threshold (cumulative); `ecn_mark - step_mark` are coupled marks |
| `dropped` | qdisc drops (cumulative) |
| `backlog_pkts` | packets queued at the poll, both queues |
| `maxq` | largest queue length seen so far |

The 180 s sweeps have all 11 columns; the 60 s CUBIC runs have only the first six. Cumulative counters count from
when the qdisc was created, so take differences over the window you analyse.

## Processing

`scripts/summarize_coexistence.py` reduces each coexistence run to its last 60 s:

1. `t0` is the first line of the Prague sender's ss trace, which is when iperf3 starts.
2. The ss loggers stop about 2 s before iperf3 does. The window therefore ends at
   `W_end = min(last Prague ss sample, last Classic ss sample, t0 + 180 s)`, which is about `t0` + 178 s, and spans
   `[W_end - 60 s, W_end]`.
3. **Throughput** is the increase of `bytes_acked` over the window, summed over a sender's five data connections and
   divided by the time between the first and last sample. This is what the receivers acknowledged.
4. **Router quantities** use the router samples inside the same window:
   - p′ is the mean of `prob_raw`.
   - Delays are the mean and 95th percentile of the per-poll readings.
   - Marking fractions are differences of the cumulative counters.
5. **Configuration values** are means over the three trials.

As a cross-check, iperf3's own sender-side byte count over its last 60 intervals agrees with the acknowledged
throughput to within ±0.008 C in every run.

`results/coexistence_runs.csv` has one row per run (270 rows):

| Column | Definition |
|---|---|
| `cc`, `btl_mbps`, `rtt_ms`, `target_ms`, `trial` | Classic CC, capacity C, base RTT, PI2 target, trial |
| `window_start_s`, `window_end_s` | the window, in seconds after `t0` |
| `prague_mbps`, `classic_mbps` | throughput of the five Prague / five Classic flows |
| `prague_share` | `prague_mbps` / C |
| `utilization` | (Prague + Classic throughput) / C |
| `prague_sender_mbps` | iperf3 sender-side Prague throughput over its last 60 intervals (cross-check) |
| `p_mean` | mean PI2 base probability p′ |
| `qdelay_c_mean_ms`, `qdelay_l_mean_ms`, `qdelay_l_p95_ms` | Classic and L4S queueing delay |
| `l4s_ce_frac` | CE-marked fraction of L4S packets: Δ`ecn_mark` / Δ`pkts_in_l` |
| `step_share_of_ce` | fraction of those CE marks set by the step threshold: Δ`step_mark` / Δ`ecn_mark` |
| `router_samples` | router polls in the window |
| remaining columns | inputs to the integrity checks (iperf3 durations, stream counts and errors, ss sample gaps, router-log coverage) |

`results/coexistence_cells.csv` has one row per configuration (90 rows):
- `trials` is the number of trials.
- `p_trials` is the number of trials with router data.
- `prague_share` is the trial mean, and `prague_share_sd`, `_min` and `_max` describe its spread across trials.
- Every other column is the trial mean of the run column with the same name, ignoring missing values.

## Known data issues

- **Truncated router log.** The log for BBRv2, 100 Mbps, RTT 30 ms, target 5 ms, trial 700 ends 22.6 s after
  `t0`; the raw file really ends there. The run has no router data in its window, so p′ and the other router columns
  for that configuration average trials 701–702. Its throughput is unaffected.
- **Invalid delay readings.** In the coexistence router logs, 79 delay readings equal 4294967295 µs (2³² − 1). This
  is a race in the kernel's statistics dump, not a delay. `read_router_log()` in `scripts/dataset.py` sets them to
  NaN; p′ and the counters in those rows are valid.
- **iperf3 per-interval bytes.** The sender-side byte counts are application writes into the socket buffer, not
  delivered data. That is why throughput comes from `bytes_acked`.
- **Shrinking Prague MSS.** A starved Prague flow shrinks its MSS: against BBRv1 the Prague `mss` drops to as low as
  150 B. Router packet counts times 1448 B therefore do not give Prague's throughput.
