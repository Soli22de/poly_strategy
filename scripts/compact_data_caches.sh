#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
GAMMA="${GAMMA:-data/polymarket-gamma.ndjson}"
EXTERNAL_SIGNALS="${EXTERNAL_SIGNALS:-data/external-signals.ndjson}"
MAX_EXTERNAL_SIGNAL_LINES="${MAX_EXTERNAL_SIGNAL_LINES:-2000}"
DRY_RUN="${DRY_RUN:-0}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "missing python: $PYTHON_BIN" >&2
  exit 1
fi

"$PYTHON_BIN" - "$GAMMA" "$EXTERNAL_SIGNALS" "$MAX_EXTERNAL_SIGNAL_LINES" "$DRY_RUN" <<'PY'
import json
import os
import sys
from pathlib import Path

gamma_path = Path(sys.argv[1])
signals_path = Path(sys.argv[2])
max_signal_lines = int(sys.argv[3])
dry_run = sys.argv[4] == "1"


def compact_gamma(path: Path) -> None:
    if not path.exists() or path.stat().st_size == 0:
        print(f"compact_gamma_skipped path={path} reason=missing_or_empty")
        return
    latest_by_market_id = {}
    order = []
    input_rows = 0
    malformed_rows = 0
    with path.open() as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            input_rows += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                malformed_rows += 1
                continue
            if row.get("type") != "raw_polymarket_gamma_market":
                continue
            raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
            market_id = str(row.get("market_id") or raw.get("id") or raw.get("conditionId") or "")
            if not market_id:
                malformed_rows += 1
                continue
            if market_id not in latest_by_market_id:
                order.append(market_id)
            latest_by_market_id[market_id] = row
    output_rows = len(latest_by_market_id)
    before_bytes = path.stat().st_size
    print(
        "compact_gamma "
        f"path={path} input_rows={input_rows} output_rows={output_rows} "
        f"malformed_rows={malformed_rows} before_bytes={before_bytes} dry_run={int(dry_run)}"
    )
    if dry_run:
        return
    tmp = path.with_suffix(path.suffix + ".compact.tmp")
    with tmp.open("w") as handle:
        for market_id in order:
            handle.write(json.dumps(latest_by_market_id[market_id], sort_keys=True) + "\n")
    os.replace(tmp, path)
    print(f"compact_gamma_done path={path} after_bytes={path.stat().st_size}")


def trim_tail(path: Path, max_lines: int) -> None:
    if max_lines < 1:
        raise ValueError("max lines must be at least 1")
    if not path.exists() or path.stat().st_size == 0:
        print(f"trim_tail_skipped path={path} reason=missing_or_empty")
        return
    with path.open("rb") as handle:
        lines = handle.read().splitlines()
    before_lines = len(lines)
    if before_lines <= max_lines:
        print(f"trim_tail_skipped path={path} lines={before_lines} max_lines={max_lines}")
        return
    kept = lines[-max_lines:]
    print(f"trim_tail path={path} before_lines={before_lines} after_lines={len(kept)} dry_run={int(dry_run)}")
    if dry_run:
        return
    tmp = path.with_suffix(path.suffix + ".trim.tmp")
    with tmp.open("wb") as handle:
        handle.write(b"\n".join(kept) + b"\n")
    os.replace(tmp, path)


compact_gamma(gamma_path)
trim_tail(signals_path, max_signal_lines)
PY
