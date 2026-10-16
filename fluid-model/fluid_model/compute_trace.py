# Modified from the original fluid model (Scherrer et al., IMC 2022); see README.md.
from fluid_model.names import *
from fluid_model.helpers import *
from fluid_model.cc import reno, cubic, bbr

import numpy as np
import time

c_cubic = 0.4
b_cubic = 0.7

inst = 0.5
loss_abruptness = 100

# --------------------------------------------------------------------------------------------------
# DE Models
def step_with_delay(cfg, env, state):

    step = cfg[stp]

    step_nr = len(state[q])

    # Queue size
    y_at_link = 0
    for i in range(env[N]):
        lookback_i = max(step_nr - int(round(env[D0][i]/step)), 0)
        y_at_link += state[x][i][lookback_i]

    state[q].append( min(max(0, state[q][-1] + ( (1-state[p][-1]) * y_at_link - env[C])*step), env[B]) )

    # Link flow
    state[y].append( y_at_link )

    t = step_nr * cfg[stp]

    for i in range(env[N]):

        # RTT
        state[tau][i].append( env[D][i] + state[q][-1] / env[C])

        # Cwnds
        lookback = {
            tau: max(step_nr - int(env[D][i]/step), 0),
            tau+tau: max(step_nr - int(2*env[D][i]/step), 0)
        }
        lookback[x] = max(step_nr - int(state[tau][i][lookback[tau]]/step), 0)
        lookback[p] = max(step_nr - int((state[tau][i][lookback[tau]]-env[D0][i])/step), 0)
        lookback[tau+q] = max(step_nr - int((env[D][i]-env[D0][i])/step), 0)
        lookback[10] = max(step_nr - int(10000/step), 0)

        if env[CC][i] == RENO:
            state = reno.reno_update(cfg, env, state, i, t, lookback)
        elif env[CC][i] == CUBIC:
            state = cubic.cubic_update(cfg, env, state, i, t, lookback)
        elif env[CC][i] == VEGAS:
            state = vegas.vegas_update(cfg, env, state, i, t, lookback)
        elif BBR in env[CC][i]:
            state = bbr.bbr_update(cfg, env, state, i, t, lookback)

    # Penalty
    if env[AQM] == RED:
        if env[N] > 1: # Instantaneous (Idealization)
            q_len = state[q][-1]
        else: # For traces
            q_len = state[q][max(step_nr-int(16/step), 0)]
        p_new = q_len / env[B]
        p_new = max(0, p_new)
        p_new = min(1, p_new)
        state[p].append( p_new )
        state[pc].append( p_new )
    elif env[AQM] == DROPTAIL:
        # --- Discrete
        p_new = (1 - env[C]/y_at_link) if (state[q][-1] == env[B] and y_at_link > env[C]) else 0
        p_new = max(0, min(p_new, 1))
        state[p].append( p_new )
        # --- Continuous
        p_new = (1 - env[C]/y_at_link) * (state[q][-1]/env[B])**loss_abruptness if y_at_link > env[C] else 0
        p_new = max(0, min(p_new, 1))
        state[pc].append( p_new )
    elif env[AQM] == PI2:
        # Every T_update, the base probability p' integrates the queueing-delay error and its change since the last
        # update (clipped to [0, 1]); in between, p' is held. Classic traffic is dropped with probability p'^2.
        qdelay = state[q][-1] / env[C]  # ms
        if step_nr > 0 and step_nr % int(round(env[PI2_TUPDATE] / step)) == 0:
            delta = env[PI2_ALPHA] * (qdelay - env[PI2_TARGET]) + env[PI2_BETA] * (qdelay - state[pi2_prev_qdelay])
            state[pprime].append( max(0.0, min(1.0, state[pprime][-1] + delta)) )
            state[pi2_prev_qdelay] = qdelay
        else:
            state[pprime].append( state[pprime][-1] )
        p_new = max(0.0, min(1.0, state[pprime][-1] ** 2))
        state[p].append( p_new )
        state[pc].append( p_new )



def generate_trace(cfg, cmb, env):

    # The only random draws are BBRv2's initial ProbeBW phase offsets (tstr below); a 'seed' parameter fixes them
    if SEED in cmb:
        random.seed(cmb[SEED])

    state       = {}
    state[w]    = [[env[D][i]*env[C]/env[N]] for i in range(env[N])]
    state[p]    = [0]
    state[pc]   = [0]
    state[q]    = [0]
    state[tau]  = [[env[D][i]] for i in range(env[N])]

    if CUBIC in env[CC]:
        state[wmax] = [[1.1*state[w][i][-1]] for i in range(env[N])]
        #state[s]    = [[10700] for _ in range(env[N])]
        state[s] = [[0] for _ in range(env[N])]
    if sum([1 if BBR in env[CC][i] else 0 for i in range(env[N])]) > 0:
        #state[w] = [[(0.5+random.random()*2.0)*state[w][i][0] if BBR == env[CC][i] else state[w][i][0]] for i in range(env[N])]
        state[tstr] = [[0] for i in range(env[N])]
        state[xmax] = [[state[w][i][0]/env[D][0]] for i in range(env[N])]
        state[xpcg] = [[state[w][i][0]/env[D][0]] for i in range(env[N])]
        state[xbtl] = [[state[w][i][0]/env[D][0]] for i in range(env[N])]
        state[xdel] = [[state[w][i][0]/env[D][0]] for i in range(env[N])]
        state[mcrs] = [[-1] for i in range(env[N])]
        state[tmin] = [[env[D][i]] for i in range(env[N])]
        state[tprt] = [[10000] for i in range(env[N])]
        state[mprt] = [[0] for i in range(env[N])]
        state[w]    = [[state[xbtl][i][0]*state[tmin][i][0]] if env[CC][i] == BBR else state[w][i] for i in range(env[N])]
    if BBR2 in env[CC]:
        state[tstr] = [[-10*env[D][i]-random.random()*1000] for i in range(env[N])]
        state[wlo]  = [[state[w][i][0]] for i in range(env[N])]
        state[whi]  = [[(1+2*max(cmb[B]-4,0)/4)*5/4*state[w][i][0]] for i in range(env[N])]
        state[mdwn] = [[0] for i in range(env[N])]
        state[mcrs] = [[1] for i in range(env[N])]
        state[tprt] = [[5000] if env[CC][i] == BBR2 else state[tprt][i] for i in range(env[N])]
    if env[AQM] == PI2:
        state[pprime] = [0.0]
        state[pi2_prev_qdelay] = 0.0

    state[v]    = [[state[w][i][0]] for i in range(env[N])]
    state[x]    = [[state[w][i][0]/env[D][i]] for i in range(env[N])]
    state[y]    = [sum([state[w][i][0]/env[D][i] for i in range(env[N])]) ]

    duration_sum = 0
    for i in range(cfg[T]-1):
        if (i % int(1000/cfg[stp])) == 0:
            print(str(i / int(1000/cfg[stp]))+'s')
        start = time.time()
        step_with_delay(cfg, env, state)
        duration_sum += time.time() - start

    return state
