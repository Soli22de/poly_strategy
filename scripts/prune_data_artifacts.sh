#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DATA_DIR="${DATA_DIR:-data}"
DRY_RUN="${DRY_RUN:-0}"
DATED_CACHE_RETENTION_DAYS="${DATED_CACHE_RETENTION_DAYS:-7}"
GZIP_RETENTION_DAYS="${GZIP_RETENTION_DAYS:-7}"

mkdir -p "$DATA_DIR"

run_rm() {
  local path="$1"
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "would_delete path=$path"
    return 0
  fi
  echo "delete path=$path"
  rm -f "$path"
}

delete_globs() {
  shopt -s nullglob
  local path
  for path in "$@"; do
    [[ -f "$path" ]] || continue
    run_rm "$path"
  done
  shopt -u nullglob
}

delete_old_glob() {
  local days="$1"
  shift
  shopt -s nullglob
  local path
  for path in "$@"; do
    [[ -f "$path" ]] || continue
    if [[ "$DRY_RUN" == "1" ]]; then
      find "$path" -type f -mtime +"$days" -print | sed 's/^/would_delete path=/'
    else
      find "$path" -type f -mtime +"$days" -print -delete | sed 's/^/delete path=/'
    fi
  done
  shopt -u nullglob
}

# Disposable outputs from smoke tests, manual probes, provider experiments, and one-off backtests.
delete_globs \
  "$DATA_DIR"/*.compact.tmp \
  "$DATA_DIR"/*.promotion.* \
  "$DATA_DIR"/*.tmp.* \
  "$DATA_DIR"/*.trim.tmp \
  "$DATA_DIR"/tmp-* \
  "$DATA_DIR"/*-smoke* \
  "$DATA_DIR"/sample*.ndjson \
  "$DATA_DIR"/book-test.ndjson \
  "$DATA_DIR"/current-check.ndjson \
  "$DATA_DIR"/current-live-check.ndjson \
  "$DATA_DIR"/empty-rules.json \
  "$DATA_DIR"/execute-refresh-*.ndjson \
  "$DATA_DIR"/execution-plans-*.ndjson \
  "$DATA_DIR"/execution-pretrade-*.ndjson \
  "$DATA_DIR"/expanded-opportunity-refresh-*.ndjson \
  "$DATA_DIR"/expanded-scan-1000-* \
  "$DATA_DIR"/expanded-candidate-groups-* \
  "$DATA_DIR"/external-signals-smoke.ndjson \
  "$DATA_DIR"/glm51-* \
  "$DATA_DIR"/gpt55-candidate-rules.json \
  "$DATA_DIR"/gpt55-live-binaries.ndjson \
  "$DATA_DIR"/llm-discovery-smoke.json \
  "$DATA_DIR"/live-binaries.ndjson \
  "$DATA_DIR"/live-final-smoke.ndjson \
  "$DATA_DIR"/live-smoke.ndjson \
  "$DATA_DIR"/paper-monitor-*smoke* \
  "$DATA_DIR"/paper-monitor-2h-* \
  "$DATA_DIR"/paper-monitor-24h-* \
  "$DATA_DIR"/paper-report-*smoke* \
  "$DATA_DIR"/polymarket-gamma-gpt55.ndjson \
  "$DATA_DIR"/realtime-expanded-1000-* \
  "$DATA_DIR"/rule-markets-*smoke*.ndjson \
  "$DATA_DIR"/rule-markets-targeted-postreview.ndjson \
  "$DATA_DIR"/rule-monitor-*smoke*.ndjson \
  "$DATA_DIR"/rule-monitor-targeted-postreview.ndjson \
  "$DATA_DIR"/watchlist-expanded-1000.json

# Dated external/cross-platform caches are useful briefly, but can be regenerated.
delete_old_glob "$DATED_CACHE_RETENTION_DAYS" \
  "$DATA_DIR"/kalshi-open-*.ndjson \
  "$DATA_DIR"/kalshi-open-events-*.ndjson \
  "$DATA_DIR"/kalshi-series-*.json \
  "$DATA_DIR"/cross-platform-*.json \
  "$DATA_DIR"/cross-platform-*.ndjson

delete_old_glob "$GZIP_RETENTION_DAYS" "$DATA_DIR"/*.gz

echo "prune_done dry_run=$DRY_RUN data_dir=$DATA_DIR dated_cache_retention_days=$DATED_CACHE_RETENTION_DAYS gzip_retention_days=$GZIP_RETENTION_DAYS"
