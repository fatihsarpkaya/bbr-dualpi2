# Modified from the original fluid model (Scherrer et al., IMC 2022); see README.md.
RENO  = 'RENO'
CUBIC = 'CUBIC'
VEGAS = 'VEGAS'
BBR   = 'BBR'
BBR2  = 'BBR2'
PCC   = 'PCC'
PCCRENO = 'PCCRENO'
PCCVEGAS = 'PCCVEGAS'
PCCFLEX = 'PCCFLEX'

RED = 'RED'
DROPTAIL = 'Drop-tail'
PI2 = 'PI2'

# -----------------------------------------------------------
# Parameters
const = 'const'
vary = 'vary'
stp  = 'stp'
T = 'T'
start = 'start'
end = 'end'

N   = 'senders'
C   = 'link_capacity'
AQM = 'qdisc'
CC  = 'cc_combination'
B  = 'switch_buffer'
D   = 'D'
D0  = 'd0'
DL  = 'link_latency'
SLR = 'source_latency_range'
UFP = 'ufp'
SEED = 'seed'

# PI2 parameters
PI2_TARGET  = 'pi2_target'   # Target queueing delay (ms)
PI2_TUPDATE = 'pi2_tupdate'  # Update interval (ms)
PI2_ALPHA   = 'pi2_alpha'    # Gain on the queueing-delay error (per ms)
PI2_BETA    = 'pi2_beta'     # Gain on the queueing-delay change (per ms)

# Sensitivity parameters (defaults: the original model's constants)
CWND_GAIN      = 'bbr_cwnd_gain'        # BBRv1/BBRv2 ProbeBW cwnd gain (2)
LOSS_THRESHOLD = 'bbr2_loss_threshold'  # BBRv2 loss threshold on the drop probability (0.02)

# -----------------------------------------------------------
# State
q    = 'q'    # Queue length
w    = 'w'    # Cwnd size
v    = 'v'    # Inflight volume
tau  = 'tau'  # RTT
x    = 'x'    # Rate
y    = 'y'    # Total rate
p    = 'p'    # Loss probability
pc   = 'pc'   # Continous loss probability
pprime = 'pprime'  # PI2 base probability p'
pi2_prev_qdelay = 'pi2_prev_qdelay'  # Queueing delay at the last PI2 update (ms)

wmax_last = 'wmax_last'
wmax = 'wmax' # Cwnd size at time of last loss (CUBIC)
s    = 's'    # Time since last loss (CUBIC)    

tstr = 'tstr' # Start time of period
xpcg = 'xpcg' # Pacing rate
xmax = 'xmax' # Maximum rate measured within one cycle (BBR)
xbtl = 'xbtl' # Estimated bottleneck bandwidth (BBR)
xdel = 'xdel' # Delivery rate
mcrs = 'mcrs' # Cwnd-limited mode
tmin = 'tmin' # RTprop
tprt = 'tprt' # ProbeRT timer (Time until next evaluation)
mprt = 'mprt' # ProbeRT mode
wlo  = 'wlo'  # inflight_lo
whi  = 'whi'  # inflight_hi
mdwn = 'mdwn'  # Probe-bandwidth phase
util = 'util'
utl1 = 'u1'
utl2 = 'u2'
gmma = 'gmma'