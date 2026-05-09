#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LABEL="${LABEL:-poly_strategy_realtime_monitor_24h}"
LOG_PATH="${LOG_PATH:-data/realtime-monitor-24h-v1.log}"
REPORT_OUT="${REPORT_OUT:-data/realtime-monitor-24h-v1.jsonl}"
SNAPSHOTS_OUT="${SNAPSHOTS_OUT:-data/realtime-monitor-24h-v1-snapshots.ndjson}"
SNAPSHOT_INTERVAL="${SNAPSHOT_INTERVAL:-2}"
STALE_TIMEOUT="${STALE_TIMEOUT:-30}"
RECONNECT_DELAY="${RECONNECT_DELAY:-2}"
MIN_NET_EDGE="${MIN_NET_EDGE:-0.002}"
MAX_CAPITAL_PER_TRADE="${MAX_CAPITAL_PER_TRADE:-10}"
BANKROLL="${BANKROLL:-50}"
MIN_PAPER_ROI="${MIN_PAPER_ROI:-0.01}"
MIN_RUN_OBSERVATIONS="${MIN_RUN_OBSERVATIONS:-2}"
MIN_RUN_SECONDS="${MIN_RUN_SECONDS:-3}"
INCLUDE_TOP_MARKETS="${INCLUDE_TOP_MARKETS:-150}"
INCLUDE_TOP_NEG_RISK_GROUPS="${INCLUDE_TOP_NEG_RISK_GROUPS:-25}"
MAX_WATCHLIST_MARKETS="${MAX_WATCHLIST_MARKETS:-250}"

mkdir -p "$(dirname "$LOG_PATH")"
if [[ "${USE_KICKSTART:-1}" == "1" ]] && launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
  launchctl kickstart -k "gui/$(id -u)/$LABEL"
  launchctl print "gui/$(id -u)/$LABEL" | awk -v label="$LABEL" 'NR == 1 {print label " kickstarted"}'
  exit 0
fi

launchctl remove "$LABEL" >/dev/null 2>&1 || true

cmd="cd '$ROOT_DIR' && PYTHONUNBUFFERED=1 REPORT_OUT='$REPORT_OUT' SNAPSHOTS_OUT='$SNAPSHOTS_OUT' SNAPSHOT_INTERVAL='$SNAPSHOT_INTERVAL' STALE_TIMEOUT='$STALE_TIMEOUT' RECONNECT_DELAY='$RECONNECT_DELAY' MIN_NET_EDGE='$MIN_NET_EDGE' MAX_CAPITAL_PER_TRADE='$MAX_CAPITAL_PER_TRADE' BANKROLL='$BANKROLL' MIN_PAPER_ROI='$MIN_PAPER_ROI' MIN_RUN_OBSERVATIONS='$MIN_RUN_OBSERVATIONS' MIN_RUN_SECONDS='$MIN_RUN_SECONDS' INCLUDE_TOP_MARKETS='$INCLUDE_TOP_MARKETS' INCLUDE_TOP_NEG_RISK_GROUPS='$INCLUDE_TOP_NEG_RISK_GROUPS' MAX_WATCHLIST_MARKETS='$MAX_WATCHLIST_MARKETS' scripts/run_realtime_monitor.sh >> '$LOG_PATH' 2>&1"
launchctl submit -l "$LABEL" -- /bin/zsh -lc "$cmd"
launchctl list | awk -v label="$LABEL" '$3 == label {print}'
