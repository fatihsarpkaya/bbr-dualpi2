from fluid_model.names import *

def reno_update(cfg, env, state, i, t, lookback):

    step = cfg[stp]

    # Window size
    ack_rate  = state[x][i][lookback[x]] * (1-state[p][lookback[p]])
    loss_rate = state[x][i][lookback[x]] * state[p][lookback[p]]
    w_new = state[w][i][-1] + step * (ack_rate / state[w][i][-1] - loss_rate * state[w][i][-1]/2)
    w_new = max(1, w_new)
    state[w][i].append(w_new)
    
    # Rate
    state[x][i].append( state[w][i][-1]/state[tau][i][-1] )

    return state