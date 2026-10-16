"""Paper Figure 3: measured PI2 base probability p' versus normalized Prague throughput at 100 Mbps.

Panels CUBIC | BBRv1 | BBRv2, same axes. Each point is one configuration (base RTT, PI2 target), mean of three trials:
  x = mean router p' over the last 60 s of the run   (results/coexistence_cells.csv `p_mean`)
  y = Prague throughput / capacity, same window       (`prague_share`, the values printed in Figure 2)
Base RTT = hue (10 ms red, 30 ms purple, 50 ms green); PI2 target = shade of that hue, from dark (5 ms) to light
(75 ms) in equal CIELAB lightness steps (L* 22 ... 74). A line in the RTT's hue joins the targets of one sweep.
Dashed line: equal share (0.5). BBRv2 RTT 30 ms / target 5 ms: p' averages two trials (one router log is truncated).
Writes figures/fig3_pprime_vs_prague_share.{pdf,png}. Usage: python plot_fig3.py
"""
import logging
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.ticker import MultipleLocator

HERE = Path(__file__).resolve().parent.parent
CELLS = HERE / "results" / "coexistence_cells.csv"
OUT = HERE / "figures" / "fig3_pprime_vs_prague_share"

BTL = 100
CCS = [("cubic", "CUBIC"), ("bbr1", "BBRv1"), ("bbr2", "BBRv2")]
TARGETS = [5, 15, 25, 50, 75]
RTTS = [10, 30, 50]
W_IN = 7.16  # IEEE \textwidth
P = "$p$′"  # italic p + the text font's prime
MS = 4.3  # marker diameter (pt)
EDGE = dict(edgecolors="0.12", linewidths=0.45)
FAIR = dict(color="0.55", lw=0.7, ls=(0, (4, 3)))

logging.getLogger("fontTools").setLevel(logging.ERROR)  # PDF font-subsetting chatter
mpl.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "Times", "DejaVu Serif"], "mathtext.fontset": "stix",
    "pdf.fonttype": 42, "ps.fonttype": 42,  # embed TrueType fonts (IEEE PDF eXpress rejects Type 3)
    "font.size": 8, "axes.labelsize": 9, "axes.titlesize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8,
    "legend.fontsize": 8, "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "xtick.minor.width": 0.45, "ytick.minor.width": 0.45, "xtick.major.size": 3, "ytick.major.size": 3,
    "xtick.minor.size": 1.6, "ytick.minor.size": 1.6, "xtick.direction": "in", "ytick.direction": "in",
})


def lch_ramp(l_hi, l_lo, hue, chroma, n):
    """n sRGB colours of one CIELCh hue (degrees, D65) with CIELAB lightness falling in equal steps from l_hi to
    l_lo. Chroma is lowered where needed to stay inside the sRGB gamut, so the lightness steps stay exact."""
    out = []
    for L in np.linspace(l_hi, l_lo, n):
        C = chroma
        while True:
            a, b = C * np.cos(np.deg2rad(hue)), C * np.sin(np.deg2rad(hue))
            fy = (L + 16) / 116
            xyz = [w * (t ** 3 if t ** 3 > 0.008856 else (t - 16 / 116) / 7.787)
                   for w, t in zip((0.95047, 1.0, 1.08883), (fy + a / 500, fy, fy - b / 200))]
            lin = np.array([[3.2406, -1.5372, -0.4986], [-0.9689, 1.8758, 0.0415], [0.0557, -0.2040, 1.0570]]) @ xyz
            if np.all((lin >= -1e-4) & (lin <= 1 + 1e-4)) or C <= 0:
                break
            C -= 1
        lin = np.clip(lin, 0, 1)
        out.append(mpl.colors.to_hex(np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * lin ** (1 / 2.4) - 0.055)))
    return out


HUE = {10: (40, 90), 30: (315, 80), 50: (170, 80)}  # CIELCh hue angle and chroma: red, purple, green
SHADE = {r: lch_ramp(74, 22, h, c, n=len(TARGETS))[::-1] for r, (h, c) in HUE.items()}  # [0] = 5 ms, darkest


def setup_plane(ax, ylabel):
    ax.set_xlim(0, 0.4)
    ax.set_ylim(0, 1)
    ax.xaxis.set_major_locator(MultipleLocator(0.1))
    ax.xaxis.set_minor_locator(MultipleLocator(0.05))
    ax.xaxis.set_major_formatter(lambda v, _: "0" if v == 0 else f"{v:g}")
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0], labels=["0", "0.25", "0.5", "0.75", "1"])
    ax.tick_params(which="both", top=True, right=True, labelleft=ylabel, labelbottom=True)


def main():
    c = pd.read_csv(CELLS)
    d = c[c.btl_mbps == BTL]
    if len(d) != 45 or not (d.trials == 3).all() or not (d.p_trials >= 2).all() or d.p_mean.isna().any():
        raise SystemExit(f"expected 45 configurations at {BTL} Mbps with 3 throughput trials and >= 2 p' trials each")
    if not d.p_mean.between(0, 0.4).all():
        raise SystemExit(f"p' outside the 0-0.4 axis:\n{d[~d.p_mean.between(0, 0.4)]}")
    for r in d[d.p_trials < 3].itertuples():
        print(f"note: p' for {r.cc} RTT {r.rtt_ms} ms target {r.target_ms} ms is the mean of {r.p_trials} trials")

    # Geometry in inches: three equal panels, colour key on the right
    left, right, gap, top, bottom, ph, key_room = 0.56, 0.10, 0.20, 0.06, 0.36, 1.0, 0.62
    pw = (W_IN - left - right - key_room - 2 * gap) / 3
    H = top + ph + bottom
    fig = plt.figure(figsize=(W_IN, H))
    axes = [fig.add_axes([(left + i * (pw + gap)) / W_IN, bottom / H, pw / W_IN, ph / H]) for i in range(3)]
    for i, (cc, label) in enumerate(CCS):
        ax = axes[i]
        setup_plane(ax, ylabel=i == 0)
        ax.axhline(0.5, zorder=1, **FAIR)
        for rtt in RTTS:
            g = d[(d.cc == cc) & (d.rtt_ms == rtt)].sort_values("target_ms")
            ax.plot(g.p_mean, g.prague_share, color=SHADE[rtt][2], lw=0.9, zorder=3, clip_on=False)
        for rtt in RTTS:
            g = d[(d.cc == cc) & (d.rtt_ms == rtt)].sort_values("target_ms")
            ax.scatter(g.p_mean, g.prague_share, s=MS ** 2, marker="o",
                       c=[SHADE[rtt][TARGETS.index(t)] for t in g.target_ms], zorder=4, clip_on=False, **EDGE)
        ax.text(0.97, 0.94, f"({'abc'[i]}) {label}", transform=ax.transAxes, ha="right", va="top", fontsize=9)
    axes[0].set_ylabel("Prague\nthroughput share", linespacing=1.0)
    h = [Line2D([], [], color=SHADE[r][2], lw=0.9, marker="o", ms=MS, mfc=SHADE[r][2], mec="0.12", mew=0.45,
                label=f"RTT {r} ms") for r in RTTS]
    h.append(Line2D([], [], label="Fair share", **FAIR))
    axes[0].legend(handles=h, loc="lower right", ncol=2, frameon=False, fontsize=7.5, handlelength=1.8,
                   handletextpad=0.4, columnspacing=0.8, labelspacing=0.3, borderaxespad=0.25)
    plot_right = right + key_room
    fig.text((left + (W_IN - left - plot_right) / 2) / W_IN, 0.04 / H, f"Measured PI2 base probability {P}",
             ha="center", va="bottom", fontsize=9)

    # colour key: one column per base RTT with its actual shades, one shared set of PI2 target labels
    n = len(TARGETS)
    cax = fig.add_axes([(W_IN - plot_right + 0.16) / W_IN, bottom / H, 0.24 / W_IN, ph / H])
    cax.set_xlim(0, len(RTTS))
    cax.set_ylim(0, n)
    for j, rtt in enumerate(RTTS):
        for k in range(n):
            cax.add_patch(Rectangle((j, k), 1, 1, facecolor=SHADE[rtt][k], edgecolor="white", lw=0.8))
    cax.set_xticks([])
    cax.yaxis.tick_right()
    cax.yaxis.set_label_position("right")
    cax.set_yticks(np.arange(n) + 0.5, [str(t) for t in TARGETS])
    cax.tick_params(length=0, pad=2, labelsize=7.5)
    for s in cax.spines.values():
        s.set_linewidth(0.5)
    cax.set_ylabel("PI2 target (ms)", fontsize=9, labelpad=3)

    OUT.parent.mkdir(exist_ok=True)
    fig.savefig(OUT.with_suffix(".pdf"), bbox_inches="tight", pad_inches=0.02)
    fig.savefig(OUT.with_suffix(".png"), dpi=300, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print(f"wrote figures/{OUT.name}.pdf and .png")


if __name__ == "__main__":
    main()
