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
GAMMA="${GAMMA:-data/polymarket-gamma.ndjson}"
RULES="${RULES:-data/gpt55-candidate-rules-all.json}"
WATCHLIST="${WATCHLIST:-data/watchlist-current.json}"
EXTERNAL_SIGNALS="${EXTERNAL_SIGNALS:-data/external-signals.ndjson}"
REFRESH_EXTERNAL_SIGNAL_MARKETS="${REFRESH_EXTERNAL_SIGNAL_MARKETS:-1}"
EXTERNAL_SIGNAL_MARKET_LIMIT="${EXTERNAL_SIGNAL_MARKET_LIMIT:-1000}"
EXTERNAL_SIGNAL_MARKET_REPORT="${EXTERNAL_SIGNAL_MARKET_REPORT:-data/external-signal-market-refresh.json}"
EXTERNAL_SIGNAL_MARKET_WORKERS="${EXTERNAL_SIGNAL_MARKET_WORKERS:-8}"
PROXY="${PROXY:-127.0.0.1:10808}"
if [[ -n "$PROXY" && -z "${HTTPS_PROXY:-}" ]]; then
  export HTTPS_PROXY="http://${PROXY}"
  export HTTP_PROXY="http://${PROXY}"
fi
LIMIT="${LIMIT:-100}"
PAGES="${PAGES:-5}"
OFFSET="${OFFSET:-0}"
TIMEOUT="${TIMEOUT:-15}"
BATCH_SIZE="${BATCH_SIZE:-10}"
CONTEXT_MARKET_LIMIT="${CONTEXT_MARKET_LIMIT:-20}"
LLM_WORKERS="${LLM_WORKERS:-4}"
LLM_ERROR_RETRIES="${LLM_ERROR_RETRIES:-2}"
LLM_ERROR_RETRY_BATCH_SIZE="${LLM_ERROR_RETRY_BATCH_SIZE:-1}"
LLM_TIMEOUT="${LLM_TIMEOUT:-120}"
LLM_COMMAND_TIMEOUT="${LLM_COMMAND_TIMEOUT:-900}"
LLM_RETRIES="${LLM_RETRIES:-2}"
LLM_CHAT_TIMEOUT="${LLM_CHAT_TIMEOUT:-25}"
LLM_CHAT_COMMAND_TIMEOUT="${LLM_CHAT_COMMAND_TIMEOUT:-300}"
LLM_CHAT_RETRIES="${LLM_CHAT_RETRIES:-0}"
LLM_PROVIDER_HEALTHCHECK="${LLM_PROVIDER_HEALTHCHECK:-1}"
LLM_HEALTH_TIMEOUT="${LLM_HEALTH_TIMEOUT:-20}"
LLM_MAX_OUTPUT_TOKENS="${LLM_MAX_OUTPUT_TOKENS:-4000}"
LLM_REASONING_EFFORT="${LLM_REASONING_EFFORT:-high}"
LLM_VERBOSITY="${LLM_VERBOSITY:-}"
LLM_TOPIC_CLUSTER="${LLM_TOPIC_CLUSTER:-1}"
LLM_MAX_NEW_MARKETS_PER_REFRESH="${LLM_MAX_NEW_MARKETS_PER_REFRESH:-240}"
ALLOW_LLM_FAILURE="${ALLOW_LLM_FAILURE:-1}"
MIN_CONFIDENCE="${MIN_CONFIDENCE:-0.95}"
INCLUDE_TOP_MARKETS="${INCLUDE_TOP_MARKETS:-400}"
INCLUDE_TOP_NEG_RISK_GROUPS="${INCLUDE_TOP_NEG_RISK_GROUPS:-60}"
MIN_LIQUIDITY="${MIN_LIQUIDITY:-0}"
MIN_VOLUME_24H="${MIN_VOLUME_24H:-0}"
MAX_WATCHLIST_MARKETS="${MAX_WATCHLIST_MARKETS:-1000}"
RESTART_ON_CHANGE="${RESTART_ON_CHANGE:-0}"
RESTART_SCRIPT="${RESTART_SCRIPT:-scripts/restart_realtime_monitor.sh}"
SKIP_GAMMA="${SKIP_GAMMA:-0}"
SKIP_LLM="${SKIP_LLM:-0}"
PRIMARY_MODEL="${OPENAI_MODEL:-}"
PRIMARY_BASE_URL="${OPENAI_BASE_URL:-}"
PRIMARY_API_MODE="${OPENAI_API_MODE:-}"
PRIMARY_API_KEY="${OPENAI_API_KEY:-}"
BACKUP_MODEL="${OPENAI_BACKUP_MODEL:-}"
BACKUP_BASE_URL="${OPENAI_BACKUP_BASE_URL:-}"
BACKUP_API_MODE="${OPENAI_BACKUP_API_MODE:-}"
BACKUP_API_KEY="${OPENAI_BACKUP_API_KEY:-}"
FALLBACK_MODEL="${OPENAI_FALLBACK_MODEL:-${LLM_FALLBACK_MODEL:-}}"
FALLBACK_BASE_URL="${OPENAI_FALLBACK_BASE_URL:-${OPENAI_BASE_URL:-}}"
FALLBACK_API_MODE="${OPENAI_FALLBACK_API_MODE:-${OPENAI_API_MODE:-}}"
FALLBACK_API_KEY="${OPENAI_FALLBACK_API_KEY:-${OPENAI_API_KEY:-}}"

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

discovery_error_count() {
  local path="$1"
  "$PYTHON_BIN" - "$path" <<'PY'
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
if not path.exists() or not path.read_text().strip():
    print(0)
else:
    row = json.loads(path.read_text())
    print(len(row.get("discovery_errors") or []))
PY
}

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
      echo "command_timeout seconds=$limit_seconds pid=$pid" >&2
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

provider_health_check() {
  local label="$1"
  local model="$2"
  local base_url="$3"
  local api_mode="$4"
  local api_key="$5"
  if [[ "$LLM_PROVIDER_HEALTHCHECK" != "1" ]]; then
    return 0
  fi
  [[ -n "$model" ]] || return 1
  echo "provider_health_check label=$label model=$model api_mode=${api_mode:-default} base_url=${base_url:-default}"
  if [[ -n "$api_key" ]]; then
    OPENAI_API_KEY="$api_key" OPENAI_BASE_URL="$base_url" OPENAI_API_MODE="$api_mode" "$PYTHON_BIN" - "$model" "$base_url" "$api_mode" "$LLM_HEALTH_TIMEOUT" <<'PY'
import sys
from poly_strategy.openai_rules import OpenAIRuleDiscoveryClient
from poly_strategy.rule_discovery import MarketText

model, base_url, api_mode, timeout = sys.argv[1], sys.argv[2] or None, sys.argv[3] or None, float(sys.argv[4])
market = MarketText(
    "healthcheck",
    "Will Bitcoin be above $100,000 by December 31, 2026?",
    "Resolves Yes if Bitcoin trades above $100,000 before the deadline.",
    ["Yes", "No"],
    "2026-12-31",
    "Crypto",
    "bitcoin-above-100k-2026",
)
try:
    client = OpenAIRuleDiscoveryClient(
        model=model,
        timeout=timeout,
        base_url=base_url,
        retries=0,
        max_output_tokens=800,
        reasoning_effort="high",
        api_mode=api_mode,
    )
    client.discover_relations([market])
except Exception as exc:
    print(f"provider_health_error type={exc.__class__.__name__} message={str(exc)[:240]}", file=sys.stderr)
    raise SystemExit(42)
print("provider_health_ok=1")
PY
  else
    "$PYTHON_BIN" - "$model" "$base_url" "$api_mode" "$LLM_HEALTH_TIMEOUT" <<'PY'
import sys
from poly_strategy.openai_rules import OpenAIRuleDiscoveryClient
from poly_strategy.rule_discovery import MarketText

model, base_url, api_mode, timeout = sys.argv[1], sys.argv[2] or None, sys.argv[3] or None, float(sys.argv[4])
market = MarketText(
    "healthcheck",
    "Will Bitcoin be above $100,000 by December 31, 2026?",
    "Resolves Yes if Bitcoin trades above $100,000 before the deadline.",
    ["Yes", "No"],
    "2026-12-31",
    "Crypto",
    "bitcoin-above-100k-2026",
)
try:
    client = OpenAIRuleDiscoveryClient(
        model=model,
        timeout=timeout,
        base_url=base_url,
        retries=0,
        max_output_tokens=800,
        reasoning_effort="high",
        api_mode=api_mode,
    )
    client.discover_relations([market])
except Exception as exc:
    print(f"provider_health_error type={exc.__class__.__name__} message={str(exc)[:240]}", file=sys.stderr)
    raise SystemExit(42)
print("provider_health_ok=1")
PY
  fi
}

run_discovery_provider() {
  local label="$1"
  local model="$2"
  local base_url="$3"
  local api_mode="$4"
  local api_key="$5"
  local cache_path="$6"
  local out_path="$7"
  local request_timeout="$LLM_TIMEOUT"
  local request_retries="$LLM_RETRIES"
  case "${api_mode:-}" in
    chat|chat_completions|chat-completions|chatcompletions)
      request_timeout="$LLM_CHAT_TIMEOUT"
      request_retries="$LLM_CHAT_RETRIES"
      ;;
  esac
  local args=(
    discover-rules
    --raw "$GAMMA"
    --out "$out_path"
    --cache "$cache_path"
    --batch-size "$BATCH_SIZE"
    --context-market-limit "$CONTEXT_MARKET_LIMIT"
    --client-workers "$LLM_WORKERS"
    --retry-failed-batches "$LLM_ERROR_RETRIES"
    --retry-failed-batch-size "$LLM_ERROR_RETRY_BATCH_SIZE"
    --min-confidence "$MIN_CONFIDENCE"
    --timeout "$request_timeout"
    --retries "$request_retries"
    --max-output-tokens "$LLM_MAX_OUTPUT_TOKENS"
    --reasoning-effort "$LLM_REASONING_EFFORT"
    --continue-on-client-error
  )
  if [[ -n "$model" ]]; then
    args+=(--model "$model")
  fi
  if [[ -n "$base_url" ]]; then
    args+=(--base-url "$base_url")
  fi
  if [[ -n "$api_mode" ]]; then
    args+=(--api-mode "$api_mode")
  fi
  if [[ -n "$LLM_VERBOSITY" ]]; then
    args+=(--verbosity "$LLM_VERBOSITY")
  fi
  if [[ "$LLM_TOPIC_CLUSTER" == "1" ]]; then
    args+=(--topic-cluster)
  fi
  if [[ -n "$LLM_MAX_NEW_MARKETS_PER_REFRESH" && "$LLM_MAX_NEW_MARKETS_PER_REFRESH" != "0" ]]; then
    args+=(--max-new-markets "$LLM_MAX_NEW_MARKETS_PER_REFRESH")
  fi
  echo "discover_provider label=$label model=$model api_mode=${api_mode:-default} base_url=${base_url:-default} cache=$cache_path out=$out_path"
  if [[ -n "$api_key" ]]; then
    OPENAI_API_KEY="$api_key" OPENAI_BASE_URL="$base_url" OPENAI_API_MODE="$api_mode" "$PYTHON_BIN" -m poly_strategy.cli "${args[@]}"
  else
    "$PYTHON_BIN" -m poly_strategy.cli "${args[@]}"
  fi
}

provider_command_timeout() {
  local api_mode="$1"
  case "${api_mode:-}" in
    chat|chat_completions|chat-completions|chatcompletions)
      echo "$LLM_CHAT_COMMAND_TIMEOUT"
      ;;
    *)
      echo "$LLM_COMMAND_TIMEOUT"
      ;;
  esac
}

if [[ "$SKIP_LLM" != "1" && -n "$PRIMARY_MODEL" ]]; then
  current_cache="$RULES"
  current_rules=""
  tmp_paths=()
  final_status=0
  for spec in \
    "primary|$PRIMARY_MODEL|$PRIMARY_BASE_URL|$PRIMARY_API_MODE|$PRIMARY_API_KEY" \
    "backup|$BACKUP_MODEL|$BACKUP_BASE_URL|$BACKUP_API_MODE|$BACKUP_API_KEY" \
    "fallback|$FALLBACK_MODEL|$FALLBACK_BASE_URL|$FALLBACK_API_MODE|$FALLBACK_API_KEY"; do
    IFS='|' read -r label model base_url api_mode api_key <<< "$spec"
    [[ -n "$model" ]] || continue
    set +e
    provider_health_check "$label" "$model" "$base_url" "$api_mode" "$api_key"
    health_status=$?
    set -e
    if [[ "$health_status" != "0" ]]; then
      final_status="$health_status"
      echo "discover_provider_skip label=$label reason=healthcheck_failed status=$health_status"
      continue
    fi
    stage_out="$(mktemp "${RULES}.tmp.XXXXXX")"
    tmp_paths+=("$stage_out")
    command_timeout="$(provider_command_timeout "$api_mode")"
    set +e
    run_with_timeout "$command_timeout" run_discovery_provider "$label" "$model" "$base_url" "$api_mode" "$api_key" "$current_cache" "$stage_out"
    status=$?
    set -e
    stage_used=0
    if [[ "$status" == "0" || -s "$stage_out" ]]; then
      current_cache="$stage_out"
      current_rules="$stage_out"
      stage_used=1
    fi
    final_status="$status"
    if [[ "$stage_used" == "0" ]]; then
      echo "discover_provider_done label=$label status=$status unresolved_errors=unknown output_written=0"
      continue
    fi
    errors="$(discovery_error_count "$current_cache")"
    echo "discover_provider_done label=$label status=$status unresolved_errors=$errors output_written=1"
    if [[ "$errors" == "0" ]]; then
      final_status=0
      break
    fi
  done
  if [[ -n "$current_rules" && -s "$current_rules" ]]; then
    mv "$current_rules" "$RULES"
    for path in "${tmp_paths[@]}"; do
      [[ "$path" == "$current_rules" ]] || rm -f "$path"
    done
  elif [[ "$ALLOW_LLM_FAILURE" == "1" && -s "$RULES" ]]; then
    echo "discover_rules_failed status=$final_status using_existing_rules=$RULES" >&2
    for path in "${tmp_paths[@]}"; do
      rm -f "$path"
    done
  else
    for path in "${tmp_paths[@]}"; do rm -f "$path"; done
    exit "$final_status"
  fi
else
  echo "skip_llm=1 or OPENAI_MODEL is empty; reusing existing rule cache: $RULES"
fi

if [[ "$REFRESH_EXTERNAL_SIGNAL_MARKETS" == "1" && -s "$EXTERNAL_SIGNALS" ]]; then
  "$PYTHON_BIN" -m poly_strategy.cli collect-external-signal-markets \
    --external-signals "$EXTERNAL_SIGNALS" \
    --out "$GAMMA" \
    --report-out "$EXTERNAL_SIGNAL_MARKET_REPORT" \
    --limit "$EXTERNAL_SIGNAL_MARKET_LIMIT" \
    --max-workers "$EXTERNAL_SIGNAL_MARKET_WORKERS" \
    --timeout "$TIMEOUT" \
    --proxy "$PROXY" \
    --skip-errors
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
