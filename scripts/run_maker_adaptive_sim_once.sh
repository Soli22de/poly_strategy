#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
SNAPSHOTS="${SNAPSHOTS:-data/realtime-monitor-24h-v1-snapshots.ndjson}"
RULES="${RULES:-data/gpt55-candidate-rules-all.json}"
GAMMA="${GAMMA:-data/polymarket-gamma.ndjson}"
OUT="${OUT:-data/maker-adaptive-sim-current.json}"
TICK_SIZE="${TICK_SIZE:-0.001}"
QUOTE_OFFSET_TICKS="${QUOTE_OFFSET_TICKS:-1,2,3,5,10}"
MIN_EDGE="${MIN_EDGE:-0.002}"
MIN_ROI="${MIN_ROI:-0.001}"
MAX_CAPITAL="${MAX_CAPITAL:-100}"
MAX_LEG_COUNT="${MAX_LEG_COUNT:-30}"
HORIZON_SECONDS="${HORIZON_SECONDS:-300}"
MAX_CANDIDATES_PER_BATCH="${MAX_CANDIDATES_PER_BATCH:-10}"
PARTIAL_LOSS_RATE="${PARTIAL_LOSS_RATE:-1.0}"
MIN_OBSERVATIONS="${MIN_OBSERVATIONS:-5}"
TOP="${TOP:-25}"
INCLUDE_YES_NO_PAIRS="${INCLUDE_YES_NO_PAIRS:-0}"
NO_IMPROVE_BID="${NO_IMPROVE_BID:-0}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "missing python: $PYTHON_BIN" >&2
  exit 1
fi

if [[ ! -s "$SNAPSHOTS" ]]; then
  echo "maker_adaptive_status=missing_snapshots out=$OUT"
  exit 0
fi

args=(
  maker-adaptive-sim
  --snapshots "$SNAPSHOTS"
  --rules "$RULES"
  --gamma "$GAMMA"
  --out "$OUT"
  --tick-size "$TICK_SIZE"
  --quote-offset-ticks "$QUOTE_OFFSET_TICKS"
  --min-edge "$MIN_EDGE"
  --min-roi "$MIN_ROI"
  --max-capital "$MAX_CAPITAL"
  --max-leg-count "$MAX_LEG_COUNT"
  --horizon-seconds "$HORIZON_SECONDS"
  --max-candidates-per-batch "$MAX_CANDIDATES_PER_BATCH"
  --partial-loss-rate "$PARTIAL_LOSS_RATE"
  --min-observations "$MIN_OBSERVATIONS"
  --top "$TOP"
)

if [[ "$INCLUDE_YES_NO_PAIRS" == "1" ]]; then
  args+=(--include-yes-no-pairs)
fi

if [[ "$NO_IMPROVE_BID" == "1" ]]; then
  args+=(--no-improve-bid)
fi

exec "$PYTHON_BIN" -m poly_strategy.cli "${args[@]}"
