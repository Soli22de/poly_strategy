#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
RUN_ANALYSIS="${RUN_ANALYSIS:-1}"
ANALYSIS="${ANALYSIS:-data/realtime-monitor-24h-v1-analysis.json}"
MARKET_IDS_OUT="${MARKET_IDS_OUT:-data/optimization-target-market-ids.txt}"
SNAPSHOTS_OUT="${SNAPSHOTS_OUT:-data/optimization-target-snapshots.ndjson}"
RULES="${RULES:-data/gpt55-candidate-rules-all.json}"
GAMMA="${GAMMA:-data/polymarket-gamma.ndjson}"
OUT="${OUT:-data/maker-hybrid-scan-focus.json}"
LEVER="${LEVER:-maker_fee_avoidance}"
TOP_TARGETS="${TOP_TARGETS:-1}"
MAX_TARGET_MARKETS="${MAX_TARGET_MARKETS:-120}"
PROXY="${PROXY:-127.0.0.1:10808}"
TIMEOUT="${TIMEOUT:-15}"
BOOK_WORKERS="${BOOK_WORKERS:-8}"
EXPAND_NEG_RISK_GROUPS="${EXPAND_NEG_RISK_GROUPS:-1}"
TICK_SIZE="${TICK_SIZE:-0.001}"
QUOTE_MODE="${QUOTE_MODE:-near_ask}"
QUOTE_OFFSET_TICKS="${QUOTE_OFFSET_TICKS:-1}"
MIN_EDGE="${MIN_EDGE:-0.0001}"
MIN_ROI="${MIN_ROI:-0.00005}"
MAX_CAPITAL="${MAX_CAPITAL:-100}"
MAX_LEG_COUNT="${MAX_LEG_COUNT:-120}"
MIN_MAKER_LEGS="${MIN_MAKER_LEGS:-2}"
MAX_MAKER_LEGS="${MAX_MAKER_LEGS:-3}"
MAKER_SELECTION_POOL_SIZE="${MAKER_SELECTION_POOL_SIZE:-10}"
MAX_MAKER_COMBINATIONS="${MAX_MAKER_COMBINATIONS:-40}"
TOP="${TOP:-50}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "missing python: $PYTHON_BIN" >&2
  exit 1
fi

if [[ "$RUN_ANALYSIS" == "1" ]]; then
  OUT="$ANALYSIS" scripts/run_realtime_analysis_once.sh
fi

if [[ ! -s "$ANALYSIS" ]]; then
  echo "maker_focus=0 reason=missing_analysis analysis=$ANALYSIS"
  exit 0
fi

"$PYTHON_BIN" -m poly_strategy.cli optimization-target-markets "$ANALYSIS" \
  --lever "$LEVER" \
  --top-targets "$TOP_TARGETS" \
  --max-markets "$MAX_TARGET_MARKETS" \
  --out "$MARKET_IDS_OUT"

if [[ ! -s "$MARKET_IDS_OUT" ]]; then
  echo "maker_focus=0 reason=no_target_market_ids analysis=$ANALYSIS lever=$LEVER"
  exit 0
fi

: > "$SNAPSHOTS_OUT"

collect_args=(
  -m poly_strategy.cli collect-polymarket-binaries
  --out "$SNAPSHOTS_OUT"
  --gamma "$GAMMA"
  --market-ids-file "$MARKET_IDS_OUT"
  --refresh-missing-gamma
  --timeout "$TIMEOUT"
  --proxy "$PROXY"
  --book-workers "$BOOK_WORKERS"
  --skip-book-errors
  --max-markets "$MAX_TARGET_MARKETS"
)
if [[ "$EXPAND_NEG_RISK_GROUPS" != "1" ]]; then
  collect_args+=(--no-expand-neg-risk-groups)
fi
"$PYTHON_BIN" "${collect_args[@]}"

"$PYTHON_BIN" -m poly_strategy.cli maker-hybrid-scan \
  --snapshots "$SNAPSHOTS_OUT" \
  --rules "$RULES" \
  --gamma "$GAMMA" \
  --out "$OUT" \
  --tick-size "$TICK_SIZE" \
  --quote-mode "$QUOTE_MODE" \
  --quote-offset-ticks "$QUOTE_OFFSET_TICKS" \
  --min-edge "$MIN_EDGE" \
  --min-roi "$MIN_ROI" \
  --max-capital "$MAX_CAPITAL" \
  --max-leg-count "$MAX_LEG_COUNT" \
  --min-maker-legs "$MIN_MAKER_LEGS" \
  --max-maker-legs "$MAX_MAKER_LEGS" \
  --maker-selection-pool-size "$MAKER_SELECTION_POOL_SIZE" \
  --max-maker-combinations "$MAX_MAKER_COMBINATIONS" \
  --top "$TOP"
