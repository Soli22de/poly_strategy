#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f .env.local ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env.local
  set +a
fi

if [[ -n "${PROXY:-}" && -z "${HTTPS_PROXY:-}" ]]; then
  export HTTPS_PROXY="http://${PROXY}"
  export HTTP_PROXY="http://${PROXY}"
fi

LABEL="${LABEL:-poly_strategy_realtime_monitor_24h}"
LOG_PATH="${LOG_PATH:-data/realtime-monitor-24h-v1.log}"
REPORT_OUT="${REPORT_OUT:-data/realtime-monitor-24h-v1.jsonl}"
SNAPSHOTS_OUT="${SNAPSHOTS_OUT:-data/realtime-monitor-24h-v1-snapshots.ndjson}"
SNAPSHOT_INTERVAL="${SNAPSHOT_INTERVAL:-2}"
STALE_TIMEOUT="${STALE_TIMEOUT:-30}"
RECONNECT_DELAY="${RECONNECT_DELAY:-2}"
MIN_NET_EDGE="${MIN_NET_EDGE:-0.002}"
MAX_CAPITAL_PER_TRADE="${MAX_CAPITAL_PER_TRADE:-10}"
BANKROLL="${BANKROLL:-100}"
MIN_PAPER_ROI="${MIN_PAPER_ROI:-0.01}"
MIN_RUN_OBSERVATIONS="${MIN_RUN_OBSERVATIONS:-2}"
MIN_RUN_SECONDS="${MIN_RUN_SECONDS:-3}"
INCLUDE_TOP_MARKETS="${INCLUDE_TOP_MARKETS:-150}"
INCLUDE_TOP_NEG_RISK_GROUPS="${INCLUDE_TOP_NEG_RISK_GROUPS:-25}"
MAX_WATCHLIST_MARKETS="${MAX_WATCHLIST_MARKETS:-250}"
WS_MAX_SIZE="${WS_MAX_SIZE:-4194304}"
RUNTIME_DIR="${RUNTIME_DIR:-var/run}"
MANAGER_PID_FILE="${MANAGER_PID_FILE:-$RUNTIME_DIR/poly_strategy-background.pid}"
MONITOR_PID_FILE="${MONITOR_PID_FILE:-$RUNTIME_DIR/poly_strategy-monitor.pid}"

mkdir -p "$(dirname "$LOG_PATH")" "$RUNTIME_DIR"

pid_alive() {
  local pid="${1:-}"
  [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1
}

read_pid_file() {
  local path="$1"
  [[ -s "$path" ]] && sed -n '1p' "$path" || true
}

stop_pid() {
  local pid="$1"
  pid_alive "$pid" || return 0
  pkill -TERM -P "$pid" >/dev/null 2>&1 || true
  kill -TERM "$pid" >/dev/null 2>&1 || true
  for _ in {1..20}; do
    pid_alive "$pid" || return 0
    sleep 0.25
  done
  pkill -KILL -P "$pid" >/dev/null 2>&1 || true
  kill -KILL "$pid" >/dev/null 2>&1 || true
}

manager_pid="$(read_pid_file "$MANAGER_PID_FILE")"
if pid_alive "$manager_pid"; then
  monitor_pid="$(read_pid_file "$MONITOR_PID_FILE")"
  if pid_alive "$monitor_pid"; then
    stop_pid "$monitor_pid"
  fi
  rm -f "$MONITOR_PID_FILE"
  echo "manager_monitor_restart_requested manager_pid=$manager_pid"
  exit 0
fi

if [[ "${USE_KICKSTART:-1}" == "1" ]] && launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
  launchctl kickstart -k "gui/$(id -u)/$LABEL"
  launchctl print "gui/$(id -u)/$LABEL" | awk -v label="$LABEL" 'NR == 1 {print label " kickstarted"}'
  exit 0
fi

launchctl remove "$LABEL" >/dev/null 2>&1 || true

cmd="cd '$ROOT_DIR' && PYTHONUNBUFFERED=1 REPORT_OUT='$REPORT_OUT' SNAPSHOTS_OUT='$SNAPSHOTS_OUT' SNAPSHOT_INTERVAL='$SNAPSHOT_INTERVAL' STALE_TIMEOUT='$STALE_TIMEOUT' RECONNECT_DELAY='$RECONNECT_DELAY' MIN_NET_EDGE='$MIN_NET_EDGE' MAX_CAPITAL_PER_TRADE='$MAX_CAPITAL_PER_TRADE' BANKROLL='$BANKROLL' MIN_PAPER_ROI='$MIN_PAPER_ROI' MIN_RUN_OBSERVATIONS='$MIN_RUN_OBSERVATIONS' MIN_RUN_SECONDS='$MIN_RUN_SECONDS' INCLUDE_TOP_MARKETS='$INCLUDE_TOP_MARKETS' INCLUDE_TOP_NEG_RISK_GROUPS='$INCLUDE_TOP_NEG_RISK_GROUPS' MAX_WATCHLIST_MARKETS='$MAX_WATCHLIST_MARKETS' WS_MAX_SIZE='$WS_MAX_SIZE' scripts/run_realtime_monitor.sh >> '$LOG_PATH' 2>&1"
launchctl submit -l "$LABEL" -- /bin/zsh -lc "$cmd"
launchctl list | awk -v label="$LABEL" '$3 == label {print}'
