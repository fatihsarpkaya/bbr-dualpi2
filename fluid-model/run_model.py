#!/usr/bin/python3
# Modified from the original fluid model (Scherrer et al., IMC 2022); see README.md.

from fluid_model.names import *
from fluid_model.compute_trace import *
from fluid_model.process_trace import *
from fluid_model.cc import reno
from fluid_model.helpers import *

import sys
import os
import argparse
import random
import copy
import string

from datetime import datetime

# -----------------------------------------------------------------------------
# Use Python implementation for computing trace (slow but easy to debug)
def run_model_for_config(cfg, dump_trace_flag=True, plot_trace_flag=False):

    analysis_results = []
    result_file_name = cfg['result_folder'] + datetime.strftime(datetime.now(), "%Y-%m-%d--%H-%M-%S") + '.json'

    if not os.path.exists(cfg['result_folder'] + 'traces/'):
        os.mkdir(cfg['result_folder'] + 'traces/')

    for cmb in cfg[vary]:

        env = get_environment(cmb)

        state = generate_trace(cfg, cmb,env)

        trace_file_name = cfg['result_folder'] + 'traces/' + datetime.strftime(datetime.now(), "%Y-%m-%d--%H-%M-%S-%f") + '.json'

        # Dump aggregate statistics
        analysis_results.append( {**cmb, **(analyze_trace(cfg, env, state, trace_file_name))} )
        with open(result_file_name, 'w+') as result_file:
            json.dump(analysis_results, result_file, indent=4)

        # Dump trace
        if dump_trace_flag:
            dump_trace(cfg, cmb, env, state, trace_file_name)
        if plot_trace_flag:
            plot_trace(cfg, cmb, env, state, cfg['result_folder'])    

        # Free this run's state before the next combination (e.g. the next seed) is computed
        del state

    return analysis_results


def main():

    parser = argparse.ArgumentParser(description='Run fluid model.')

    parser.add_argument('-c', '--config',   required=True)
    parser.add_argument('--plot-trace', action='store_true', help='also plot each trace (needs a LaTeX installation)')
    args = parser.parse_args()

    cfg = parse_config(args.config)

    result_folder = 'results/'
    if not os.path.exists(result_folder):
        os.mkdir(result_folder)
    result_folder += cfg['name'] + '/'
    if not os.path.exists(result_folder):
        os.mkdir(result_folder)
    result_folder += 'fluid_model/'
    if not os.path.exists(result_folder):
        os.mkdir(result_folder)

    cfg['result_folder'] = result_folder

    run_model_for_config(cfg, plot_trace_flag=args.plot_trace)


if __name__ == '__main__':
    main()
