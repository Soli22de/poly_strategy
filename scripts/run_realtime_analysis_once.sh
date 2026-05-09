#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
REPORT="${REPORT:-data/realtime-monitor-24h-v1.jsonl}"
SNAPSHOTS="${SNAPSHOTS:-data/realtime-monitor-24h-v1-snapshots.ndjson}"
RULES="${RULES:-data/gpt55-candidate-rules-all.json}"
GAMMA="${GAMMA:-data/polymarket-gamma.ndjson}"
OUT="${OUT:-data/realtime-monitor-24h-v1-analysis.json}"
NEAR_MISS_MIN_NET_EDGE="${NEAR_MISS_MIN_NET_EDGE:-0.002}"
NEAR_MISS_TOP="${NEAR_MISS_TOP:-20}"
ALLOW_ANALYSIS_FAILURE="${ALLOW_ANALYSIS_FAILURE:-1}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "missing python: $PYTHON_BIN" >&2
  exit 1
fi

if [[ ! -s "$REPORT" || ! -s "$SNAPSHOTS" ]]; then
  echo "realtime_analysis_skipped reason=missing_report_or_snapshots report=$REPORT snapshots=$SNAPSHOTS"
  exit 0
fi

args=(
  monitor-analyze "$REPORT"
  --snapshots "$SNAPSHOTS"
  --rules "$RULES"
  --gamma "$GAMMA"
  --near-miss-min-net-edge "$NEAR_MISS_MIN_NET_EDGE"
  --near-miss-top "$NEAR_MISS_TOP"
  --out "$OUT"
)

set +e
"$PYTHON_BIN" -m poly_strategy.cli "${args[@]}"
status=$?
set -e
if [[ "$status" != "0" ]]; then
  echo "realtime_analysis_error status=$status report=$REPORT snapshots=$SNAPSHOTS out=$OUT"
  if [[ "$ALLOW_ANALYSIS_FAILURE" == "1" ]]; then
    exit 0
  fi
  exit "$status"
fi
