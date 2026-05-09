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
- Background jobs currently use `launchctl submit`; persistent LaunchAgents are not yet installed.

## Critical Gap Checklist

- [ ] Expand opportunity coverage beyond the current small watchlist.
  - [ ] Rank high-liquidity/high-relevance Polymarket markets.
  - [ ] Include high-liquidity single-market YES/NO bundles.
  - [ ] Include all viable neg-risk groups/baskets from Gamma metadata.
  - [ ] Include discovered relation-rule markets.
  - [ ] Produce a larger prioritized watchlist without blindly subscribing to every market.
- [ ] Add automatic incremental market discovery.
  - [ ] Pull fresh Gamma markets on a schedule.
  - [ ] Run LLM/rule discovery only on new markets.
  - [ ] Reuse rule cache for previously processed markets.
  - [ ] Rebuild watchlist after discovery.
  - [ ] Restart/reload realtime monitor when the watchlist changes.
- [ ] Add realtime-specific analysis reports.
  - [ ] Opportunity frequency and zero-opportunity streaks.
  - [ ] Near-miss distribution.
  - [ ] Fee drag diagnostics.
  - [ ] Spread/price-distance reasons for no opportunities.
  - [ ] Closest market/rule candidates.
  - [ ] WebSocket health, stale/reconnect, and message-age metrics.
- [ ] Complete alert to execution dry-run linkage.
  - [ ] Read latest alert/monitor state.
  - [ ] Refresh quote/orderbook before plan creation.
  - [ ] Build dry-run execution plan.
  - [ ] Run pretrade checks.
  - [ ] Keep live execution blocked unless explicitly enabled.
- [ ] Add notification outputs.
  - [ ] Webhook JSON notification.
  - [ ] Telegram-compatible notification.
  - [ ] Discord-compatible notification.
  - [ ] Local desktop notification command path.
- [ ] Add production data maintenance.
  - [ ] Date/file rotation helper.
  - [ ] Compress old raw/snapshot files.
  - [ ] Retain reports and alert logs.
  - [ ] Guard against disk exhaustion.
- [ ] Convert background jobs to persistent LaunchAgents.
  - [ ] Realtime monitor plist.
  - [ ] Alert loop plist.
  - [ ] Optional discovery refresh plist.
  - [ ] Install/reload helper script.
- [ ] Build cross-platform/Kalshi framework.
  - [ ] Kalshi market collector.
  - [ ] Kalshi orderbook parser/collector.
  - [ ] Polymarket/Kalshi matching candidates.
  - [ ] Cross-platform fee/funding/risk model.
  - [ ] Dry-run-only cross-platform execution risk report.
- [ ] Integrate external tool signals into the realtime loop.
  - [ ] Poll generic external signal URLs/files.
  - [ ] Normalize Oddpool/PillarLabAI/Polyprophet-style payloads through the existing signal schema.
  - [ ] Convert high-confidence signals into watchlist priority boosts.
- [ ] Add live-risk controls while keeping live trading disabled.
  - [ ] Daily max loss.
  - [ ] Per-trade max loss/notional.
  - [ ] Max order count.
  - [ ] Kill switch.
  - [ ] Partial-fill/reconciliation placeholders.
  - [ ] Balance/API-key safety checks.
  - [ ] Failure cooldown/pause mechanism.
- [ ] Final validation.
  - [ ] Unit tests.
  - [ ] Smoke tests with current data.
  - [ ] Code review checklist.
  - [ ] Git commit for each key block.

## Execution Notes

- Use `.venv/bin/python` for commands and tests.
- Default proxy for live HTTP smoke tests can be `127.0.0.1:10808` when needed.
- Do not place API keys, private keys, or secrets in this repository.
- Do not enable live order posting in automation; only dry-run plans are allowed for this phase.
