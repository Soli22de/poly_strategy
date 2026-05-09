#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
GAMMA="${GAMMA:-data/polymarket-gamma.ndjson}"
RULES="${RULES:-data/gpt55-candidate-rules-all.json}"
WATCHLIST="${WATCHLIST:-data/watchlist-current.json}"
EXTERNAL_SIGNALS="${EXTERNAL_SIGNALS:-}"
PROXY="${PROXY:-127.0.0.1:10808}"
LIMIT="${LIMIT:-100}"
PAGES="${PAGES:-5}"
OFFSET="${OFFSET:-0}"
TIMEOUT="${TIMEOUT:-15}"
BATCH_SIZE="${BATCH_SIZE:-10}"
MIN_CONFIDENCE="${MIN_CONFIDENCE:-0.95}"
INCLUDE_TOP_MARKETS="${INCLUDE_TOP_MARKETS:-150}"
INCLUDE_TOP_NEG_RISK_GROUPS="${INCLUDE_TOP_NEG_RISK_GROUPS:-25}"
MIN_LIQUIDITY="${MIN_LIQUIDITY:-0}"
MIN_VOLUME_24H="${MIN_VOLUME_24H:-0}"
MAX_WATCHLIST_MARKETS="${MAX_WATCHLIST_MARKETS:-250}"
RESTART_ON_CHANGE="${RESTART_ON_CHANGE:-1}"
RESTART_SCRIPT="${RESTART_SCRIPT:-scripts/restart_realtime_monitor.sh}"
SKIP_GAMMA="${SKIP_GAMMA:-0}"
SKIP_LLM="${SKIP_LLM:-0}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "missing python: $PYTHON_BIN" >&2
  exit 1
fi

mkdir -p "$(dirname "$GAMMA")" "$(dirname "$RULES")" "$(dirname "$WATCHLIST")"

if [[ "$SKIP_GAMMA" != "1" ]]; then
  "$PYTHON_BIN" -m poly_strategy.cli collect-polymarket \
    --out "$GAMMA" \
    --limit "$LIMIT" \
    --pages "$PAGES" \
    --offset "$OFFSET" \
    --timeout "$TIMEOUT" \
    --proxy "$PROXY"
fi

if [[ "$SKIP_LLM" != "1" && -n "${OPENAI_MODEL:-}" ]]; then
  rules_tmp="$(mktemp "${RULES}.tmp.XXXXXX")"
  "$PYTHON_BIN" -m poly_strategy.cli discover-rules \
    --raw "$GAMMA" \
    --out "$rules_tmp" \
    --cache "$RULES" \
    --batch-size "$BATCH_SIZE" \
    --min-confidence "$MIN_CONFIDENCE"
  mv "$rules_tmp" "$RULES"
else
  echo "skip_llm=1 or OPENAI_MODEL is empty; reusing existing rule cache: $RULES"
fi

watchlist_tmp="$(mktemp "${WATCHLIST}.tmp.XXXXXX")"
watchlist_args=(
  build-watchlist
  --gamma "$GAMMA"
  --rules "$RULES"
  --out "$watchlist_tmp"
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

changed=0
if [[ ! -f "$WATCHLIST" ]] || ! cmp -s "$watchlist_tmp" "$WATCHLIST"; then
  mv "$watchlist_tmp" "$WATCHLIST"
  changed=1
else
  rm -f "$watchlist_tmp"
fi

count="$("$PYTHON_BIN" -c 'import json, sys; from pathlib import Path; path = Path(sys.argv[1]); row = json.loads(path.read_text()) if path.exists() else {"markets": []}; print(len(row.get("markets", [])))' "$WATCHLIST")"
echo "watchlist_markets=$count changed=$changed path=$WATCHLIST"

if [[ "$changed" == "1" && "$RESTART_ON_CHANGE" == "1" ]]; then
  "$RESTART_SCRIPT"
fi
