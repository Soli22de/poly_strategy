#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
MONITOR_REPORT="${MONITOR_REPORT:-data/realtime-monitor-24h-v1.jsonl}"
EXECUTION_PLANS="${EXECUTION_PLANS:-data/realtime-alert-execution-plans.ndjson}"
MAKER_ADAPTIVE="${MAKER_ADAPTIVE:-data/maker-adaptive-sim-current.json}"
MAKER_HEDGE="${MAKER_HEDGE:-data/maker-hedge-sim-current.json}"
MAKER_HYBRID="${MAKER_HYBRID:-data/maker-hybrid-sim-current.json}"
MAKER_HYBRID_TAPE="${MAKER_HYBRID_TAPE:-data/maker-hybrid-tape-sim-current.json}"
CROSS_PLATFORM_SCAN="${CROSS_PLATFORM_SCAN:-data/cross-platform-verified-scan-cap100.json}"
MIN_MAKER_HYBRID_TAPE_EDGE_AT_CAP="${MIN_MAKER_HYBRID_TAPE_EDGE_AT_CAP:-0.25}"
MIN_CROSS_PLATFORM_CAPITAL_EDGE="${MIN_CROSS_PLATFORM_CAPITAL_EDGE:-0.5}"
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
  --maker-hedge "$MAKER_HEDGE" \
  --maker-hybrid "$MAKER_HYBRID" \
  --maker-hybrid-tape "$MAKER_HYBRID_TAPE" \
  --cross-platform-scan "$CROSS_PLATFORM_SCAN" \
  --min-maker-hybrid-tape-edge-at-cap "$MIN_MAKER_HYBRID_TAPE_EDGE_AT_CAP" \
  --min-cross-platform-capital-edge "$MIN_CROSS_PLATFORM_CAPITAL_EDGE" \
  --out "$OUT" \
  --success-log "$SUCCESS_LOG"
