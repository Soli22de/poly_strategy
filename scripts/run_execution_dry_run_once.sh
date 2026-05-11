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

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
ALERTS_PATH="${ALERTS_PATH:-data/realtime-monitor-24h-v1-alerts.ndjson}"
GAMMA="${GAMMA:-data/polymarket-gamma.ndjson}"
RULES="${RULES:-data/gpt55-candidate-rules-all.json}"
SNAPSHOTS_OUT="${SNAPSHOTS_OUT:-data/realtime-alert-execution-refresh.ndjson}"
PLANS_OUT="${PLANS_OUT:-data/realtime-alert-execution-plans.ndjson}"
PROXY="${PROXY:-127.0.0.1:10808}"
TIMEOUT="${TIMEOUT:-10}"
BOOK_WORKERS="${BOOK_WORKERS:-4}"
MAX_ALERTS="${MAX_ALERTS:-20}"
MIN_NET_EDGE="${MIN_NET_EDGE:-0.002}"
MAX_CAPITAL_PER_TRADE="${MAX_CAPITAL_PER_TRADE:-9.5}"
BANKROLL="${BANKROLL:-100}"
MIN_PAPER_ROI="${MIN_PAPER_ROI:-0.01}"
MIN_RUN_OBSERVATIONS="${MIN_RUN_OBSERVATIONS:-1}"
MIN_RUN_SECONDS="${MIN_RUN_SECONDS:-0}"
MAX_TRADES="${MAX_TRADES:-3}"
SLIPPAGE_BPS="${SLIPPAGE_BPS:-50}"
TICK_SIZE="${TICK_SIZE:-0.01}"
MAX_LEG_COUNT="${MAX_LEG_COUNT:-2}"
MIN_LIMIT_EDGE_PER_SHARE="${MIN_LIMIT_EDGE_PER_SHARE:-0.002}"
MIN_LIMIT_ROI="${MIN_LIMIT_ROI:-0.001}"
RISK_STATE="${RISK_STATE:-data/risk-state.json}"
KILL_SWITCH="${KILL_SWITCH:-data/KILL_SWITCH}"
MAX_TRADE_NOTIONAL="${MAX_TRADE_NOTIONAL:-10}"
MAX_DAILY_LOSS="${MAX_DAILY_LOSS:-25}"
MAX_DAILY_ORDERS="${MAX_DAILY_ORDERS:-20}"
MAX_ORDER_COUNT="${MAX_ORDER_COUNT:-2}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "missing python: $PYTHON_BIN" >&2
  exit 1
fi

if [[ ! -s "$ALERTS_PATH" ]]; then
  echo "alerts=0 snapshots=0 plans=0 out=$PLANS_OUT"
  exit 0
fi

exec "$PYTHON_BIN" -m poly_strategy.cli execute-alerts "$ALERTS_PATH" \
  --gamma "$GAMMA" \
  --rules "$RULES" \
  --snapshots-out "$SNAPSHOTS_OUT" \
  --out "$PLANS_OUT" \
  --max-alerts "$MAX_ALERTS" \
  --timeout "$TIMEOUT" \
  --proxy "$PROXY" \
  --book-workers "$BOOK_WORKERS" \
  --skip-book-errors \
  --refresh-missing-gamma \
  --min-net-edge "$MIN_NET_EDGE" \
  --max-capital-per-trade "$MAX_CAPITAL_PER_TRADE" \
  --bankroll "$BANKROLL" \
  --min-paper-roi "$MIN_PAPER_ROI" \
  --min-run-observations "$MIN_RUN_OBSERVATIONS" \
  --min-run-seconds "$MIN_RUN_SECONDS" \
  --max-trades "$MAX_TRADES" \
  --slippage-bps "$SLIPPAGE_BPS" \
  --tick-size "$TICK_SIZE" \
  --max-leg-count "$MAX_LEG_COUNT" \
  --min-limit-edge-per-share "$MIN_LIMIT_EDGE_PER_SHARE" \
  --min-limit-roi "$MIN_LIMIT_ROI" \
  --require-pretrade-pass \
  --risk-state "$RISK_STATE" \
  --kill-switch "$KILL_SWITCH" \
  --max-trade-notional "$MAX_TRADE_NOTIONAL" \
  --max-daily-loss "$MAX_DAILY_LOSS" \
  --max-daily-orders "$MAX_DAILY_ORDERS" \
  --max-order-count "$MAX_ORDER_COUNT" \
  --require-risk-pass
