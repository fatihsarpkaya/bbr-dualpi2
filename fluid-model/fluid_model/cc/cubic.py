from fluid_model.names import *
from fluid_model.helpers import *

c_cubic = 0.4
b_cubic = 0.7

def cubic_update(cfg, env, state, i, t, lookback):

  step = cfg[stp]

  # ----- Parameters
  s_unit = 1000
  s_offset =  2.0

  # ----- Window computation
  wmax_new = state[wmax][i][-1] + step * idc(state[p][lookback[p]] - 1e-6) * (state[w][i][lookback[tau+tau]] - state[wmax][i][-1])
  state[wmax][i].append( wmax_new )
  s_new = state[s][i][-1] + step * (1 - idc(state[p][lookback[p]] - 1e-6) * state[s][i][-1])
  state[s][i].append( s_new )
  cubic_function = state[s][i][-1]/s_unit + s_offset - (wmax_new*b_cubic/c_cubic)**(1/3)
  w_new = c_cubic * cubic_function**3 + state[wmax][i][-1]

  w_new = max(1, w_new)
  state[w][i].append(w_new)
  
  # Rate
  state[x][i].append( state[w][i][-1]/state[tau][i][-1] )

  return state