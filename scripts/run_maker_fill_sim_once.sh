#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
SNAPSHOTS="${SNAPSHOTS:-data/realtime-monitor-24h-v1-snapshots.ndjson}"
RULES="${RULES:-data/gpt55-candidate-rules-all.json}"
GAMMA="${GAMMA:-data/polymarket-gamma.ndjson}"
OUT="${OUT:-data/maker-fill-sim-current.json}"
TICK_SIZE="${TICK_SIZE:-0.001}"
QUOTE_MODE="${QUOTE_MODE:-near_ask}"
MIN_EDGE="${MIN_EDGE:-0.002}"
MIN_ROI="${MIN_ROI:-0.001}"
MAX_CAPITAL="${MAX_CAPITAL:-100}"
MAX_LEG_COUNT="${MAX_LEG_COUNT:-30}"
HORIZON_SECONDS="${HORIZON_SECONDS:-300}"
MAX_CANDIDATES_PER_BATCH="${MAX_CANDIDATES_PER_BATCH:-10}"
TOP="${TOP:-50}"
INCLUDE_YES_NO_PAIRS="${INCLUDE_YES_NO_PAIRS:-0}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "missing python: $PYTHON_BIN" >&2
  exit 1
fi

if [[ ! -s "$SNAPSHOTS" ]]; then
  echo "maker_fill_observations=0 reason=missing_snapshots out=$OUT"
  exit 0
fi

args=(
  maker-fill-sim
  --snapshots "$SNAPSHOTS"
  --rules "$RULES"
  --gamma "$GAMMA"
  --out "$OUT"
  --tick-size "$TICK_SIZE"
  --quote-mode "$QUOTE_MODE"
  --min-edge "$MIN_EDGE"
  --min-roi "$MIN_ROI"
  --max-capital "$MAX_CAPITAL"
  --max-leg-count "$MAX_LEG_COUNT"
  --horizon-seconds "$HORIZON_SECONDS"
  --max-candidates-per-batch "$MAX_CANDIDATES_PER_BATCH"
  --top "$TOP"
)

if [[ "$INCLUDE_YES_NO_PAIRS" == "1" ]]; then
  args+=(--include-yes-no-pairs)
fi

exec "$PYTHON_BIN" -m poly_strategy.cli "${args[@]}"
