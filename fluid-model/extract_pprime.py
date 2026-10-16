#!/usr/bin/env python3
"""Write p'(t) of each fluid-model run in results/ to ../Experiment_Data/fluid-model/<name>_seed<k>.csv.xz
(sensitivity runs, configs/sensitivity/, to ../Experiment_Data/fluid-model/sensitivity/).

Columns: time_ms (from the start of the run, 1-ms samples) and pprime (the PI2 base probability p'). These are the
files read by plotting-scripts/fluid_results.py. If a configuration was run more than once, its latest trace per
seed is used.

Usage: python extract_pprime.py [name ...]   (default: every configuration in configs/ and its subfolders)
"""
import json
import lzma
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIGS = HERE / 'configs'
OUT = HERE.parent / 'Experiment_Data' / 'fluid-model'


def extract(config):
    name, out = config.stem, OUT / config.parent.relative_to(CONFIGS)
    out.mkdir(parents=True, exist_ok=True)
    latest = {}
    for f in sorted((HERE / 'results' / name / 'fluid_model' / 'traces').glob('*.json')):  # timestamped: oldest first
        with open(f) as fh:
            d = json.load(fh)
        latest[d['seed']] = d
    for seed, d in sorted(latest.items()):
        ms = int(round(1 / d['stp']))  # steps per ms
        with lzma.open(out / ('%s_seed%s.csv.xz' % (name, seed)), 'wt') as fh:
            fh.write('time_ms,pprime\n')
            for k, v in zip(d['t_index'], d['pprime']):
                fh.write('%d,%r\n' % (k // ms, v / 100))
    return sorted(latest)


def main():
    configs = {f.stem: f for f in CONFIGS.rglob('*.yaml')}
    for name in sys.argv[1:] or sorted(configs):
        seeds = extract(configs[name])
        print('%s: %s' % (name, 'seeds %s' % seeds if seeds else 'no traces in results/'))


if __name__ == '__main__':
    main()
