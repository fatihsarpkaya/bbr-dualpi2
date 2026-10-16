"""Figure 1: application-level impact of Prague coexistence with CUBIC or BBRv1 under DualPI2 (100 Mbps, 30 ms RTT).
(a) video streaming: rebuffering per flow, (b) file transfer: mean flow completion time, (c) video call: achieved rate
as % of the target rate. Markers are medians over five trials; error bars span min-max. Writes Plots/fig1.pdf."""
import json
import re
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import MultipleLocator

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "Experiment_Data" / "motivation-experiments"
OUT = ROOT / "Plots" / "fig1.pdf"
BG_ORDER = ["cubic", "bbr1"]  # Classic CC; the data also contain BBRv3 runs, not shown
BG_LABEL = {"cubic": "vs\nCUBIC", "bbr1": "vs\nBBRv1"}
COLOR = "#2F7E83"

plt.rcParams.update({
    "pdf.fonttype": 42, "ps.fonttype": 42,
    "font.family": "serif", "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "font.size": 9, "axes.labelsize": 9, "xtick.labelsize": 7, "ytick.labelsize": 8, "legend.fontsize": 8,
    "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "xtick.major.size": 2.5, "ytick.major.size": 2.5,
})


def background_cc(name, app):
    """Classic CC from an experiment or trial name, e.g. streaming-TCP_updates-TCP_prague_bbr1_DualPI2_..."""
    m = re.match(rf"^{app}_updates-TCP_prague_([^_]+)_DualPI2_", name)
    return m.group(1) if m else None


def load():
    rebuffer, fct, call = defaultdict(list), defaultdict(list), {}
    for t in json.load(open(DATA / "video_streaming_results_large_buffer.json"))["trials"]:
        rebuffer[background_cc(t["file"], "streaming-TCP")].append(
            t["summary"]["total_rebuffering_sec"] / t["summary"]["num_flows"])
    for t in json.load(open(DATA / "file_transfer.json"))["trials"]:
        fct[background_cc(t["file"], "file_transfer-TCP")].append(float(t["mean_completion_time_sec"]))
    for name, e in json.load(open(DATA / "prague_receiver_agg-5-apps.json")).items():
        call[background_cc(name, "call-PRAGUE")] = [float(t["mean_achieved_rate_fraction_pct"]) for t in e["trials"]]
    return rebuffer, fct, call


def panel(ax, data, ylabel, ymin=None, ymax=None, log_y=False):
    for x, bg in enumerate(BG_ORDER):
        vals = np.array(data[bg])
        med, lo, hi = np.median(vals), vals.min(), vals.max()
        ax.plot(x, med, marker="o", linestyle="none", markersize=5.5, markerfacecolor=COLOR,
                markeredgecolor="#222222", markeredgewidth=0.7, zorder=3, clip_on=False)
        # the trial range is shorter than the marker, so the error bar is drawn on top of it
        ax.errorbar(x, med, yerr=[[med - lo], [hi - med]], fmt="none", ecolor="#222222", elinewidth=1.4, capsize=5,
                    capthick=1.1, zorder=4, clip_on=False)
    ax.set_xticks(range(len(BG_ORDER)))
    ax.set_xticklabels([BG_LABEL[b] for b in BG_ORDER])
    ax.set_xlim(-0.35, len(BG_ORDER) - 0.65)
    ax.set_ylabel(ylabel)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if log_y:
        ax.set_yscale("log")
        ax.grid(axis="y", which="major", linestyle="--", linewidth=0.4, alpha=0.5)
        ax.grid(axis="y", which="minor", linestyle=":", linewidth=0.3, alpha=0.3)
    else:
        ax.grid(axis="y", linestyle="--", linewidth=0.4, alpha=0.5)
        ax.set_ylim(ymin, ymax if ymax is not None else max(max(data[b]) for b in BG_ORDER) * 1.25)
        ax.yaxis.set_major_locator(MultipleLocator(50))


def main():
    rebuffer, fct, call = load()
    panels = [(rebuffer, dict(ylabel="Total\nrebuffering (s)", ymin=0)),
              (fct, dict(ylabel="Flow completion\ntime (s)", log_y=True)),
              (call, dict(ylabel="Achieved\nrate (%)", ymin=0, ymax=115))]
    titles = ["(a) TCP Prague\nvideo streaming", "(b) TCP Prague\nfile transfer", "(c) UDP Prague\nvideo call"]
    fig, axes = plt.subplots(1, 3, figsize=(3.5, 1.42))
    for ax, (data, kw), title in zip(axes, panels, titles):
        panel(ax, data, **kw)
        ax.set_title(title, fontsize=7, pad=5, linespacing=1.0)
        ax.yaxis.label.set_linespacing(1.0)
    plt.tight_layout(pad=0.2, w_pad=0.2)
    plt.savefig(OUT, bbox_inches="tight", pad_inches=0.01)
    print(f"wrote {OUT.name}")


if __name__ == "__main__":
    main()
