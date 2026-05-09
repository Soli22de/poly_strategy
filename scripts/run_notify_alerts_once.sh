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
ALERTS_PATH="${ALERTS_PATH:-data/realtime-monitor-24h-v1-alerts.ndjson}"
NOTIFY_OUT="${NOTIFY_OUT:-data/realtime-monitor-24h-v1-notifications.ndjson}"
MAX_ALERTS="${MAX_ALERTS:-20}"
TIMEOUT="${TIMEOUT:-10}"
PROXY="${PROXY:-}"
DRY_RUN="${DRY_RUN:-0}"
DESKTOP="${DESKTOP:-0}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "missing python: $PYTHON_BIN" >&2
  exit 1
fi

if [[ ! -s "$ALERTS_PATH" ]]; then
  echo "alerts=0 notifications=0 out=$NOTIFY_OUT"
  exit 0
fi

args=(
  notify-alerts "$ALERTS_PATH"
  --out "$NOTIFY_OUT"
  --max-alerts "$MAX_ALERTS"
  --timeout "$TIMEOUT"
)

if [[ -n "$PROXY" ]]; then
  args+=(--proxy "$PROXY")
fi
if [[ -n "${ALERT_WEBHOOK_URL:-}" ]]; then
  args+=(--webhook-url "$ALERT_WEBHOOK_URL")
fi
if [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "${TELEGRAM_CHAT_ID:-}" ]]; then
  args+=(--telegram-bot-token "$TELEGRAM_BOT_TOKEN" --telegram-chat-id "$TELEGRAM_CHAT_ID")
fi
if [[ -n "${DISCORD_WEBHOOK_URL:-}" ]]; then
  args+=(--discord-webhook-url "$DISCORD_WEBHOOK_URL")
fi
if [[ "$DESKTOP" == "1" ]]; then
  args+=(--desktop)
fi
if [[ "$DRY_RUN" == "1" ]]; then
  args+=(--dry-run)
fi

exec "$PYTHON_BIN" -m poly_strategy.cli "${args[@]}"
