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
SNAPSHOTS="${SNAPSHOTS:-data/realtime-monitor-24h-v1-snapshots.ndjson}"
REPORT_OUT="${REPORT_OUT:-data/exhaustive-group-promotion.json}"
STATE="${STATE:-data/exhaustive-group-promotion-state.json}"
MIN_NET_EDGE="${MIN_NET_EDGE:-0.002}"
TOP="${TOP:-5}"
MIN_CONFIDENCE="${MIN_CONFIDENCE:-0.95}"
RECHECK_HOURS="${RECHECK_HOURS:-24}"
TIMEOUT="${TIMEOUT:-120}"
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

candidate_count="$("$PYTHON_BIN" - "$SNAPSHOTS" "$RULES" "$MIN_NET_EDGE" "$TOP" <<'PY'
import sys
from pathlib import Path
from poly_strategy.exhaustive_groups import promotion_candidate_count

snapshots, rules, min_edge, top = sys.argv[1], sys.argv[2], float(sys.argv[3]), int(sys.argv[4])
print(promotion_candidate_count(Path(snapshots), Path(rules), min_net_edge=min_edge, top_n=top))
PY
)"
if [[ "$candidate_count" == "0" ]]; then
  echo "rule_promotion_skipped reason=no_positive_diagnostic_candidates min_net_edge=$MIN_NET_EDGE top=$TOP"
  exit 0
fi

rules_tmp="$(mktemp "${RULES}.promotion.XXXXXX")"
args=(
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
if [[ -n "${OPENAI_MODEL:-}" ]]; then
  args+=(--model "$OPENAI_MODEL")
fi
if [[ -n "${OPENAI_BASE_URL:-}" ]]; then
  args+=(--base-url "$OPENAI_BASE_URL")
fi
if [[ -n "$VERBOSITY" ]]; then
  args+=(--verbosity "$VERBOSITY")
fi

set +e
"$PYTHON_BIN" -m poly_strategy.cli "${args[@]}"
status=$?
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
