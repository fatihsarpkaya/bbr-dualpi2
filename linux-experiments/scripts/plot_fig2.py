"""Paper Figure 2: normalized Prague throughput with five Prague and five CUBIC, BBRv2 or BBRv1 flows under DualPI2.

Rows = Classic CC (CUBIC, BBRv2, BBRv1), columns = bottleneck capacity (100, 500 Mbps); in each panel
x = PI2 delay target, y = base RTT. Cell value (colour and printed number) = Prague throughput / capacity over the
last 60 s of the run, mean of three trials (results/coexistence_cells.csv `prague_share`, written by
summarize_coexistence.py). Colour: coolwarm, blue = low, light grey = 0.5 (equal share), red = high.
Writes figures/fig2_prague_share.{pdf,png}. Usage: python plot_fig2.py
"""
import logging
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent.parent
CELLS = HERE / "results" / "coexistence_cells.csv"
OUT = HERE / "figures" / "fig2_prague_share"

CCS = [("cubic", "CUBIC"), ("bbr2", "BBRv2"), ("bbr1", "BBRv1")]  # rows, top to bottom
BTLS = [(100, "100 Mbps"), (500, "500 Mbps")]  # columns
TARGETS = [5, 15, 25, 50, 75]
RTTS = [10, 30, 50]  # bottom to top
CMAP = mpl.colormaps["coolwarm"].with_extremes(bad="white")
NORM = mpl.colors.Normalize(0.0, 1.0)
CELL_FONTSIZE = 6.5

logging.getLogger("fontTools").setLevel(logging.ERROR)  # PDF font-subsetting chatter
mpl.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "Times", "DejaVu Serif"], "mathtext.fontset": "stix",
    "pdf.fonttype": 42, "ps.fonttype": 42,  # embed TrueType fonts (IEEE PDF eXpress rejects Type 3)
    "font.size": 8, "axes.labelsize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8,
    "hatch.linewidth": 0.5, "axes.linewidth": 0.0,
})


def text_color(value):
    """Black, unless white contrasts clearly more with the cell colour (>= 1.2 x black's contrast ratio)."""
    c = np.asarray(CMAP(NORM(value))[:3])
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    lum = 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    return "white" if 1.05 / (lum + 0.05) >= 1.2 * (lum + 0.05) / 0.05 else "black"


def draw(ax, grid):
    ny, nx = grid.shape
    ax.pcolormesh(np.arange(nx + 1), np.arange(ny + 1), np.ma.masked_invalid(grid), cmap=CMAP, norm=NORM,
                  edgecolors="white", linewidth=0.6)
    for i, j in zip(*np.where(np.isfinite(grid))):
        ax.text(j + 0.5, i + 0.5, f"{grid[i, j]:.2f}", ha="center", va="center", fontsize=CELL_FONTSIZE,
                color=text_color(grid[i, j]))
    ax.set_xlim(0, nx)
    ax.set_ylim(0, ny)
    ax.set_xticks(np.arange(nx) + 0.5)
    ax.set_yticks(np.arange(ny) + 0.5)
    ax.tick_params(length=0, pad=2)
    ax.set_xticklabels([])
    ax.set_yticklabels([])


def main():
    c = pd.read_csv(CELLS)
    if len(c) != 90 or not (c.trials == 3).all():
        raise SystemExit(f"expected 90 configurations with 3 trials each, got {len(c)}, trials {sorted(c.trials.unique())}")
    m = {(r.cc, r.btl_mbps, r.rtt_ms, r.target_ms): r.prague_share for r in c.itertuples()}

    # Geometry in inches for an IEEE single column (\columnwidth = 3.5 in)
    W, left, gap_x, gap_y, top, bottom = 3.5, 0.60, 0.07, 0.07, 0.22, 0.42
    cb_gap, cb_w, cb_room = 0.10, 0.08, 0.42  # gap to the colorbar, bar width, room for its ticks and label
    pw = (W - left - gap_x - cb_gap - cb_w - cb_room) / 2
    ph = pw / len(TARGETS) * len(RTTS)  # square cells
    H = top + 3 * ph + 2 * gap_y + bottom
    fig = plt.figure(figsize=(W, H))
    for r, (cc, cc_label) in enumerate(CCS):
        y0 = bottom + (len(CCS) - 1 - r) * (ph + gap_y)
        for col, (btl, btl_label) in enumerate(BTLS):
            ax = fig.add_axes([(left + col * (pw + gap_x)) / W, y0 / H, pw / W, ph / H])
            grid = np.array([[m.get((cc, btl, rtt, t), np.nan) for t in TARGETS] for rtt in RTTS])
            assert np.isfinite(grid).all(), f"missing configuration in {cc} {btl} Mbps"
            draw(ax, grid)
            if r == 0:
                ax.set_title(btl_label, fontsize=9, fontweight="bold", pad=4)
            if r == len(CCS) - 1:
                ax.set_xticklabels([str(t) for t in TARGETS])
            if col == 0:
                ax.set_yticklabels([str(t) for t in RTTS])
        fig.text(0.08 / W, (y0 + ph / 2) / H, cc_label, rotation=90, ha="center", va="center", fontsize=9,
                 fontweight="bold")
    grid_h = 3 * ph + 2 * gap_y
    fig.text(0.29 / W, (bottom + grid_h / 2) / H, "Base RTT (ms)", rotation=90, ha="center", va="center", fontsize=9)
    fig.text((left + pw + gap_x / 2) / W, (bottom - 0.30) / H, "PI2 delay target (ms)", ha="center", va="center",
             fontsize=9)
    cax = fig.add_axes([(left + 2 * pw + gap_x + cb_gap) / W, bottom / H, cb_w / W, grid_h / H])
    cb = fig.colorbar(mpl.cm.ScalarMappable(norm=NORM, cmap=CMAP), cax=cax, orientation="vertical")
    cb.set_ticks([0, 0.25, 0.5, 0.75, 1.0], labels=["0", "0.25", "0.5", "0.75", "1"])
    cb.ax.tick_params(length=2, width=0.5, pad=1.5, labelsize=8)
    cb.outline.set_linewidth(0.5)
    cb.set_label("Prague throughput share", fontsize=9, labelpad=3)

    OUT.parent.mkdir(exist_ok=True)
    fig.savefig(OUT.with_suffix(".pdf"), bbox_inches="tight", pad_inches=0.02)
    fig.savefig(OUT.with_suffix(".png"), dpi=300, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print(f"wrote figures/{OUT.name}.pdf and .png")


if __name__ == "__main__":
    main()
