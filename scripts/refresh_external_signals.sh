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
URL="${URL:-${ODDPOOL_API_URL:-${EXTERNAL_SIGNAL_URL:-}}}"
OUT="${OUT:-data/external-signals.ndjson}"
PROXY="${PROXY:-127.0.0.1:10808}"
TIMEOUT="${TIMEOUT:-10}"
REFRESH_WATCHLIST="${REFRESH_WATCHLIST:-1}"
ALLOW_EXTERNAL_SIGNAL_FAILURE="${ALLOW_EXTERNAL_SIGNAL_FAILURE:-1}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "missing python: $PYTHON_BIN" >&2
  exit 1
fi

if [[ -z "$INPUT_PATH" && -z "$URL" ]]; then
  echo "external_signals=0 reason=no_INPUT_PATH_or_URL out=$OUT"
  exit 0
fi

args=(ingest-external-signals --source "$SOURCE" --out "$OUT" --timeout "$TIMEOUT")
if [[ -n "$INPUT_PATH" ]]; then
  args+=(--input "$INPUT_PATH")
else
  args+=(--url "$URL" --proxy "$PROXY")
  if [[ "$SOURCE" == "oddpool" && -n "${ODDPOOL_API_KEY:-}" ]]; then
    args+=(--header "X-API-Key=${ODDPOOL_API_KEY}")
  fi
fi
set +e
"$PYTHON_BIN" -m poly_strategy.cli "${args[@]}"
status=$?
set -e
if [[ "$status" != "0" ]]; then
  echo "external_signals_error status=$status source=$SOURCE url=$URL out=$OUT"
  if [[ "$ALLOW_EXTERNAL_SIGNAL_FAILURE" == "1" ]]; then
    exit 0
  fi
  exit "$status"
fi

if [[ "$REFRESH_WATCHLIST" == "1" ]]; then
  SKIP_GAMMA=1 SKIP_LLM=1 EXTERNAL_SIGNALS="$OUT" scripts/refresh_discovery_watchlist.sh
fi
