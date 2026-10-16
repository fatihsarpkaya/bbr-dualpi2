"""Figure 5: from the Classic-side PI2 signal to Prague throughput. Writes Plots/fig5a.pdf and Plots/fig5b.pdf.

(a) Steady-state Prague throughput R(p_hat) = theta0 (1 - p_hat) / p_hat (De Vleeschauwer et al., 2025) for one flow,
    with theta0 = 2 / max(RTT, 25 ms) packets/s, 30 ms RTT and 1500-B packets (theta0 = 0.8 Mbps).
(b) Prague share of the link at 100 Mbps and 30 ms base RTT, five Prague and five BBRv1 or BBRv2 flows: measured
    (main results, mean of three trials) and predicted from p' with p_hat = min(2p', 1), for five flows: from the
    measured p' (same runs and window) and from the fluid model's p' (five Classic flows alone, 20-40 s, averaged
    over seeds). Predictions above the link capacity are drawn at the capacity with an upward arrow.
Both subfigures are drawn at their printed size, side by side in one IEEE column.
"""
import logging
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

import fluid_results
import main_results

PLOTS = Path(__file__).resolve().parent.parent / "Plots"
COLUMN = 252 / 72.27  # IEEE column width (in)
H, BOTTOM, TOP = 1.78, 0.187, 0.706  # height (in) and vertical extent of the axes, shared by (a) and (b)
LEGEND_SIZE = 6.8
RTT, CAPACITY, FLOWS, PACKET = 30, 100, 5, 1500  # ms, Mbps, flows, bytes
TARGETS = [5, 15, 25, 50, 75]
CCS = [("bbr1", "BBRv1", "#d95f02", "s"), ("bbr2", "BBRv2", "#1b9e77", "^")]
LS = {"meas": "-", "lin": (0, (3.2, 1.6)), "fl": (0, (1, 1.3))}

logging.getLogger("fontTools").setLevel(logging.ERROR)
mpl.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "Times", "STIXGeneral", "DejaVu Serif"],
    "mathtext.fontset": "cm", "pdf.fonttype": 42, "ps.fonttype": 42,
    "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 7.5, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "legend.fontsize": LEGEND_SIZE, "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "xtick.minor.width": 0.4, "xtick.major.size": 2.5, "ytick.major.size": 2.5, "xtick.minor.size": 1.5,
    "xtick.major.pad": 2, "ytick.major.pad": 2, "axes.titlepad": 2,
    "axes.spines.top": False, "axes.spines.right": False,
})


def prague_share(p):
    """Predicted Prague share of the link for PI2 base probability p' (inf if p' = 0)."""
    p_hat = min(1.0, 2 * p)
    if p_hat <= 0:
        return np.inf
    theta0 = 2.0 / max(RTT / 1000, 0.025)  # packets/s
    return FLOWS * theta0 * (1 - p_hat) / p_hat * PACKET * 8 / 1e6 / CAPACITY


def fig5a(left=0.31, right=0.95):
    theta = 2.0 / max(RTT / 1000, 0.025) * PACKET * 8 / 1e6  # Mbps
    p_hat = np.arange(0.008, 1 + 0.005, 0.005)
    fig = plt.figure(figsize=(0.32 * COLUMN, H))
    ax = fig.add_axes([left, BOTTOM, right - left, TOP - BOTTOM])
    ax.plot(p_hat, theta * (1 - p_hat) / p_hat, lw=1.6, color=(0, 0.447, 0.741))
    ax.grid(True, color=(0.8, 0.8, 0.8), alpha=0.4, lw=0.4)
    ax.set_axisbelow(True)
    ax.set_xlabel(r"Steady-state $\hat{p}$", labelpad=1)
    ax.set_ylabel("Throughput (Mbps)", labelpad=2)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 100)
    ax.set_xticks([0, 0.5, 1])
    ax.set_yticks(np.arange(0, 101, 20))
    ax.xaxis.set_major_formatter(lambda v, _: str(int(round(v))) if abs(v - round(v)) < 1e-9 else "%.1f" % v)
    fig.text(0.5, 0.974, r"$\theta = %.1f$ Mbps" % theta + "\n" + f"RTT = {RTT} ms" + "\n" +
             f"Packet Size = {PACKET} B", ha="center", va="top", fontsize=LEGEND_SIZE, linespacing=1.45,
             bbox=dict(facecolor="white", edgecolor=(0.8, 0.8, 0.8), boxstyle="square,pad=0.30"))
    fig.savefig(PLOTS / "fig5a.pdf")
    plt.close(fig)


def up_arrow(ax, x, y, color):
    ax.annotate("", xy=(x, y), xytext=(0, -5.5), textcoords="offset points", annotation_clip=False, zorder=6,
                arrowprops=dict(arrowstyle="-|>", color=color, lw=0.7, mutation_scale=4.2, shrinkA=0, shrinkB=0))


def fig5b(left=0.165, right=0.98, gap=0.025, ms=3.0, lw=0.9):
    d = main_results.load()
    d = d[(d.btl_mbps == CAPACITY) & (d.rtt_ms == RTT)].set_index(["cc", "target_ms"])
    fig = plt.figure(figsize=(0.66 * COLUMN, H))
    pw = (right - left - gap) / 2
    axes = [fig.add_axes([left + k * (pw + gap), BOTTOM, pw, TOP - BOTTOM]) for k in range(2)]
    for ax, (cc, label, color, marker) in zip(axes, CCS):
        curves = {"meas": [d.prague_share[cc, t] for t in TARGETS],
                  "lin": [prague_share(d.p[cc, t]) for t in TARGETS],
                  "fl": [prague_share(fluid_results.mean_pprime(cc, RTT, t)) for t in TARGETS]}
        size = ms * (1.1 if marker == "^" else 1)
        markers = {"meas": dict(marker=marker, ms=size, mfc=color, mec=color, mew=0.6),
                   "lin": dict(marker=marker, ms=size, mfc="white", mec=color, mew=0.7),
                   "fl": dict(marker="D", ms=ms * 0.75, mfc="white", mec=color, mew=0.6)}
        for z, key in zip((4, 3, 2), ("meas", "lin", "fl")):
            y = curves[key] if key == "meas" else [min(v, 1.0) for v in curves[key]]
            ax.plot(TARGETS, y, color=color, lw=lw * (1.05 if key == "fl" else 1), ls=LS[key], zorder=z,
                    clip_on=False, **markers[key])
            for x, v in zip(TARGETS, curves[key]):
                if key != "meas" and v > 1.0 + 1e-12:  # above the link capacity
                    up_arrow(ax, x, 1.075, color)
        ax.set_xscale("log")
        ax.xaxis.set_minor_formatter(mpl.ticker.NullFormatter())
        ax.set_ylim(0, 1.1)
        ax.grid(True, which="major", lw=0.4, color="#e4e4e4")
        ax.axhline(1.0, color="#9a9a9a", lw=0.5, ls=(0, (1, 1.5)), zorder=1)
        if ax is not axes[0]:
            ax.tick_params(labelleft=False)
        ax.set_xlabel("PI2 target (ms)", labelpad=1)
        ax.set_xlim(4.4, 84)
        ax.set_xticks(TARGETS, labels=[str(t) for t in TARGETS])
        ax.xaxis.set_minor_locator(mpl.ticker.NullLocator())
        ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
        ax.set_title(label)
    axes[0].set_ylabel("Prague share of link", labelpad=2)
    g = "#444444"
    handles = [Line2D([], [], color=g, lw=0.9, ls=LS["meas"], marker="o", ms=3, mfc=g, mew=0.6, label="Measured"),
               Line2D([], [], color=g, lw=0.9, ls=LS["lin"], marker="o", ms=3, mfc="white", mew=0.7,
                      label="Predicted from experimental $p'$"),
               Line2D([], [], color=g, lw=0.95, ls=LS["fl"], marker="D", ms=2.3, mfc="white", mew=0.6,
                      label="Predicted from fluid-model $p'$")]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=((left + right) / 2, 1.0), ncol=1, frameon=False,
               handlelength=1.8, handletextpad=0.3, labelspacing=0.25, borderaxespad=0, fontsize=LEGEND_SIZE)
    fig.savefig(PLOTS / "fig5b.pdf")
    plt.close(fig)


def main():
    fig5a()
    fig5b()
    print("wrote fig5a.pdf, fig5b.pdf")


if __name__ == "__main__":
    main()
