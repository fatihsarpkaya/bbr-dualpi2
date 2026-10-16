# Modified from the original fluid model (Scherrer et al., IMC 2022); see README.md.
import matplotlib.pyplot as plt
import numpy as np
import json

from fluid_model.names import *

COLORS =    {
                w:    (0.36, 0.54, 0.66),
                x:    (0.54, 0.81, 0.94),
                y:    (0.00, 0.50, 1.00),
                q:    (1.00, 0.60, 0.40),
                p:    (1.00, 0.13, 0.32),
                tau:  (0.00, 0.42, 0.24),
                wmax: (0.54, 0.17, 0.89),
                xpcg: (0.44, 0.10, 0.10),
                xmax: (0.96, 0.73, 1.00),
                xbtl: (0.98, 0.38, 0.50),
                s:    (0.38, 0.98, 0.50)
            }


LINESTYLES = { 
                RENO:     '-', 
                CUBIC:    (0, (1, 1)), 
                BBR:      (0, (5, 1)), 
                BBR2:     (0, (3,2)), 
                PCC:      (0, (4, 2)), 
                VEGAS:    (1, (1, 1)), 
                PCCVEGAS: (0, (4, 2)), 
                PCCRENO:  (0, (4, 2)),
                PCCFLEX:  (0, (4, 2))
            }


MSS = 1514
MSSms_to_Mbps = MSS*8*1000/1e6

plt.rc('text', usetex=True)
plt.rc('font', family='serif')
plt.rcParams['text.latex.preamble'] = r'\usepackage{amsmath}' + '\n' + r'\usepackage{amssymb}'

# Analyze trace
def analyze_trace(cfg, env, state, trace_file_name):

    analysis_results = {'trace_file': trace_file_name}

    t_range = range(cfg[start], cfg[end])

    # Queuing delay
    analysis_results['avg_queue'] =  np.mean(state[q][cfg[start]:cfg[end]])

    # Jitter (difference b/w consecutive delay samples that are done each msec)
    lat_jumps = []
    measure_index = cfg[start] + int(1/cfg[stp])
    while measure_index < cfg[end]:
        lat_jumps.append( np.abs(state[tau][0][measure_index] - state[tau][0][measure_index - int(1/cfg[stp])]) )
        measure_index += int(1/cfg[stp])
    analysis_results['avg_jitter'] = np.mean(lat_jumps)

    # Fairness
    sent_vols = [sum([state[x][i][t]/(env[C]/env[N]) for t in t_range]) for i in range(env[N])]
    analysis_results['jain_fairness_index'] =  sum(sent_vols)**2 / (env[N] * sum([sent_vol**2 for sent_vol in sent_vols]))

    # Loss
    dropped_volume = sum([state[pc][t]*state[y][t]*cfg[stp] for t in t_range])
    sent_volume    = sum([state[y][t]*cfg[stp]              for t in t_range])
    analysis_results['loss'] = dropped_volume/sent_volume

    # Utilization
    analysis_results['utilization'] = np.mean([min(state[y][t]/env[C], 1) if state[q][t] <= 0 else 1 for t in t_range])

    return analysis_results



def dump_trace(cfg, cmb, env, state, trace_file_name):

    t_range = [i for i in range(cfg[T]) if (i >= cfg[start] and i <= cfg[end] and i % int(1/cfg[stp]) == 0)]

    state[p]   = [pt*100 for pt in state[pc]]

    delay_ndv = len({env[D][i]:0 for i in range(env[N])}.keys())

    state[y]   = [state[y][t]/env[C]*100 for t in t_range]
    state[q]   = [state[q][t]/env[B]*100 for t in t_range]
    state[p]   = [state[p][t] for t in t_range]
    state[tau] = [state[tau][0][t] for t in t_range]

    dump_data = {   
                    'senders': env[N], 
                    'link_capacity': env[C]*MSSms_to_Mbps, 
                    'link_latency': env[DL], 
                    'cc_combination': env[CC], 
                    'switch_buffer': cmb[B],
                    'qdisc': env[AQM],
                    'source_latency_range': env[SLR],
                    y: state[y],
                    q: state[q],
                    p: state[p],
                    tau: state[tau],
                    stp: cfg[stp],
                    't_index': t_range,
                    SEED: cmb.get(SEED),
                }

    # PI2: base probability p' (in %, like p)
    if env[AQM] == PI2:
        dump_data[pprime] = [state[pprime][t]*100 for t in t_range]
        dump_data[PI2_TARGET] = env[PI2_TARGET]

    for i in range(env[N]):

        intensity =  (env[D][i]-min(env[D])+1)/(max(env[D])-min(env[D])+1)

        state[x][i] = [state[x][i][t]/env[C]*100 for t in t_range]
        dump_data[x+'_'+str(i)] = state[x][i]

        dump_data[w+'_'+str(i)] = [state[w][i][t] for t in t_range]

        if env[CC][i] == CUBIC:
            dump_data[s+'_'+str(i)] = [state[s][i][t]/(cfg[T]/cfg[stp])*100 for t in t_range]
            dump_data[wmax+'_'+str(i)] = [state[wmax][i][t] for t in t_range]
        elif BBR in env[CC][i]:
            dump_data[xbtl+'_'+str(i)] = [state[xbtl][i][t]/env[C]*100 for t in t_range]
            dump_data[xpcg+'_'+str(i)] = [state[xpcg][i][t]/env[C]*100 for t in t_range]
            dump_data[xmax+'_'+str(i)] = [state[xmax][i][t]/env[C]*100 for t in t_range]
            dump_data[xdel+'_'+str(i)] = [state[xdel][i][t]/env[C]*100 for t in t_range]
            dump_data[v+'_'+str(i)]    = [state[v][i][t] for t in t_range]
            dump_data[tstr+'_'+str(i)] = [state[tstr][i][t]/(cfg[end]*cfg[stp])*100 for t in t_range]
            dump_data[tmin+'_'+str(i)] = [(state[tmin][i][t]/env[D][i]-1)*100 for t in t_range]
            dump_data[mprt+'_'+str(i)] = [state[mprt][i][t]*100 for t in t_range]
            dump_data[tprt+'_'+str(i)] = [state[tprt][i][t]/10000*100 for t in t_range]
            if env[CC][i] == BBR2:
                dump_data[wlo+'_'+str(i)] = [state[wlo][i][t] for t in t_range]
                dump_data[whi+'_'+str(i)] = [state[whi][i][t] for t in t_range]
                dump_data[mdwn+'_'+str(i)] = [state[mdwn][i][t]*100 for t in t_range]
                dump_data[mcrs+'_'+str(i)] = [state[mcrs][i][t]*100 for t in t_range]
        elif PCC in env[CC][i]:
            utils = [state[util][i][t] for t in t_range]
            max_util = max(utils)
            dump_data[util+'_'+str(i)] = [u/max_util*100 for u in utils]
            dump_data[utl1+'_'+str(i)] = [state[utl1][i][t]*100 for t in t_range]
            dump_data[utl2+'_'+str(i)] = [state[utl2][i][t]*100 for t in t_range]
            gmmas = [state[gmma][i][t]*10 for t in t_range]
            max_gmma = max(gmmas)
            dump_data[gmma+'_'+str(i)] = [g/max_gmma*100 for g in gmmas]
            dump_data[xbtl+'_'+str(i)] = [state[xbtl][i][t]/env[C]*100 for t in t_range]

    with open(trace_file_name, 'w+') as result_file:
        json.dump(dump_data, result_file, indent=4)



def plot_trace(cfg, cmb, env, state, plot_folder_name):

    fig = plt.figure(figsize=(6, 8))
    ax  = plt.gca()

    t_range = [i for i in range(cfg[T]) if (i >= cfg[start] and i <= cfg[end] and i % int(1/cfg[stp]) == 0)]

    y_line   = plt.plot(t_range, state[y],   color=COLORS[y],   linewidth=0.5, label=r'Total rate')
    q_line   = plt.plot(t_range, state[q],   color=COLORS[q],   linewidth=0.5, label=r'Buffering (\%)')
    p_line   = plt.plot(t_range, state[p],   color=COLORS[p],   linewidth=0.5, label=r'Loss rate')
    tau_line = plt.plot(t_range, state[tau], color=COLORS[tau], linewidth=0.5, label=r'RTT')

    x_lines = {}
    for i in range(env[N]):
        intensity =  (env[D][i]-min(env[D])+1)/(max(env[D])-min(env[D])+1)
        x_lines[env[CC][i]] = plt.plot(t_range, state[x][i], color=[c*intensity for c in COLORS[x]], \
                                  linestyle=LINESTYLES[env[CC][i]], linewidth=0.5)
    for CC_protocol in x_lines.keys():
        x_lines[CC_protocol][0].set_label(r'Single rate ('+CC_protocol+r') (\%)')

    plt.plot([t_range[0], t_range[-1]], [100, 100], '--')

    xticks = [cfg[start] + i*(cfg[end] - cfg[start])/5 for i in range(6)]
    plt.xticks(xticks, labels=['%dms' % int(xtick*cfg[stp]) for xtick in xticks])

    plt.tight_layout()
    plt.subplots_adjust(bottom=0.1, top=0.9)
    CC_summary_string = '-'.join([CC_prot+':'+str(int(cmb[N]/len(cmb[CC]))) for CC_prot in cmb[CC]])
    plt.title(str(cmb[N])+' senders, ' + \
              'Protocols '+CC_summary_string+'\n' + \
              ("Bottleneck capacity %.2f Gbps, " % cmb[C]) + \
              'Buffer '+str(cmb[B])+' BDP\n' + \
              'Propagation delay '+str(env[D])+r'ms', y=1.0)
    plt.figlegend(ncol=3, loc='lower center')
    cmb_summary_string = CC_summary_string + '-' + '-'.join([k+":"+str(cmb[k]) for k in cmb.keys() if k != CC]).replace(' ', '')
    plt.savefig(plot_folder_name + cmb_summary_string + '.pdf')
    plt.close()