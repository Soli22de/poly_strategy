#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "missing python: $PYTHON_BIN" >&2
  exit 1
fi

if [[ -f .env.local ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env.local
  set +a
fi
if [[ -f scripts/load_llm_research_profile.sh ]]; then
  # shellcheck disable=SC1091
  source scripts/load_llm_research_profile.sh
fi

CANDIDATES="${CROSS_PLATFORM_EVENT_CANDIDATES:-data/cross-platform-event-title-candidates.json}"
GAMMA="${GAMMA:-data/polymarket-gamma.ndjson}"
KALSHI_MARKETS="${CROSS_PLATFORM_KALSHI_MARKETS:-data/cross-platform-kalshi-event-markets.ndjson}"
EXPANDED_MATCHES="${CROSS_PLATFORM_EXPANDED_MATCHES:-data/cross-platform-market-candidates.json}"
PREVERIFY_SCAN="${CROSS_PLATFORM_PREVERIFY_SCAN:-data/cross-platform-market-candidates-scan.json}"
OPPORTUNITY_CANDIDATES="${CROSS_PLATFORM_OPPORTUNITY_CANDIDATES:-data/cross-platform-opportunity-candidates-heuristic.json}"
VERIFIED_MATCHES="${CROSS_PLATFORM_VERIFIED_MATCHES:-data/cross-platform-opportunity-candidates-heuristic-verified.json}"
FINAL_SCAN="${CROSS_PLATFORM_FINAL_SCAN:-data/cross-platform-verified-scan-cap100.json}"
SNAPSHOTS="${CROSS_PLATFORM_SNAPSHOTS:-data/cross-platform-snapshots.ndjson}"
FINAL_SNAPSHOTS="${CROSS_PLATFORM_FINAL_SNAPSHOTS:-data/cross-platform-verified-snapshots.ndjson}"
KALSHI_ORDERBOOKS="${CROSS_PLATFORM_KALSHI_ORDERBOOKS:-data/cross-platform-kalshi-orderbooks.ndjson}"
FINAL_KALSHI_ORDERBOOKS="${CROSS_PLATFORM_FINAL_KALSHI_ORDERBOOKS:-data/cross-platform-verified-kalshi-orderbooks.ndjson}"
SIGNALS="${CROSS_PLATFORM_SIGNALS:-data/cross-platform-signals-expanded.ndjson}"
CROSS_PLATFORM_CAPITAL="${CROSS_PLATFORM_MAX_CAPITAL_PER_TRADE:-${BANKROLL:-100}}"
STEP_TIMEOUT="${CROSS_PLATFORM_STEP_TIMEOUT:-300}"

PROXY_ARG=()
if [[ -n "${PROXY:-}" ]]; then
  PROXY_ARG=(--proxy "$PROXY")
fi

run_with_timeout() {
  local limit_seconds="$1"
  shift
  if [[ "$limit_seconds" == "0" ]]; then
    "$@"
    return $?
  fi
  "$@" &
  local pid=$!
  local elapsed=0
  while kill -0 "$pid" >/dev/null 2>&1; do
    if (( elapsed >= limit_seconds )); then
      echo "command_timeout seconds=$limit_seconds pid=$pid command=$*" >&2
      pkill -TERM -P "$pid" >/dev/null 2>&1 || true
      kill -TERM "$pid" >/dev/null 2>&1 || true
      sleep 1
      pkill -KILL -P "$pid" >/dev/null 2>&1 || true
      kill -KILL "$pid" >/dev/null 2>&1 || true
      wait "$pid" >/dev/null 2>&1 || true
      return 124
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  wait "$pid"
}

run_with_timeout "$STEP_TIMEOUT" \
  "$PYTHON_BIN" -m poly_strategy.cli collect-kalshi-event-markets \
  --candidates "$CANDIDATES" \
  --out "$KALSHI_MARKETS" \
  --limit "${CROSS_PLATFORM_KALSHI_LIMIT:-1000}" \
  --timeout "${CROSS_PLATFORM_TIMEOUT:-20}" \
  "${PROXY_ARG[@]}"

run_with_timeout "$STEP_TIMEOUT" \
  "$PYTHON_BIN" -m poly_strategy.cli expand-cross-platform-candidates \
  --candidates "$CANDIDATES" \
  --kalshi-markets "$KALSHI_MARKETS" \
  --polymarket-gamma "$GAMMA" \
  --out "$EXPANDED_MATCHES" \
  --top "${CROSS_PLATFORM_EXPANDED_TOP:-500}" \
  --min-score "${CROSS_PLATFORM_EXPANDED_MIN_SCORE:-0}"

run_with_timeout "$STEP_TIMEOUT" \
  "$PYTHON_BIN" -m poly_strategy.cli scan-cross-platform-once \
  --matches "$EXPANDED_MATCHES" \
  --gamma "$GAMMA" \
  --snapshots-out "$SNAPSHOTS" \
  --kalshi-orderbooks-out "$KALSHI_ORDERBOOKS" \
  --out "$PREVERIFY_SCAN" \
  --timeout "${CROSS_PLATFORM_TIMEOUT:-20}" \
  "${PROXY_ARG[@]}" \
  --book-workers "${CROSS_PLATFORM_BOOK_WORKERS:-12}" \
  --min-net-edge "${CROSS_PLATFORM_PREVERIFY_MIN_EDGE:-0.005}" \
  --include-unverified

run_with_timeout "$STEP_TIMEOUT" \
  "$PYTHON_BIN" -m poly_strategy.cli filter-cross-platform-opportunities \
  --scan "$PREVERIFY_SCAN" \
  --matches "$EXPANDED_MATCHES" \
  --out "$OPPORTUNITY_CANDIDATES" \
  --top "${CROSS_PLATFORM_VERIFY_TOP:-60}" \
  --min-net-edge "${CROSS_PLATFORM_PREVERIFY_MIN_EDGE:-0.005}"

run_with_timeout "${CROSS_PLATFORM_VERIFY_COMMAND_TIMEOUT:-900}" \
  "$PYTHON_BIN" -m poly_strategy.cli verify-cross-platform-matches \
  --matches "$OPPORTUNITY_CANDIDATES" \
  --out "$VERIFIED_MATCHES" \
  --signals-out "$SIGNALS" \
  --top "${CROSS_PLATFORM_VERIFY_TOP:-60}" \
  --batch-size "${CROSS_PLATFORM_VERIFY_BATCH_SIZE:-1}" \
  --client-workers "${CROSS_PLATFORM_VERIFY_WORKERS:-4}" \
  --timeout "${CROSS_PLATFORM_CHAT_TIMEOUT:-30}" \
  --backup-timeout "${CROSS_PLATFORM_BACKUP_TIMEOUT:-30}" \
  --fallback-timeout "${CROSS_PLATFORM_FALLBACK_TIMEOUT:-120}" \
  --retries "${CROSS_PLATFORM_LLM_RETRIES:-1}" \
  --max-output-tokens "${CROSS_PLATFORM_MAX_OUTPUT_TOKENS:-1600}" \
  --reasoning-effort "${CROSS_PLATFORM_REASONING_EFFORT:-high}" \
  --verified-only \
  --continue-on-error

run_with_timeout "$STEP_TIMEOUT" \
  "$PYTHON_BIN" -m poly_strategy.cli scan-cross-platform-once \
  --matches "$VERIFIED_MATCHES" \
  --gamma "$GAMMA" \
  --snapshots-out "$FINAL_SNAPSHOTS" \
  --kalshi-orderbooks-out "$FINAL_KALSHI_ORDERBOOKS" \
  --out "$FINAL_SCAN" \
  --timeout "${CROSS_PLATFORM_TIMEOUT:-20}" \
  "${PROXY_ARG[@]}" \
  --book-workers "${CROSS_PLATFORM_BOOK_WORKERS:-12}" \
  --min-net-edge "${CROSS_PLATFORM_FINAL_MIN_EDGE:-0.005}" \
  --max-capital-per-trade "$CROSS_PLATFORM_CAPITAL"
