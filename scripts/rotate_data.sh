#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DATA_DIR="${DATA_DIR:-data}"
MAX_BYTES="${MAX_BYTES:-104857600}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
DRY_RUN="${DRY_RUN:-0}"
INCLUDE_REPORTS="${INCLUDE_REPORTS:-0}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOCK_DIR="$DATA_DIR/.rotate.lock"

mkdir -p "$DATA_DIR"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "rotation_skipped reason=lock_exists lock=$LOCK_DIR"
  exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

patterns=(
  "$DATA_DIR/*snapshots*.ndjson"
  "$DATA_DIR/*updates*.ndjson"
  "$DATA_DIR/*raw*.ndjson"
  "$DATA_DIR/*books*.ndjson"
  "$DATA_DIR/*.log"
)
if [[ "$INCLUDE_REPORTS" == "1" ]]; then
  patterns+=("$DATA_DIR/*.jsonl")
fi

rotate_file() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  local size
  size="$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file")"
  if (( size <= MAX_BYTES )); then
    return 0
  fi
  local rotated="${file}.${TIMESTAMP}"
  echo "rotate file=$file size=$size rotated=${rotated}.gz dry_run=$DRY_RUN"
  if [[ "$DRY_RUN" == "1" ]]; then
    return 0
  fi
  cp "$file" "$rotated"
  : > "$file"
  gzip -f "$rotated"
}

shopt -s nullglob
for pattern in "${patterns[@]}"; do
  for file in $pattern; do
    [[ "$file" == *.gz ]] && continue
    rotate_file "$file"
  done
done

if [[ "$DRY_RUN" == "1" ]]; then
  find "$DATA_DIR" -name '*.gz' -mtime +"$RETENTION_DAYS" -print | sed 's/^/would_delete /'
else
  find "$DATA_DIR" -name '*.gz' -mtime +"$RETENTION_DAYS" -print -delete
fi
