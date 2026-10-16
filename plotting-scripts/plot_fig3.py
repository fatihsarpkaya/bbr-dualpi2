"""Figure 3: measured PI2 base probability p' vs normalized Prague throughput at 100 Mbps (mean of three trials).
Base RTT = hue; PI2 target = shade (darker = smaller target). Writes Plots/fig3.pdf."""
import logging
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.ticker import MultipleLocator

import main_results

OUT = Path(__file__).resolve().parent.parent / "Plots" / "fig3.pdf"
CCS = [("cubic", "CUBIC"), ("bbr1", "BBRv1"), ("bbr2", "BBRv2")]
TARGETS = [5, 15, 25, 50, 75]
RTTS = [10, 30, 50]
W_IN = 7.16  # IEEE text width
MS = 4.3  # marker diameter (pt)
EDGE = dict(edgecolors="0.12", linewidths=0.45)
FAIR = dict(color="0.55", lw=0.7, ls=(0, (4, 3)))

logging.getLogger("fontTools").setLevel(logging.ERROR)
mpl.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "Times", "DejaVu Serif"], "mathtext.fontset": "stix",
    "pdf.fonttype": 42, "ps.fonttype": 42,
    "font.size": 8, "axes.labelsize": 9, "axes.titlesize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8,
    "legend.fontsize": 8, "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "xtick.minor.width": 0.45, "ytick.minor.width": 0.45, "xtick.major.size": 3, "ytick.major.size": 3,
    "xtick.minor.size": 1.6, "ytick.minor.size": 1.6, "xtick.direction": "in", "ytick.direction": "in",
})


def lch_ramp(l_hi, l_lo, hue, chroma, n):
    """n sRGB colours of one CIELCh hue with CIELAB lightness falling in equal steps from l_hi to l_lo."""
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
            C -= 1  # stay inside the sRGB gamut
        lin = np.clip(lin, 0, 1)
        out.append(mpl.colors.to_hex(np.where(lin <= 0.0031308, 12.92 * lin, 1.055 * lin ** (1 / 2.4) - 0.055)))
    return out


HUE = {10: (40, 90), 30: (315, 80), 50: (170, 80)}  # red, purple, green
SHADE = {r: lch_ramp(74, 22, h, c, n=len(TARGETS))[::-1] for r, (h, c) in HUE.items()}  # [0] = 5 ms, darkest


def main():
    d = main_results.load()
    d = d[d.btl_mbps == 100]

    left, right, gap, top, bottom, ph, key_room = 0.56, 0.10, 0.20, 0.06, 0.36, 1.0, 0.62  # inches
    pw = (W_IN - left - right - key_room - 2 * gap) / 3
    H = top + ph + bottom
    fig = plt.figure(figsize=(W_IN, H))
    axes = [fig.add_axes([(left + i * (pw + gap)) / W_IN, bottom / H, pw / W_IN, ph / H]) for i in range(3)]
    for i, (cc, label) in enumerate(CCS):
        ax = axes[i]
        ax.set_xlim(0, 0.4)
        ax.set_ylim(0, 1)
        ax.xaxis.set_major_locator(MultipleLocator(0.1))
        ax.xaxis.set_minor_locator(MultipleLocator(0.05))
        ax.xaxis.set_major_formatter(lambda v, _: "0" if v == 0 else f"{v:g}")
        ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0], labels=["0", "0.25", "0.5", "0.75", "1"])
        ax.tick_params(which="both", top=True, right=True, labelleft=i == 0, labelbottom=True)
        ax.axhline(0.5, zorder=1, **FAIR)
        for rtt in RTTS:
            g = d[(d.cc == cc) & (d.rtt_ms == rtt)].sort_values("target_ms")
            ax.plot(g.p, g.prague_share, color=SHADE[rtt][2], lw=0.9, zorder=3, clip_on=False)
        for rtt in RTTS:
            g = d[(d.cc == cc) & (d.rtt_ms == rtt)].sort_values("target_ms")
            ax.scatter(g.p, g.prague_share, s=MS ** 2, marker="o",
                       c=[SHADE[rtt][TARGETS.index(t)] for t in g.target_ms], zorder=4, clip_on=False, **EDGE)
        ax.text(0.97, 0.94, f"({'abc'[i]}) {label}", transform=ax.transAxes, ha="right", va="top", fontsize=9)
    axes[0].set_ylabel("Prague\nthroughput share", linespacing=1.0)
    h = [Line2D([], [], color=SHADE[r][2], lw=0.9, marker="o", ms=MS, mfc=SHADE[r][2], mec="0.12", mew=0.45,
                label=f"RTT {r} ms") for r in RTTS]
    h.append(Line2D([], [], label="Fair share", **FAIR))
    axes[0].legend(handles=h, loc="lower right", ncol=2, frameon=False, fontsize=7.5, handlelength=1.8,
                   handletextpad=0.4, columnspacing=0.8, labelspacing=0.3, borderaxespad=0.25)
    plot_right = right + key_room
    fig.text((left + (W_IN - left - plot_right) / 2) / W_IN, 0.04 / H, "Measured PI2 base probability $p$′",
             ha="center", va="bottom", fontsize=9)

    # colour key: one column per base RTT, one row per PI2 target
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
    fig.savefig(OUT, bbox_inches="tight", pad_inches=0.02)
    print(f"wrote {OUT.name}")


if __name__ == "__main__":
    main()
