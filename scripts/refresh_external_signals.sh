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
SOURCE="${SOURCE:-external_scanner}"
INPUT_PATH="${INPUT_PATH:-}"
OUT="${OUT:-data/external-signals.ndjson}"
PROXY="${PROXY:-127.0.0.1:10808}"
TIMEOUT="${TIMEOUT:-10}"
REFRESH_WATCHLIST="${REFRESH_WATCHLIST:-1}"
ALLOW_EXTERNAL_SIGNAL_FAILURE="${ALLOW_EXTERNAL_SIGNAL_FAILURE:-1}"
ODDPOOL_PLAN="${ODDPOOL_PLAN:-free}"
ODDPOOL_BASE_URL="${ODDPOOL_BASE_URL:-https://api.oddpool.com}"
ODDPOOL_SEARCH_LIMIT="${ODDPOOL_SEARCH_LIMIT:-30}"
ODDPOOL_SEARCH_EXCHANGE="${ODDPOOL_SEARCH_EXCHANGE:-}"
ODDPOOL_SEARCH_QUERIES="${ODDPOOL_SEARCH_QUERIES:-}"
ODDPOOL_INCLUDE_RECENT_EVENTS="${ODDPOOL_INCLUDE_RECENT_EVENTS:-0}"
ODDPOOL_QUOTA_STATE="${ODDPOOL_QUOTA_STATE:-data/oddpool-quota.json}"
ODDPOOL_MONTHLY_QUOTA="${ODDPOOL_MONTHLY_QUOTA:-1000}"
ODDPOOL_MIN_INTERVAL_SECONDS="${ODDPOOL_MIN_INTERVAL_SECONDS:-1.05}"
ODDPOOL_PLAN_NORMALIZED="$(printf '%s' "$ODDPOOL_PLAN" | tr '[:upper:]' '[:lower:]')"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "missing python: $PYTHON_BIN" >&2
  exit 1
fi

urlencode_query() {
  "$PYTHON_BIN" -c 'import sys, urllib.parse; print(urllib.parse.quote_plus(sys.argv[1]))' "$1"
}

URLS=()
if [[ -z "$INPUT_PATH" ]]; then
  if [[ "$SOURCE" == "oddpool" && "$ODDPOOL_PLAN_NORMALIZED" == "free" ]]; then
    if [[ -n "${ODDPOOL_SEARCH_URL:-}" ]]; then
      URLS+=("$ODDPOOL_SEARCH_URL")
    else
      if [[ "${ODDPOOL_API_URL:-}" == *"/arbitrage/"* || "${EXTERNAL_SIGNAL_URL:-}" == *"/arbitrage/"* ]]; then
        echo "oddpool_plan=free ignoring_premium_arbitrage_url=1" >&2
      fi
      query="limit=${ODDPOOL_SEARCH_LIMIT}"
      if [[ -n "$ODDPOOL_SEARCH_EXCHANGE" ]]; then
        query="${query}&exchange=$(urlencode_query "$ODDPOOL_SEARCH_EXCHANGE")"
      fi
      URLS+=("${ODDPOOL_BASE_URL%/}/search/recent/markets?${query}")
      if [[ "$ODDPOOL_INCLUDE_RECENT_EVENTS" == "1" ]]; then
        URLS+=("${ODDPOOL_BASE_URL%/}/search/recent/events?${query}")
      fi
      if [[ -n "$ODDPOOL_SEARCH_QUERIES" ]]; then
        IFS=',' read -r -a oddpool_queries <<< "$ODDPOOL_SEARCH_QUERIES"
        for oddpool_query in "${oddpool_queries[@]}"; do
          oddpool_query="${oddpool_query#"${oddpool_query%%[![:space:]]*}"}"
          oddpool_query="${oddpool_query%"${oddpool_query##*[![:space:]]}"}"
          [[ -n "$oddpool_query" ]] || continue
          URLS+=("${ODDPOOL_BASE_URL%/}/search/markets?q=$(urlencode_query "$oddpool_query")&limit=${ODDPOOL_SEARCH_LIMIT}")
        done
      fi
    fi
  else
    URL="${URL:-${ODDPOOL_API_URL:-${EXTERNAL_SIGNAL_URL:-}}}"
    if [[ -n "$URL" ]]; then
      URLS+=("$URL")
    fi
  fi
fi

if [[ -z "$INPUT_PATH" && "${#URLS[@]}" -eq 0 ]]; then
  echo "external_signals=0 reason=no_INPUT_PATH_or_URL out=$OUT"
  exit 0
fi

args=(ingest-external-signals --source "$SOURCE" --out "$OUT" --timeout "$TIMEOUT")
if [[ -n "$INPUT_PATH" ]]; then
  args+=(--input "$INPUT_PATH")
else
  for url in "${URLS[@]}"; do
    args+=(--url "$url")
  done
  args+=(--proxy "$PROXY")
  if [[ "$SOURCE" == "oddpool" && -n "${ODDPOOL_API_KEY:-}" ]]; then
    args+=(--header "X-API-Key=${ODDPOOL_API_KEY}")
  fi
  if [[ "$SOURCE" == "oddpool" && "$ODDPOOL_PLAN_NORMALIZED" == "free" ]]; then
    args+=(
      --oddpool-quota-state "$ODDPOOL_QUOTA_STATE"
      --oddpool-monthly-quota "$ODDPOOL_MONTHLY_QUOTA"
      --oddpool-min-interval-seconds "$ODDPOOL_MIN_INTERVAL_SECONDS"
    )
  fi
fi
set +e
"$PYTHON_BIN" -m poly_strategy.cli "${args[@]}"
status=$?
set -e
if [[ "$status" != "0" ]]; then
  echo "external_signals_error status=$status source=$SOURCE urls=${URLS[*]:-} out=$OUT"
  if [[ "$ALLOW_EXTERNAL_SIGNAL_FAILURE" == "1" ]]; then
    exit 0
  fi
  exit "$status"
fi

if [[ "$REFRESH_WATCHLIST" == "1" ]]; then
  SKIP_GAMMA=1 SKIP_LLM=1 EXTERNAL_SIGNALS="$OUT" scripts/refresh_discovery_watchlist.sh
fi
