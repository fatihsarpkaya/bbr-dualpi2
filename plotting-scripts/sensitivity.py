"""Sensitivity runs of Section V-B: mean p' of the fluid model (20-40 s, seed 1; five Classic flows alone, 100 Mbps,
8-BDP buffer) with one BBR constant changed, next to the same configuration with the original constant. Prints a table
(p_original, p_changed: mean p').

- Cwnd gain 3 instead of 2: BBR can queue one more BDP, so p' stays high until the PI2 target exceeds about two base
  RTTs instead of one.
- BBRv2 loss threshold 0.5 % instead of 2 %: BBRv2 reduces its inflight bounds at lower loss, and mean p' falls.
"""
import fluid_results

CHANGES = {"cwndgain3": "cwnd gain 3 (instead of 2)", "lossthreshold0.005": "loss threshold 0.5 % (instead of 2 %)"}
RUNS = ([("cwndgain3", "bbr1", rtt, t)
         for rtt, t in ((10, 15), (10, 25), (10, 50), (30, 50), (30, 75), (50, 75), (50, 150))]
        + [("cwndgain3", "bbr2", 30, t) for t in (50, 75)]
        + [("lossthreshold0.005", "bbr2", 30, t) for t in (5, 15)])
NAME = {"bbr1": "BBRv1", "bbr2": "BBRv2"}


def mean_pprime(cc, rtt, target, variant=None):
    return fluid_results.window_mean(*fluid_results.trace(cc, rtt, target, 1, variant))


def main():
    print(f"{'change':<38}{'CC':<7}{'RTT (ms)':>9}{'target (ms)':>12}{'target/RTT':>11}"
          f"{'p_original':>12}{'p_changed':>11}")
    for variant, cc, rtt, target in RUNS:
        p0, p1 = mean_pprime(cc, rtt, target), mean_pprime(cc, rtt, target, variant)
        ratio = f"  ({p0 / p1:.1f}x lower)" if variant == "lossthreshold0.005" else ""
        print(f"{CHANGES[variant]:<38}{NAME[cc]:<7}{rtt:>9}{target:>12}{target / rtt:>11.2f}{p0:>12.3f}{p1:>11.3f}{ratio}")


if __name__ == "__main__":
    main()
