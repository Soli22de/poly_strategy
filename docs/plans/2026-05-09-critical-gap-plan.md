# 2026-05-09 Critical Gap Plan

This file is the persistent execution checklist for the Polymarket arbitrage MVP. Keep it updated after every implementation block so the work does not disappear from context.

## Objective

Build a safe, fully automated dry-run research/trading loop that can discover more markets, scan realtime order books, explain why opportunities are absent, emit alerts, build pretrade-checked execution plans, and run persistently on macOS. Live trading remains disabled until separate explicit approval and key-safety work.

## Current Baseline

- Polymarket internal strategies exist: YES/NO bundle, implication, mutual exclusion, equivalence, complement, exhaustive groups, neg-risk baskets, and near-miss diagnostics.
- Realtime Polymarket WebSocket monitor exists and currently watches `data/watchlist-current.json`.
- Alert extraction exists and writes NDJSON with cooldown state.
- Execution planning exists as dry-run only by default.
- External signal normalization exists for manually supplied scanner payloads.
- Persistent LaunchAgent templates now exist under `ops/launchd/`; install them with `scripts/install_launch_agents.sh`.

## Critical Gap Checklist

- [x] Expand opportunity coverage beyond the current small watchlist.
  - [x] Rank high-liquidity/high-relevance Polymarket markets.
  - [x] Include high-liquidity single-market YES/NO bundles.
  - [x] Include all viable neg-risk groups/baskets from Gamma metadata.
  - [x] Include discovered relation-rule markets.
  - [x] Produce a larger prioritized watchlist without blindly subscribing to every market.
- [x] Add automatic incremental market discovery.
  - [x] Pull fresh Gamma markets on a schedule.
  - [x] Run LLM/rule discovery only on new markets.
  - [x] Reuse rule cache for previously processed markets.
  - [x] Rebuild watchlist after discovery.
  - [x] Restart/reload realtime monitor when the watchlist changes.
- [x] Add realtime-specific analysis reports.
  - [x] Opportunity frequency and zero-opportunity streaks.
  - [x] Near-miss distribution.
  - [x] Fee drag diagnostics.
  - [x] Spread/price-distance reasons for no opportunities.
  - [x] Closest market/rule candidates.
  - [x] WebSocket health, stale/reconnect, and message-age metrics.
- [x] Complete alert to execution dry-run linkage.
  - [x] Read latest alert/monitor state.
  - [x] Refresh quote/orderbook before plan creation.
  - [x] Build dry-run execution plan.
  - [x] Run pretrade checks.
  - [x] Keep live execution blocked unless explicitly enabled.
- [x] Add notification outputs.
  - [x] Webhook JSON notification.
  - [x] Telegram-compatible notification.
  - [x] Discord-compatible notification.
  - [x] Local desktop notification command path.
- [x] Add production data maintenance.
  - [x] Date/file rotation helper.
  - [x] Compress old raw/snapshot files.
  - [x] Retain reports and alert logs.
  - [x] Guard against disk exhaustion.
- [x] Convert background jobs to persistent LaunchAgents.
  - [x] Realtime monitor plist.
  - [x] Alert loop plist.
  - [x] Optional discovery refresh plist.
  - [x] Install/reload helper script.
- [x] Build cross-platform/Kalshi framework.
  - [x] Kalshi market collector.
  - [x] Kalshi orderbook parser/collector.
  - [x] Polymarket/Kalshi matching candidates.
  - [x] Cross-platform fee/funding/risk model.
  - [x] Dry-run-only cross-platform execution risk report.
- [x] Integrate external tool signals into the realtime loop.
  - [x] Poll generic external signal URLs/files.
  - [x] Normalize Oddpool/PillarLabAI/Polyprophet-style payloads through the existing signal schema.
  - [x] Convert high-confidence signals into watchlist priority boosts.
- [x] Add live-risk controls while keeping live trading disabled.
  - [x] Daily max loss.
  - [x] Per-trade max loss/notional.
  - [x] Max order count.
  - [x] Kill switch.
  - [x] Partial-fill/reconciliation placeholders.
  - [x] Balance/API-key safety checks.
  - [x] Failure cooldown/pause mechanism.
- [x] Final validation.
  - [x] Unit tests.
  - [x] Smoke tests with current data.
  - [x] Code review checklist.
  - [x] Git commit for each key block.

## Execution Notes

- Use `.venv/bin/python` for commands and tests.
- Default proxy for live HTTP smoke tests can be `127.0.0.1:10808` when needed.
- Do not place API keys, private keys, or secrets in this repository.
- Do not enable live order posting in automation; only dry-run plans are allowed for this phase.
