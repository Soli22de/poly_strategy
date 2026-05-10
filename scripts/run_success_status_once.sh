#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
MONITOR_REPORT="${MONITOR_REPORT:-data/realtime-monitor-24h-v1.jsonl}"
EXECUTION_PLANS="${EXECUTION_PLANS:-data/realtime-alert-execution-plans.ndjson}"
MAKER_ADAPTIVE="${MAKER_ADAPTIVE:-data/maker-adaptive-sim-current.json}"
OUT="${OUT:-data/success-status-current.json}"
SUCCESS_LOG="${SUCCESS_LOG:-data/success-events.ndjson}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "missing python: $PYTHON_BIN" >&2
  exit 1
fi

exec "$PYTHON_BIN" -m poly_strategy.cli success-status \
  --monitor-report "$MONITOR_REPORT" \
  --execution-plans "$EXECUTION_PLANS" \
  --maker-adaptive "$MAKER_ADAPTIVE" \
  --out "$OUT" \
  --success-log "$SUCCESS_LOG"
