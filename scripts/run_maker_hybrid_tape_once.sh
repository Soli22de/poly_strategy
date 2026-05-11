#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
SNAPSHOTS="${SNAPSHOTS:-data/realtime-monitor-24h-v1-snapshots.ndjson}"
RULES="${RULES:-data/gpt55-candidate-rules-all.json}"
GAMMA="${GAMMA:-data/polymarket-gamma.ndjson}"
HYBRID_SCAN="${HYBRID_SCAN:-data/maker-hybrid-scan-current.json}"
TRADES="${TRADES:-data/polymarket-data-trades-current.ndjson}"
OUT="${OUT:-data/maker-hybrid-tape-sim-current.json}"
PROXY="${PROXY:-127.0.0.1:10808}"
TIMEOUT="${TIMEOUT:-15}"
TRADE_LIMIT="${TRADE_LIMIT:-250}"
TRADE_SIDE="${TRADE_SIDE:-SELL}"
TOP_MARKETS="${TOP_MARKETS:-40}"
PER_MARKET="${PER_MARKET:-1}"
TRADE_WORKERS="${TRADE_WORKERS:-6}"
TRADE_RETRIES="${TRADE_RETRIES:-2}"
TICK_SIZE="${TICK_SIZE:-0.001}"
QUOTE_MODE="${QUOTE_MODE:-near_ask}"
QUOTE_OFFSET_TICKS="${QUOTE_OFFSET_TICKS:-1}"
MIN_EDGE="${MIN_EDGE:-0.0001}"
MIN_ROI="${MIN_ROI:-0.00005}"
MAX_CAPITAL="${MAX_CAPITAL:-100}"
MAX_LEG_COUNT="${MAX_LEG_COUNT:-80}"
MIN_MAKER_LEGS="${MIN_MAKER_LEGS:-2}"
MAX_MAKER_LEGS="${MAX_MAKER_LEGS:-3}"
MAKER_SELECTION_POOL_SIZE="${MAKER_SELECTION_POOL_SIZE:-8}"
MAX_MAKER_COMBINATIONS="${MAX_MAKER_COMBINATIONS:-25}"
HORIZON_SECONDS="${HORIZON_SECONDS:-300}"
MAX_CANDIDATES_PER_BATCH="${MAX_CANDIDATES_PER_BATCH:-50}"
TOP="${TOP:-50}"
LOCK_DIR="${LOCK_DIR:-var/locks/maker-hybrid-tape.lock}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "missing python: $PYTHON_BIN" >&2
  exit 1
fi

if [[ ! -s "$SNAPSHOTS" || ! -s "$HYBRID_SCAN" || ! -s "$GAMMA" ]]; then
  echo "maker_hybrid_tape=0 reason=missing_inputs out=$OUT"
  exit 0
fi

mkdir -p "$(dirname "$LOCK_DIR")"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "maker_hybrid_tape=0 reason=locked out=$OUT"
  exit 0
fi
TRADES_TMP="${TRADES}.tmp.$$"
cleanup() {
  rm -f "$TRADES_TMP"
  rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup EXIT

: > "$TRADES_TMP"

collect_args=(
  -m poly_strategy.cli collect-polymarket-trades
  --out "$TRADES_TMP"
  --gamma "$GAMMA"
  --hybrid-scan "$HYBRID_SCAN"
  --top-markets "$TOP_MARKETS"
  --limit "$TRADE_LIMIT"
  --side "$TRADE_SIDE"
  --timeout "$TIMEOUT"
  --proxy "$PROXY"
  --trade-workers "$TRADE_WORKERS"
  --skip-errors
  --retries "$TRADE_RETRIES"
)
if [[ "$PER_MARKET" == "1" ]]; then
  collect_args+=(--per-market)
fi

"$PYTHON_BIN" "${collect_args[@]}"
mv "$TRADES_TMP" "$TRADES"

"$PYTHON_BIN" -m poly_strategy.cli maker-hybrid-tape-sim \
  --snapshots "$SNAPSHOTS" \
  --trades "$TRADES" \
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
  --horizon-seconds "$HORIZON_SECONDS" \
  --max-candidates-per-batch "$MAX_CANDIDATES_PER_BATCH" \
  --top "$TOP"
