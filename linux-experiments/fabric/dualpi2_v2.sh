#!/usr/bin/env bash
# dualpi2_v2.sh: poll DualPI2 stats (same usage and first six columns as dualpi2.sh, plus the mark/drop counters).
# Usage: ./dualpi2_v2.sh [logfile] [time_limit_in_seconds] [iface]
#
# Columns:
#   timestamp prob_raw pkts_in_c pkts_in_l delay_c_us delay_l_us   (as in dualpi2.sh)
#   ecn_mark      cumulative CE marks set by the qdisc
#   step_mark     cumulative step-threshold marks (L4S queue sojourn > step_thresh)
#   dropped       cumulative drops of the qdisc (Classic AQM drops, overload and limit drops)
#   backlog_pkts  packets queued at the poll instant (both queues)
#   maxq          largest queue length seen by the qdisc so far
# Counters are cumulative since the qdisc was created: use differences over the measurement window.

DEFAULT_IFACE="enp8s0"
INTERVAL=0.1
DEFAULT_LOGFILE="dualpi2_stats.log"
DEFAULT_TIME_LIMIT=60

LOGFILE="${1:-$DEFAULT_LOGFILE}"
TIME_LIMIT="${2:-$DEFAULT_TIME_LIMIT}"
IFACE="${3:-$DEFAULT_IFACE}"

echo "Starting DualPI2 polling on interface $IFACE"
echo "Logging output to: $LOGFILE"
echo "Time limit: $TIME_LIMIT seconds"
echo "timestamp prob_raw pkts_in_c pkts_in_l delay_c_us delay_l_us ecn_mark step_mark dropped backlog_pkts maxq" > "$LOGFILE"

start_time=$(date +%s)
while [ $(( $(date +%s) - start_time )) -lt "$TIME_LIMIT" ]; do
    # one tc call and one awk pass per poll; a line is written only when the dualpi2 stats were found
    LINE=$(tc -s qdisc show dev "$IFACE" | grep -A8 "qdisc dualpi2" | awk '
        { for (i = 1; i < NF; i++) {
              if ($i == "prob")      prob = $(i+1)
              if ($i == "pkts_in_c") pc = $(i+1)
              if ($i == "pkts_in_l") pl = $(i+1)
              if ($i == "delay_c")   { dc = $(i+1); sub(/us$/, "", dc) }
              if ($i == "delay_l")   { dl = $(i+1); sub(/us$/, "", dl) }
              if ($i == "ecn_mark")  em = $(i+1)
              if ($i == "step_mark") sm = $(i+1)
              if ($i == "(dropped")  { dr = $(i+1); sub(/,$/, "", dr) }   # " Sent ... pkt (dropped 71, ..."
              if ($i == "backlog")   { bp = $(i+2); sub(/p$/, "", bp) }
              if ($i == "maxq")      mq = $(i+1)
        } }
        END { if (prob != "") print prob, pc, pl, dc, dl, em, sm, dr, bp, mq }')
    TS=$(date +%s.%N)
    [ -n "$LINE" ] && echo "$TS $LINE" >> "$LOGFILE"
    sleep "$INTERVAL"
done

echo "Time limit of $TIME_LIMIT seconds reached, exiting."
echo "DualPI2 polling completed."
