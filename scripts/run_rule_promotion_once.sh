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
if [[ -f scripts/load_llm_research_profile.sh ]]; then
  # shellcheck disable=SC1091
  source scripts/load_llm_research_profile.sh
fi

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
GAMMA="${GAMMA:-data/polymarket-gamma.ndjson}"
RULES="${RULES:-data/gpt55-candidate-rules-all.json}"
SNAPSHOTS="${SNAPSHOTS:-data/realtime-monitor-24h-v1-snapshots.ndjson}"
REPORT_OUT="${REPORT_OUT:-data/exhaustive-group-promotion.json}"
STATE="${STATE:-data/exhaustive-group-promotion-state.json}"
PRIMARY_MODEL="${OPENAI_MODEL:-}"
PRIMARY_BASE_URL="${OPENAI_BASE_URL:-}"
PRIMARY_API_MODE="${OPENAI_API_MODE:-}"
PRIMARY_API_KEY="${OPENAI_API_KEY:-}"
SECONDARY_MODEL="${OPENAI_SECONDARY_MODEL:-}"
SECONDARY_BASE_URL="${OPENAI_SECONDARY_BASE_URL:-}"
SECONDARY_API_MODE="${OPENAI_SECONDARY_API_MODE:-}"
SECONDARY_API_KEY="${OPENAI_SECONDARY_API_KEY:-}"
BACKUP_MODEL="${OPENAI_BACKUP_MODEL:-}"
BACKUP_BASE_URL="${OPENAI_BACKUP_BASE_URL:-}"
BACKUP_API_MODE="${OPENAI_BACKUP_API_MODE:-}"
BACKUP_API_KEY="${OPENAI_BACKUP_API_KEY:-}"
FALLBACK_MODEL="${OPENAI_FALLBACK_MODEL:-${LLM_FALLBACK_MODEL:-}}"
FALLBACK_BASE_URL="${OPENAI_FALLBACK_BASE_URL:-${OPENAI_BASE_URL:-}}"
FALLBACK_API_MODE="${OPENAI_FALLBACK_API_MODE:-${OPENAI_API_MODE:-}}"
FALLBACK_API_KEY="${OPENAI_FALLBACK_API_KEY:-${OPENAI_API_KEY:-}}"
MIN_NET_EDGE="${MIN_NET_EDGE:-0.002}"
TOP="${TOP:-20}"
MIN_CONFIDENCE="${MIN_CONFIDENCE:-0.95}"
RECHECK_HOURS="${RECHECK_HOURS:-24}"
TIMEOUT="${TIMEOUT:-120}"
COMMAND_TIMEOUT="${COMMAND_TIMEOUT:-600}"
RETRIES="${RETRIES:-2}"
MAX_OUTPUT_TOKENS="${MAX_OUTPUT_TOKENS:-2000}"
REASONING_EFFORT="${REASONING_EFFORT:-high}"
VERBOSITY="${VERBOSITY:-}"
ALLOW_PROMOTION_FAILURE="${ALLOW_PROMOTION_FAILURE:-1}"
REBUILD_WATCHLIST_ON_ADD="${REBUILD_WATCHLIST_ON_ADD:-1}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "missing python: $PYTHON_BIN" >&2
  exit 1
fi

if [[ ! -s "$RULES" || ! -s "$SNAPSHOTS" || ! -s "$GAMMA" ]]; then
  echo "rule_promotion_skipped reason=missing_inputs rules=$RULES snapshots=$SNAPSHOTS gamma=$GAMMA"
  exit 0
fi

candidate_count="$("$PYTHON_BIN" - "$SNAPSHOTS" "$RULES" "$GAMMA" "$MIN_NET_EDGE" "$TOP" <<'PY'
import sys
from pathlib import Path
from poly_strategy.exhaustive_groups import promotion_candidate_count

snapshots, rules, gamma, min_edge, top = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), int(sys.argv[5])
print(promotion_candidate_count(Path(snapshots), Path(rules), min_net_edge=min_edge, top_n=top, gamma_path=Path(gamma)))
PY
)"
if [[ "$candidate_count" == "0" ]]; then
  echo "rule_promotion_skipped reason=no_positive_diagnostic_candidates min_net_edge=$MIN_NET_EDGE top=$TOP"
  exit 0
fi

rules_tmp="$(mktemp "${RULES}.promotion.XXXXXX")"

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

run_verifier() {
  local label="$1"
  local model="$2"
  local base_url="$3"
  local api_mode="$4"
  local api_key="$5"
  local args=(
    verify-exhaustive-groups
    --gamma "$GAMMA"
    --rules-in "$RULES"
    --rules-out "$rules_tmp"
    --snapshots "$SNAPSHOTS"
    --min-net-edge "$MIN_NET_EDGE"
    --top "$TOP"
    --min-confidence "$MIN_CONFIDENCE"
    --timeout "$TIMEOUT"
    --retries "$RETRIES"
    --max-output-tokens "$MAX_OUTPUT_TOKENS"
    --reasoning-effort "$REASONING_EFFORT"
    --report-out "$REPORT_OUT"
    --state "$STATE"
    --recheck-hours "$RECHECK_HOURS"
    --skip-when-no-candidates
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
  if [[ -n "$VERBOSITY" ]]; then
    args+=(--verbosity "$VERBOSITY")
  fi
  echo "rule_promotion_provider label=$label model=$model api_mode=${api_mode:-default} base_url=${base_url:-default}"
  if [[ -n "$api_key" ]]; then
    OPENAI_API_KEY="$api_key" OPENAI_BASE_URL="$base_url" OPENAI_API_MODE="$api_mode" "$PYTHON_BIN" -m poly_strategy.cli "${args[@]}"
  else
    "$PYTHON_BIN" -m poly_strategy.cli "${args[@]}"
  fi
}

set +e
run_with_timeout "$COMMAND_TIMEOUT" run_verifier primary "$PRIMARY_MODEL" "$PRIMARY_BASE_URL" "$PRIMARY_API_MODE" "$PRIMARY_API_KEY"
status=$?
if [[ "$status" != "0" && -n "$SECONDARY_MODEL" ]]; then
  echo "rule_promotion_retry previous_status=$status next_label=secondary next_model=$SECONDARY_MODEL"
  run_with_timeout "$COMMAND_TIMEOUT" run_verifier secondary "$SECONDARY_MODEL" "$SECONDARY_BASE_URL" "$SECONDARY_API_MODE" "$SECONDARY_API_KEY"
  status=$?
fi
if [[ "$status" != "0" && -n "$BACKUP_MODEL" ]]; then
  echo "rule_promotion_retry previous_status=$status next_label=backup next_model=$BACKUP_MODEL"
  run_with_timeout "$COMMAND_TIMEOUT" run_verifier backup "$BACKUP_MODEL" "$BACKUP_BASE_URL" "$BACKUP_API_MODE" "$BACKUP_API_KEY"
  status=$?
fi
if [[ "$status" != "0" && -n "$FALLBACK_MODEL" ]]; then
  echo "rule_promotion_retry previous_status=$status next_label=fallback next_model=$FALLBACK_MODEL"
  run_with_timeout "$COMMAND_TIMEOUT" run_verifier fallback "$FALLBACK_MODEL" "$FALLBACK_BASE_URL" "$FALLBACK_API_MODE" "$FALLBACK_API_KEY"
  status=$?
fi
set -e
if [[ "$status" != "0" ]]; then
  rm -f "$rules_tmp"
  echo "rule_promotion_error status=$status report=$REPORT_OUT"
  if [[ "$ALLOW_PROMOTION_FAILURE" == "1" ]]; then
    exit 0
  fi
  exit "$status"
fi

added_count="$("$PYTHON_BIN" - "$REPORT_OUT" <<'PY'
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
row = json.loads(path.read_text()) if path.exists() and path.read_text().strip() else {}
print(int(row.get("added_count") or 0))
PY
)"
if [[ "$added_count" != "0" ]]; then
  mv "$rules_tmp" "$RULES"
  echo "rule_promotion_added count=$added_count rules=$RULES"
  if [[ "$REBUILD_WATCHLIST_ON_ADD" == "1" ]]; then
    SKIP_GAMMA=1 SKIP_LLM=1 scripts/refresh_discovery_watchlist.sh
  fi
else
  rm -f "$rules_tmp"
  echo "rule_promotion_no_additions candidates=$candidate_count report=$REPORT_OUT"
fi
