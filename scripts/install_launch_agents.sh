#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_DIR="${PLIST_DIR:-$ROOT_DIR/ops/launchd}"
TARGET_DIR="${TARGET_DIR:-$HOME/Library/LaunchAgents}"
DRY_RUN="${DRY_RUN:-0}"
BOOTSTRAP="${BOOTSTRAP:-1}"
DOMAIN="gui/$(id -u)"

mkdir -p "$TARGET_DIR"

for source in "$PLIST_DIR"/*.plist; do
  [[ -f "$source" ]] || continue
  label="$(/usr/libexec/PlistBuddy -c 'Print :Label' "$source")"
  target="$TARGET_DIR/$(basename "$source")"
  echo "install label=$label target=$target dry_run=$DRY_RUN bootstrap=$BOOTSTRAP"
  if [[ "$DRY_RUN" == "1" ]]; then
    continue
  fi
  cp "$source" "$target"
  if [[ "$BOOTSTRAP" == "1" ]]; then
    launchctl bootout "$DOMAIN" "$target" >/dev/null 2>&1 || launchctl remove "$label" >/dev/null 2>&1 || true
    launchctl bootstrap "$DOMAIN" "$target"
    launchctl enable "$DOMAIN/$label" >/dev/null 2>&1 || true
    launchctl kickstart -k "$DOMAIN/$label" >/dev/null 2>&1 || true
  fi
done

if [[ "$DRY_RUN" != "1" && "$BOOTSTRAP" == "1" ]]; then
  launchctl list | grep -E 'poly_strategy_(realtime|alert|discovery|external|data_rotation)' || true
fi
