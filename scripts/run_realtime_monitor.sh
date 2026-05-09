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

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
WATCHLIST="${WATCHLIST:-data/watchlist-current.json}"
GAMMA="${GAMMA:-data/polymarket-gamma.ndjson}"
RULES="${RULES:-data/gpt55-candidate-rules-all.json}"
EXTERNAL_SIGNALS="${EXTERNAL_SIGNALS:-}"
REPORT_OUT="${REPORT_OUT:-data/realtime-monitor-24h.jsonl}"
SNAPSHOTS_OUT="${SNAPSHOTS_OUT:-data/realtime-monitor-24h-snapshots.ndjson}"
UPDATES_OUT="${UPDATES_OUT:-}"
INCLUDE_TOP_MARKETS="${INCLUDE_TOP_MARKETS:-150}"
INCLUDE_TOP_NEG_RISK_GROUPS="${INCLUDE_TOP_NEG_RISK_GROUPS:-25}"
MIN_LIQUIDITY="${MIN_LIQUIDITY:-0}"
MIN_VOLUME_24H="${MIN_VOLUME_24H:-0}"
MAX_WATCHLIST_MARKETS="${MAX_WATCHLIST_MARKETS:-250}"
WS_MAX_SIZE="${WS_MAX_SIZE:-4194304}"
SNAPSHOT_INTERVAL="${SNAPSHOT_INTERVAL:-2}"
STALE_TIMEOUT="${STALE_TIMEOUT:-30}"
RECONNECT_DELAY="${RECONNECT_DELAY:-2}"
MIN_NET_EDGE="${MIN_NET_EDGE:-0.002}"
MAX_CAPITAL_PER_TRADE="${MAX_CAPITAL_PER_TRADE:-10}"
BANKROLL="${BANKROLL:-100}"
MIN_PAPER_ROI="${MIN_PAPER_ROI:-0.01}"
MIN_RUN_OBSERVATIONS="${MIN_RUN_OBSERVATIONS:-2}"
MIN_RUN_SECONDS="${MIN_RUN_SECONDS:-3}"
MAX_OPPORTUNITIES_PER_ITERATION="${MAX_OPPORTUNITIES_PER_ITERATION:-10}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "missing python: $PYTHON_BIN" >&2
  exit 1
fi

watchlist_args=(
  build-watchlist
  --gamma "$GAMMA"
  --rules "$RULES"
  --out "$WATCHLIST"
  --include-top-markets "$INCLUDE_TOP_MARKETS"
  --include-top-neg-risk-groups "$INCLUDE_TOP_NEG_RISK_GROUPS"
  --min-liquidity "$MIN_LIQUIDITY"
  --min-volume-24h "$MIN_VOLUME_24H"
  --max-markets "$MAX_WATCHLIST_MARKETS"
)

if [[ -n "$EXTERNAL_SIGNALS" ]]; then
  watchlist_args+=(--external-signals "$EXTERNAL_SIGNALS")
fi

"$PYTHON_BIN" -m poly_strategy.cli "${watchlist_args[@]}"

args=(
  realtime-monitor-watchlist
  --watchlist "$WATCHLIST"
  --rules "$RULES"
  --gamma "$GAMMA"
  --report-out "$REPORT_OUT"
  --snapshots-out "$SNAPSHOTS_OUT"
  --snapshot-interval "$SNAPSHOT_INTERVAL"
  --ws-max-size "$WS_MAX_SIZE"
  --stale-timeout "$STALE_TIMEOUT"
  --reconnect-delay "$RECONNECT_DELAY"
  --min-net-edge "$MIN_NET_EDGE"
  --max-capital-per-trade "$MAX_CAPITAL_PER_TRADE"
  --bankroll "$BANKROLL"
  --min-paper-roi "$MIN_PAPER_ROI"
  --min-run-observations "$MIN_RUN_OBSERVATIONS"
  --min-run-seconds "$MIN_RUN_SECONDS"
  --max-opportunities-per-iteration "$MAX_OPPORTUNITIES_PER_ITERATION"
)

if [[ -n "$UPDATES_OUT" ]]; then
  args+=(--updates-out "$UPDATES_OUT")
fi

if [[ -n "${MAX_MESSAGES:-}" ]]; then
  args+=(--max-messages "$MAX_MESSAGES")
fi

if [[ -n "${MAX_ITERATIONS:-}" ]]; then
  args+=(--max-iterations "$MAX_ITERATIONS")
fi

if [[ -n "${MAX_RECONNECTS:-}" ]]; then
  args+=(--max-reconnects "$MAX_RECONNECTS")
fi

exec "$PYTHON_BIN" -u -m poly_strategy.cli "${args[@]}"
