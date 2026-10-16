"""Figure 4: the Classic-side PI2 signal in Linux and in the PI2-extended fluid model, five Classic flows without
Prague, 100 Mbps, 8-BDP buffer. Writes Plots/fig4a.pdf and Plots/fig4b.pdf.

(a) p'(t) at 50 ms base RTT and a 15 ms PI2 target. Fluid model: 20-40 s of the run (for BBRv2 the seed whose mean is
    closest to the seed mean). Linux CUBIC: 20-40 s of the 60-s run whose mean is closest to the trial mean. Linux
    BBRv1/BBRv2: the 20-s window of the 180-s runs (any trial, starting from 20 s) closest to the model trace above it:
    for BBRv1, whose model p' holds a steady level, the smallest Wasserstein-1 distance between the p' samples; for
    BBRv2, whose model p' oscillates, the smallest RMS distance between autocorrelation functions (lags up to 6 s).
(b) Mean p': fluid model over 20-40 s (averaged over seeds), Linux over the last 60 s of the 180-s runs (averaged
    over trials).
"""
import logging
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap, Normalize, to_rgb
from matplotlib.patches import Rectangle

import classic_alone
import fluid_results

PLOTS = Path(__file__).resolve().parent.parent / "Plots"
W, H = 3.45, 2.05  # inches; each subfigure is half the text width
CCS = [("cubic", "CUBIC"), ("bbr1", "BBRv1"), ("bbr2", "BBRv2")]
RTTS, TARGETS = [10, 30, 50], [5, 15, 25, 50, 75]
RTT, TARGET, WIN = 50, 15, 20.0  # (a): configuration and window length (s)
T0, T1 = fluid_results.T0, fluid_results.T1
FLUID_COLOR, EXPER_COLOR = "#3B6CB7", "#C44E52"
CMAP = ListedColormap(mpl.colormaps["plasma"](np.linspace(0.80, 0.10, 256)))  # p' = 0 orange, high p' purple
NORM = Normalize(0, 0.45)

logging.getLogger("fontTools").setLevel(logging.ERROR)
mpl.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "Times", "STIXGeneral", "DejaVu Serif"],
    "mathtext.fontset": "cm", "pdf.fonttype": 42, "ps.fonttype": 42,
    "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 7.5, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
})
STYLE_A = {"axes.edgecolor": "#52514e", "axes.labelcolor": "#0b0b0b", "text.color": "#0b0b0b",
           "xtick.color": "#52514e", "ytick.color": "#52514e", "axes.spines.top": False, "axes.spines.right": False,
           "xtick.major.size": 2.5, "ytick.major.size": 2.5, "xtick.major.pad": 2, "ytick.major.pad": 2}
STYLE_B = {"axes.titlepad": 2, "xtick.major.pad": 1.5, "ytick.major.pad": 1.5}


def closest_to_mean(runs):
    """The (t, p) run whose 20-40 s mean is closest to the mean over the runs."""
    m = np.array([p[(t >= T0) & (t < T1)].mean() for t, p in runs])
    return runs[int(np.argmin(np.abs(m - m.mean())))]


def w1(a, b, q=np.linspace(0.0005, 0.9995, 1000)):
    """Wasserstein-1 distance between two samples."""
    return float(np.mean(np.abs(np.quantile(a, q) - np.quantile(b, q))))


def acf(x, lags=60):
    x = x - x.mean()
    return np.array([(x[:len(x) - k] * x[k:]).sum() for k in range(lags + 1)]) / (x * x).sum()


def best_window(cc, ref):
    """Trial and start (s) of the 20-s window of the 180-s Linux runs closest to the model's 20-40 s (1-ms samples)."""
    dt = 0.1  # s, autocorrelation grid
    if cc == "bbr2":
        step, a_ref = 0.5, acf(np.interp(np.arange(0, WIN, dt), np.arange(len(ref)) * 0.001, ref))
        dist = lambda t, p, s: np.sqrt(np.mean((acf(np.interp(np.arange(s, s + WIN, dt), t, p))[1:] - a_ref[1:]) ** 2))  # noqa: E731
    else:
        step = 1.0
        dist = lambda t, p, s: w1(p[(t >= s) & (t < s + WIN)], ref)  # noqa: E731
    best = None
    for trial in classic_alone.TRIALS_180:
        t, p, end = classic_alone.trace_180s(cc, RTT, TARGET, trial)
        for s in np.arange(20.0, end - WIN + 1e-9, step):
            d = dist(t, p, s)
            if best is None or d < best[0]:
                best = (d, trial, s, t, p)
    return best[1:]


def fig4a():
    fig, axes = plt.subplots(2, 3, figsize=(W, H), sharex=True, sharey=True)
    for col, (cc, label) in enumerate(CCS):
        tf, pf = closest_to_mean([fluid_results.trace(cc, RTT, TARGET, s) for s in fluid_results.SEEDS[cc]])
        win = (tf >= T0) & (tf <= T1)
        pf_win = pf[(tf >= T0) & (tf < T1)]
        if cc == "cubic":
            tl, pl = closest_to_mean([classic_alone.trace_60s(cc, RTT, TARGET, k) for k in classic_alone.TRIALS_60])
            trial, lo = None, T0
        else:
            trial, lo, tl, pl = best_window(cc, pf_win)
        m = (tl >= lo - 0.2) & (tl <= lo + WIN + 0.2)  # one sample beyond each edge so the line spans the window
        rows = ((tf[win][::5] - T0, pf[win][::5], FLUID_COLOR, "Fluid model"),  # model every 5 ms
                (tl[m] - lo, pl[m], EXPER_COLOR, "Experiment"))
        for row, (t, p, color, source) in enumerate(rows):
            ax = axes[row, col]
            ax.plot(t, p, color=color, lw=0.9, solid_joinstyle="round", clip_on=True)
            ax.set_title(f"{source}: {label}", pad=2)
            ax.grid(True, which="major", lw=0.4, alpha=0.5)
        if pf_win.max() < 0.02:  # the model's CUBIC p' is ~0: say so
            axes[0, col].text(WIN / 2, 0.035, r"max $p'$ = %.4f" % pf_win.max(), ha="center", va="bottom",
                              fontsize=6.5, style="italic", color="#444444")
        print(f"{label}: Linux {'60-s run, 20-40 s' if trial is None else f'trial {trial}, {lo:.1f}-{lo + WIN:.1f} s'}")
    for ax in axes.flat:
        ax.set_xlim(0, WIN)
        ax.set_ylim(-0.012, 0.6)
        ax.set_xticks([0, 5, 10, 15, 20])
        ax.set_yticks([0, 0.3, 0.6], labels=["0", "0.3", "0.6"])
    for row in range(2):
        axes[row, 0].set_ylabel(r"$p'$", labelpad=2)
    for col in range(3):
        axes[1, col].set_xlabel("Time (s)", labelpad=1)
    fig.tight_layout(pad=0.15, w_pad=0.25, h_pad=0.35)
    # place the two rows of panels at the heights of the two heatmap rows in (b)
    top, bottom, gap = 0.8733, 0.153, 0.105
    ph = (top - bottom - gap) / 2
    for (row, _), ax in zip(np.ndindex(2, 3), axes.flat):
        x0, _, w, _ = ax.get_position().bounds
        ax.set_position([x0, (top, bottom + ph)[row] - ph, w, ph])
    fig.savefig(PLOTS / "fig4a.pdf")
    plt.close(fig)


def text_color(rgb):
    """Black or white, whichever contrasts more with the cell colour."""
    r, g, b = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb[:3]]
    return "white" if 0.2126 * r + 0.7152 * g + 0.0722 * b < 0.18 else "black"


def fig4b():
    value = {(source, cc, rtt, t): load(cc, rtt, t) for source, load in
             (("fluid", fluid_results.mean_pprime), ("linux", classic_alone.mean_pprime))
             for cc in ("bbr1", "bbr2") for rtt in RTTS for t in TARGETS}
    fig = plt.figure(figsize=(W, H))
    left, mid, right, gap = 0.088, 0.016, 0.858, 0.04  # gap: white space around each cell (cell units)
    pw, ph, tops = (right - left - mid) / 2, 0.315, [0.875, 0.455]
    for k, (source, source_label) in enumerate([("fluid", "Fluid model"), ("linux", "Experiment")]):
        for c, (cc, cc_label) in enumerate([("bbr1", "BBRv1"), ("bbr2", "BBRv2")]):
            ax = fig.add_axes([left + c * (pw + mid), tops[k] - ph, pw, ph])
            for i, rtt in enumerate(RTTS):
                for j, t in enumerate(TARGETS):
                    v = value[(source, cc, rtt, t)]
                    rgb = CMAP(NORM(v))
                    ax.add_patch(Rectangle((j + gap, i + gap), 1 - 2 * gap, 1 - 2 * gap, facecolor=rgb, lw=0))
                    ax.text(j + 0.5, i + 0.53, f"{v:.2f}".replace("0.", ".", 1), ha="center", va="center",
                            fontsize=7.0, color=text_color(to_rgb(rgb)))
            ax.set_xlim(0, len(TARGETS))
            ax.set_ylim(len(RTTS), 0)
            ax.set_xticks(np.arange(len(TARGETS)) + 0.5, labels=[str(t) for t in TARGETS] if k == 1 else [])
            ax.tick_params(length=0)
            for s in ax.spines.values():
                s.set_visible(False)
            if c == 0:
                ax.set_yticks(np.arange(len(RTTS)) + 0.5, labels=[str(r) for r in RTTS])
            else:
                ax.set_yticks([])
            ax.set_title(f"{source_label}: {cc_label}", loc="left", fontsize=7)
    cb = fig.colorbar(mpl.cm.ScalarMappable(norm=NORM, cmap=CMAP),
                      cax=fig.add_axes([right + 0.022, tops[1] - ph, 0.022, tops[0] - tops[1] + ph]))
    cb.set_ticks([0, 0.1, 0.2, 0.3, 0.4])
    cb.ax.tick_params(labelsize=6.5, length=1.8, width=0.5, pad=1)
    cb.outline.set_linewidth(0.4)
    cb.set_label(r"Mean $p'$", fontsize=7, labelpad=2)
    fig.text((left + right) / 2, 0.025, "PI2 target (ms)", ha="center", va="bottom", fontsize=7.5)
    fig.text(0.018, (tops[0] + tops[1] - ph) / 2, "Base RTT (ms)", rotation=90, ha="center", va="center",
             fontsize=7.5)
    fig.savefig(PLOTS / "fig4b.pdf")
    plt.close(fig)


def main():
    with mpl.rc_context(STYLE_A):
        fig4a()
    with mpl.rc_context(STYLE_B):
        fig4b()
    print("wrote fig4a.pdf, fig4b.pdf")


if __name__ == "__main__":
    main()
