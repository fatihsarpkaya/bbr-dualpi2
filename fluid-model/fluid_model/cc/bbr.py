# Modified from the original fluid model (Scherrer et al., IMC 2022); see README.md.
from fluid_model.names import *
from fluid_model.helpers import *

def bbr_update(cfg, env, state, i, t, lookback):

    step = cfg[stp]
    step_nr = int(t/step)

    tau_lookback = state[tau][i][lookback[tau]]
    tau2_lookback = state[tau][i][lookback[tau+tau]]

    t_net = t - state[tstr][i][-1]

    RTprop = state[tmin][i][lookback[tau]]

    if env[CC][i] == BBR:
        T_pbw = 8*RTprop
    elif env[CC][i] == BBR2:
        T_pbw = min(2000+i/env[N]*1000, 63*RTprop)

    # Delivery rate
    if state[y][lookback[p]] >= env[C] or state[q][lookback[tau+q]] > 0:
        xdel_wo_loss = state[x][i][lookback[x]] / state[y][lookback[p]] * env[C]
    else:
        xdel_wo_loss = state[x][i][lookback[x]]
    #state[xdel][i].append( state[xdel][i][-1] + step * (xdel_wo_loss - state[xdel][i][-1]) * 0.03 )
    state[xdel][i].append( xdel_wo_loss )

    # Check if ProbeRT mode should be entered/exited
    state[mprt][i].append( state[mprt][i][-1] + step * ( idc(-state[tprt][i][lookback[tau]]) * (idc(state[tmin][i][-1]-state[tmin][i][lookback[10]]) * (1-state[mprt][i][lookback[tau]]) - state[mprt][i][-1]) ) )
    state[tprt][i].append( state[tprt][i][-1] + step * ( idc(-state[tprt][i][lookback[tau]]) * (10000 - 9800 * idc(state[tmin][i][-1]-state[tmin][i][lookback[10]]) * (1-state[mprt][i][lookback[tau]]) - state[tprt][i][-1]) - 1 ) )

    # Is ProbeRT active?
    mprt_val = round(state[mprt][i][-1])

    # Is cwnd-limited mode active?
    mcrs_val = max(state[mcrs][i][-1], 0)

    # Is DOWN phase active?
    if env[CC][i] == BBR2:
        mdwn_val = max(state[mdwn][i][-1], 0)

    # Cwnd (inflight limit)
    bdp = state[xbtl][i][-1] * RTprop
    if env[CC][i] == BBR:
        w_prt = 4
        w_pbw = env[CWND_GAIN]*math.ceil(bdp)
    elif env[CC][i] == BBR2:
        w_prt = bdp/2
        w_pbw = min(env[CWND_GAIN]*math.ceil(bdp), min(state[wlo][i][-1], (1-mcrs_val*0.15)*state[whi][i][-1]) )
    state[w][i].append( (1-mprt_val) * w_pbw + mprt_val * w_prt )

    # Maximum measured delivery rate
    state[xmax][i].append( state[xmax][i][-1] + step * (1-mprt_val) * ( 5*Gamma(state[xdel][i][-1]-state[xmax][i][-1]) - sig(10 - t_net) * state[xmax][i][-1] ) )

    # Estimated bottleneck rate (set to maximum rate at end of period)
    xbtl_refresh_time = 7.0 if env[CC][i] == BBR else 0 #9.5 + math.floor(t_net/(10*RTprop)) * 10
    if env[CC][i] == BBR:
        state[xbtl][i].append( state[xbtl][i][-1] + step * (1-mprt_val) * ( sig(t_net - T_pbw + 10) * (state[xmax][i][-1]-state[xbtl][i][-1]) ) )
    elif env[CC][i] == BBR2:
        lookback_Tpbw = max(step_nr-int(T_pbw/step), 0)
        max_bw_sample = max(state[xmax][i][lookback_Tpbw], state[xmax][i][-1])
        dmdwn = state[mdwn][i][-1] #- state[mdwn][i][max(step_nr-2,0)]
        state[xbtl][i].append( state[xbtl][i][-1] + (1-mprt_val) * idc(dmdwn-0.1) * (max_bw_sample-state[xbtl][i][-1]) )

    # Cwnd adaptation based on mode
    dv_pbw = state[x][i][-1] - xdel_wo_loss
    if env[CC][i] == BBR:
         dv_pbw = dv_pbw #-0.1 * state[v][i][-1] / env[D][i]
    if env[CC][i] == BBR2:
        drain_target = min(bdp, 0.85*state[whi][i][-1])
        dv_pbw = (1-mcrs_val) * dv_pbw + mcrs_val * (drain_target - state[v][i][-1])
    dv_prt = state[w][i][-1] - state[v][i][-1]
    dv = (1-mprt_val) * dv_pbw + mprt_val * dv_prt
    state[v][i].append( max(state[v][i][-1] + step*dv, 0) )

    # Pacing rate adaptation based on mode
    x_ifl = state[w][i][-1] / state[tau][i][lookback[tau]]
    if env[CC][i] == BBR:
        phi_i = i % 6
        phase0 = 0.25 * smoothsig(t_net - phi_i*RTprop) * smoothsig((phi_i+1)*RTprop - t_net)
        phase1 = 0.25 * smoothsig(t_net - (phi_i+1)*RTprop) * smoothsig((phi_i+2)*RTprop - t_net)
    elif env[CC][i] == BBR2:
        drain_target = min(bdp, 0.85*state[whi][i][-1])
        dmdwn = (1-mcrs_val) * idc(t_net - RTprop) * min(idc(state[v][i][-1]-499/400*bdp)+idc(state[pc][lookback[p]]-env[LOSS_THRESHOLD]), 1) * (1 - state[mdwn][i][-1]) \
              - state[mdwn][i][-1] * min(idc(drain_target - state[v][i][-1]) + idc(t_net - 10*RTprop),1)
        state[mdwn][i].append( state[mdwn][i][-1] + dmdwn )
        phase0 = (1-mcrs_val) * sig(t_net - RTprop) * (1-state[mdwn][i][-1]) * (1/4)
        phase1 = state[mdwn][i][-1] * 1/4
    x_pcg = state[xbtl][i][-1] * (1 + phase0 - phase1)
    state[xpcg][i].append( x_pcg )
    x_pbw = min(x_ifl, x_pcg) #(1 - mcrs_val) * x_pcg + mcrs_val * min(x_ifl, x_pcg)
    x_prt = state[v][i][-1] / state[tau][i][-1]
    state[x][i].append( (1-mprt_val) * x_pbw + mprt_val * x_prt )

    # BBR2: Adapt inflight_hi and inflight_lo
    if env[CC][i] == BBR2:
        bdp = state[xbtl][i][-1] * RTprop
        # Max-adjust inflight_hi to current inflight, but decrease it in case of loss when probing for bandwidth
        dwhi = (1-mcrs_val) * idc(t_net - RTprop) * smoothsig(state[v][i][-1] - state[whi][i][-1]) * 2**(t_net/RTprop) \
             - (1-mcrs_val) * idc(state[pc][lookback[p]]-env[LOSS_THRESHOLD]) * 0.3/env[D][i] * state[whi][i][-1]
        state[whi][i].append( max(state[whi][i][-1] + step*dwhi, 1.15 * bdp)) #1.02*bdp) )
        # In probing phase, reset inflight_lo to base window; else, adjust downwards upon loss
        dwlo = (1-state[mcrs][i][-1]) * (state[whi][i][-1] - state[wlo][i][-1])/step \
             - mcrs_val * idc(state[pc][lookback[p]]-env[LOSS_THRESHOLD]) * -math.log(0.9)/env[D][i] * state[wlo][i][-1]
        state[wlo][i].append( state[wlo][i][-1] + step*dwlo )

    # BBR2: Check if we must enter/exit cruising mode
    if env[CC][i] == BBR2:
        dmcrs = (idc(-dmdwn-0.1) * (1 - mcrs_val) - idc(t_net - T_pbw) * mcrs_val ) / step
        state[mcrs][i].append( state[mcrs][i][-1] + step * dmcrs )

    # Adjust RTprop
    state[tmin][i].append( state[tmin][i][-1] + step * (-Gamma(state[tmin][i][-1] - tau_lookback)) )

    # Start time of period
    state[tstr][i].append( state[tstr][i][-1] + idc(t - state[tstr][i][-1] - T_pbw) * (t - state[tstr][i][-1]) )

    return state