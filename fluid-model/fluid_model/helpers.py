# Modified from the original fluid model (Scherrer et al., IMC 2022); see README.md.
import numpy as np
import math
import yaml 
import itertools
import random

from fluid_model.names import *

# --------------------------------------------------------------------------------------------------
# Helper functions

MSS = 1514

sharpness = 500

# Sigmoid function (numerically stable implementation)
sig = lambda x : 1/(1 + math.exp(-sharpness*x)) if x >= 0 else 1 - 1/(1 + math.exp(sharpness*x)) 

# Smooth sigmoid
smooth_sharpness = 5
smoothsig = lambda x : 1/(1 + math.exp(-smooth_sharpness*x)) if x >= 0 else 1 - 1/(1 + math.exp(smooth_sharpness*x))

# Indicator function (Discrete version of sigma)
idc = lambda x : 1 if x >= 0 else 0

# ReLU function
Gamma = lambda x : x * sig(x)

# Pulse function
P_sum = lambda x, phi, I , W : math.exp(-1/2 * ((x-phi*I)%(3*I))**2/(W/6)**2) + math.exp(-1/2 * ((phi*I-x)%(3*I))**2/(W/6)**2)

sigP = lambda x, start, end, I : sig((x/I)%3 - start) * sig(end - (x/I)%3)

# Transition function (optimized)
P = lambda x, phi, I, W, V : V / (math.sqrt(2*math.pi)*(W/6)) * P_sum(x, phi, I, W)



def get_environment(cmb, use_stdout_flag=True):

    env = {}

    env[N] = cmb[N]
    env[C] = cmb[C] * 1e6 / (MSS * 8 * 1000)

    env[DL] = cmb[DL]
    bdp = math.ceil((cmb[C]/8 * 1e6 * env[DL]/1000)/MSS)
    env[B] =  int(cmb[B] * bdp)

    env[CC] = []
    n_adopters_each_protocol = int(env[N]/len(cmb[CC]))
    for CC_prot in sorted(cmb[CC]):
        env[CC] += [CC_prot] * n_adopters_each_protocol

    random.seed(1)
    source_latency_range = cmb[SLR]
    env[SLR] = cmb[SLR]
    slr_length = source_latency_range[1] - source_latency_range[0]
    env[D] = []
    env[D0] = []
    for i in range(cmb[N]):
        d0_rand = float("%.1f" % random.uniform(source_latency_range[0], source_latency_range[1]))
        env[D0].append( d0_rand )
        env[D].append( 2*env[DL] + 2*d0_rand )

    env[AQM] = cmb[AQM]

    # PI2 parameters; the defaults are those of Linux DualPI2 (alpha = 0.16 Hz, beta = 3.2 Hz)
    if env[AQM] == PI2:
        env[PI2_TARGET]  = cmb.get(PI2_TARGET, 15.0)
        env[PI2_TUPDATE] = cmb.get(PI2_TUPDATE, 16.0)
        env[PI2_ALPHA]   = cmb.get(PI2_ALPHA, 41.0 / 256000.0)
        env[PI2_BETA]    = cmb.get(PI2_BETA, 819.0 / 256000.0)

    # BBR constants varied in the sensitivity runs; the defaults are the original model's
    env[CWND_GAIN]      = cmb.get(CWND_GAIN, 2)
    env[LOSS_THRESHOLD] = cmb.get(LOSS_THRESHOLD, 0.02)

    if (use_stdout_flag):
        print(env)

    return env



def parse_config(config_file_name):

    cfg = {vary: []}

    with open(config_file_name, 'r') as config_file:
        print(config_file_name)
        try:
            raw_config = yaml.safe_load(config_file)
        except yaml.YAMLError as exc:
            print("Invalid config file: ", exc)
            sys.exit(1)

    # Constant parameters
    cfg['name'] = raw_config['name']
    cfg[stp] = raw_config['model_parameters']['computation_parameters']['stp']
    cfg[T]   = int(raw_config['common_parameters']['send_duration'] * 1000 / cfg[stp])
    cfg[start] = int(raw_config['common_parameters']['truncate_front'] * 1000 / cfg[stp])
    cfg[end]   = int(cfg[T] - raw_config['common_parameters']['truncate_back']*1000 / cfg[stp])

    # Varying parameters
    varying_parameters = list(raw_config['varying_parameters'].keys())
    for prod_elem in itertools.product(*[raw_config['varying_parameters'][vp] for vp in varying_parameters]):
        prod_elem_map = {}
        for i in range(len(varying_parameters)):
            prod_elem_map[varying_parameters[i]] = prod_elem[i]
        cfg[vary].append(prod_elem_map)

    return cfg