#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
REPORT_PATH="${REPORT_PATH:-data/realtime-monitor-24h-v1.jsonl}"
ALERTS_OUT="${ALERTS_OUT:-data/realtime-monitor-24h-v1-alerts.ndjson}"
ALERT_STATE="${ALERT_STATE:-data/realtime-monitor-24h-v1-alert-state.json}"
MIN_PAPER_ROI="${MIN_PAPER_ROI:-0.01}"
COOLDOWN_SECONDS="${COOLDOWN_SECONDS:-60}"
MAX_ALERTS="${MAX_ALERTS:-20}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "missing python: $PYTHON_BIN" >&2
  exit 1
fi

exec "$PYTHON_BIN" -m poly_strategy.cli monitor-alerts "$REPORT_PATH" \
  --min-paper-roi "$MIN_PAPER_ROI" \
  --max-alerts "$MAX_ALERTS" \
  --out "$ALERTS_OUT" \
  --state "$ALERT_STATE" \
  --cooldown-seconds "$COOLDOWN_SECONDS"
