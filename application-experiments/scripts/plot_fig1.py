"""Paper Figure 1: application-level impact of Prague coexistence with Classic traffic under DualPI2.

Five Prague application flows share a 100 Mbps DualPI2 bottleneck (30 ms base RTT, 15 ms PI2 target) with five CUBIC
or BBRv1 bulk flows. Three panels, one per application, each comparing "vs CUBIC" with "vs BBRv1":
  (a) TCP Prague video streaming: rebuffering time per flow (s), i.e. summary.total_rebuffering_sec / num_flows
  (b) TCP Prague file transfer:   mean flow completion time of the trial (s), log scale
  (c) UDP Prague video call:      achieved rate as a percentage of the call's target rate
Markers are medians over the five trials; error bars span min-max. The data files also contain runs against BBRv3,
which the figure leaves out.
Reads data/*.json; writes figures/fig1_application_impact.{pdf,png}. Usage: python plot_fig1.py
"""
import json
import re
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import MultipleLocator

HERE = Path(__file__).resolve().parent.parent
STREAMING_JSON = HERE / "data" / "video_streaming_results_large_buffer.json"
CALL_JSON = HERE / "data" / "prague_receiver_agg-5-apps.json"
FILE_TRANSFER_JSON = HERE / "data" / "file_transfer.json"
OUT = HERE / "figures" / "fig1_application_impact"
COLUMN_WIDTH_IN = 3.5  # IEEE single column
HEIGHT_IN = 1.42  # 1.2 in of plot + room for the two-line application titles

BG_ORDER = ["cubic", "bbr1"]  # background (Classic) CC, left to right
BG_DISPLAY = {"cubic": "vs\nCUBIC", "bbr1": "vs\nBBRv1"}
BG_COLOR = {"cubic": "#2F7E83", "bbr1": "#2F7E83"}

plt.rcParams.update({
    "pdf.fonttype": 42, "ps.fonttype": 42,  # embed TrueType fonts (IEEE PDF eXpress rejects Type 3)
    "font.family": "serif", "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "font.size": 9, "axes.labelsize": 9, "xtick.labelsize": 7, "ytick.labelsize": 8, "legend.fontsize": 8,
    "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "xtick.major.size": 2.5, "ytick.major.size": 2.5,
})

WORKLOAD_PATTERNS = {
    "streaming": re.compile(r"^streaming-TCP_updates-TCP_prague_([^_]+)_DualPI2_.+_tx_L4S$"),
    "call": re.compile(r"^call-PRAGUE_updates-TCP_prague_([^_]+)_DualPI2_.+_rx_L4S$"),
    "file_transfer": re.compile(r"^file_transfer-TCP_updates-TCP_prague_([^_]+)_DualPI2_.+_tx_L4S$"),
}


def experiment_name(file_name):
    """Trial log name -> experiment name (drops '.log' and the '_t<trial>' suffix)."""
    return re.sub(r"_t\d+(?=_tx_L4S$)", "", file_name.replace(".log", ""))


def background_cc(exp_name, workload):
    m = WORKLOAD_PATTERNS[workload].match(exp_name)
    return m.group(1).lower() if m else None


def rebuffering_per_flow(trial):
    return trial["summary"]["total_rebuffering_sec"] / trial["summary"]["num_flows"]


def mean_fct(trial):
    if "mean_completion_time_sec" in trial:
        return float(trial["mean_completion_time_sec"])
    vals = trial.get("completion_times_sec", [])
    if len(vals) == 0:
        raise ValueError("Trial has no mean_completion_time_sec and no completion_times_sec.")
    return float(np.mean(vals))


def load():
    """{workload: {background CC: [one value per trial]}}"""
    streaming = json.load(open(STREAMING_JSON))
    rebuffer = defaultdict(list)
    for trial in streaming["trials"]:
        bg = background_cc(experiment_name(trial["file"]), "streaming")
        if bg in BG_ORDER:
            rebuffer[bg].append(rebuffering_per_flow(trial))

    call = {}
    for exp_name, exp_data in json.load(open(CALL_JSON)).items():
        bg = background_cc(exp_name, "call")
        if bg in BG_ORDER and exp_data.get("trials"):
            call[bg] = [float(t["mean_achieved_rate_fraction_pct"]) for t in exp_data["trials"]]

    fct = defaultdict(list)
    for trial in json.load(open(FILE_TRANSFER_JSON))["trials"]:
        bg = background_cc(experiment_name(trial["file"]), "file_transfer")
        if bg in BG_ORDER:
            fct[bg].append(mean_fct(trial))
    return rebuffer, fct, call


def plot_median_range(ax, bg_data, ylabel, ymin=None, ymax=None, log_y=False):
    """Median marker per background CC with min-max error bars drawn on top."""
    positions = list(range(len(BG_ORDER)))
    upper_values = []
    for x, bg in zip(positions, BG_ORDER):
        vals = np.array([v for v in bg_data.get(bg, []) if not (isinstance(v, float) and np.isnan(v))])
        if len(vals) == 0:
            continue
        med, lo, hi = np.median(vals), np.min(vals), np.max(vals)
        upper_values.append(hi)
        # The trial range spans < 1 pt on the page (smaller than the 5.5 pt marker), so the error bar is drawn ON TOP
        # of the marker with caps wider than the marker: it stays visible, at its true length.
        ax.plot(x, med, marker="o", linestyle="none", markersize=5.5, markerfacecolor=BG_COLOR[bg],
                markeredgecolor="#222222", markeredgewidth=0.7, zorder=3,
                clip_on=False)  # a value of exactly 0 sits on the axis; draw the whole marker
        ax.errorbar(x, med, yerr=[[med - lo], [hi - med]], fmt="none", ecolor="#222222", elinewidth=1.4, capsize=5,
                    capthick=1.1, zorder=4, clip_on=False)

    ax.set_xticks(positions)
    ax.set_xticklabels([BG_DISPLAY[b] for b in BG_ORDER])
    ax.set_xlim(-0.35, len(BG_ORDER) - 0.65)  # narrow margins, so the two labels fit in the short, narrow panels
    ax.set_ylabel(ylabel)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if log_y:
        ax.set_yscale("log")
        ax.grid(axis="y", which="major", linestyle="--", linewidth=0.4, alpha=0.5)
        ax.grid(axis="y", which="minor", linestyle=":", linewidth=0.3, alpha=0.3)
        if ymin is not None or ymax is not None:
            ax.set_ylim(ymin, ymax)
    else:
        ax.grid(axis="y", linestyle="--", linewidth=0.4, alpha=0.5)
        eff_ymin = 0 if ymin is None else ymin
        if ymax is not None:
            ax.set_ylim(eff_ymin, ymax)
        elif upper_values:
            ax.set_ylim(eff_ymin, max(upper_values) * 1.25)


def main():
    rebuffer, fct, call = load()
    panels = [
        (rebuffer, dict(ylabel="Total\nrebuffering (s)", ymin=0)),
        (fct, dict(ylabel="Flow completion\ntime (s)", log_y=True)),
        (call, dict(ylabel="Achieved\nrate (%)", ymin=0, ymax=115)),
    ]
    titles = ["(a) TCP Prague\nvideo streaming", "(b) TCP Prague\nfile transfer", "(c) UDP Prague\nvideo call"]
    for data, kw in panels:
        if any(len(data.get(bg, [])) != 5 for bg in BG_ORDER):
            raise SystemExit(f"expected 5 trials per background CC for {kw['ylabel']!r}")

    fig, axes = plt.subplots(1, 3, figsize=(COLUMN_WIDTH_IN, HEIGHT_IN))
    for ax, (data, kw), title in zip(axes, panels, titles):
        plot_median_range(ax, data, **kw)
        ax.set_title(title, fontsize=7, pad=5, linespacing=1.0)
        ax.yaxis.label.set_linespacing(1.0)
        if not kw.get("log_y"):
            ax.yaxis.set_major_locator(MultipleLocator(50))  # short panels: ticks every 50 so labels do not crowd
    plt.tight_layout(pad=0.2, w_pad=0.2)
    OUT.parent.mkdir(exist_ok=True)
    plt.savefig(OUT.with_suffix(".pdf"), bbox_inches="tight", pad_inches=0.01)
    plt.savefig(OUT.with_suffix(".png"), dpi=300, bbox_inches="tight", pad_inches=0.01)

    print("median / min / max over the 5 trials:")
    for data, kw in panels:
        print(f"  {kw['ylabel']}:".replace("\n", " "))
        for bg in BG_ORDER:
            v = np.array(data[bg])
            print(f"    vs {bg}: {np.median(v):.3f} / {v.min():.3f} / {v.max():.3f}")
    print(f"wrote figures/{OUT.name}.pdf and .png")


if __name__ == "__main__":
    main()
