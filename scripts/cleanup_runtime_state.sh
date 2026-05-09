#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DATA_DIR="${DATA_DIR:-data}"
VAR_DIR="${VAR_DIR:-var}"
DRY_RUN="${DRY_RUN:-0}"

run_cmd() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf 'would_run'
    printf ' %q' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

delete_glob() {
  local matched=0
  shopt -s nullglob
  for path in "$@"; do
    matched=1
    echo "delete path=$path"
    run_cmd rm -f "$path"
  done
  shopt -u nullglob
  if [[ "$matched" == "0" ]]; then
    return 0
  fi
}

truncate_file() {
  local path="$1"
  [[ -f "$path" ]] || return 0
  echo "truncate path=$path"
  if [[ "$DRY_RUN" != "1" ]]; then
    : > "$path"
  fi
}

mkdir -p "$DATA_DIR" "$VAR_DIR/run" "$VAR_DIR/log"

delete_glob "$DATA_DIR"/*.tmp.* "$DATA_DIR"/*snapshots*.ndjson.*.gz
delete_glob "$DATA_DIR"/paper-monitor-24h*.ndjson "$DATA_DIR"/paper-monitor-24h*.jsonl "$DATA_DIR"/paper-monitor-24h*.log
delete_glob "$DATA_DIR"/paper-monitor-2h*.ndjson "$DATA_DIR"/paper-monitor-2h*.jsonl "$DATA_DIR"/paper-monitor-2h*.log

for path in \
  "$DATA_DIR/realtime-monitor-24h-v1.log" \
  "$DATA_DIR/realtime-monitor-24h-v1.jsonl" \
  "$DATA_DIR/realtime-monitor-24h-v1-snapshots.ndjson" \
  "$DATA_DIR/realtime-monitor-24h-v1-alerts.log" \
  "$DATA_DIR/realtime-monitor-24h-v1-alerts.ndjson" \
  "$DATA_DIR/realtime-alert-execution-dry-run.log" \
  "$DATA_DIR/realtime-alert-notifications.log" \
  "$DATA_DIR/realtime-analysis.log" \
  "$DATA_DIR/realtime-discovery-refresh.log" \
  "$DATA_DIR/rule-promotion.log" \
  "$DATA_DIR/external-signals-refresh.log" \
  "$DATA_DIR/data-rotation.log" \
  "$VAR_DIR/log/poly_strategy-background.log" \
  "$VAR_DIR/log/realtime-monitor.log"; do
  truncate_file "$path"
done

rm -f "$VAR_DIR/run/poly_strategy-background.pid" "$VAR_DIR/run/poly_strategy-monitor.pid" 2>/dev/null || true

echo "cleanup_done dry_run=$DRY_RUN data_dir=$DATA_DIR var_dir=$VAR_DIR"
