# Pipeline

The current system runs in this order:

1. Discover markets from Polymarket, Kalshi, and external signal sources.
2. Normalize and cache deterministic or LLM-discovered rules.
3. Build a prioritized watchlist from the validated rules.
4. Collect live books and snapshots for only the watched markets.
5. Scan the realtime feed for stable opportunity runs.
6. Turn stable opportunities into paper trades and execution plans.
7. Apply pretrade checks and risk limits before any live action.
8. Emit alerts, notifications, and status summaries.

## Why the monitor can still show zero opportunities

Zero actionable opportunities does not mean the system is broken. The usual causes are:

- Coverage is too narrow relative to the market universe.
- Semantic verification rejects most candidate pairs.
- Fees and spread remove the apparent edge.
- Liquidity is too thin for the minimum quantity filters.
- A near-miss is present, but the book is stale or unstable.
- Execution guardrails block anything that is not pretrade-safe.

## Practical reading of the outputs

- `0 verified candidates`: the scanners found no validated relation or cross-venue pair.
- `near-miss only`: the market is close, but the edge is not robust enough.
- `paper trade rejected`: the edge exists in theory, but not after fees, size, or stability filters.
- `execution plan empty`: the system intentionally stayed in dry-run mode.

## Opportunity Chain Analysis

`paper-analyze` and `monitor-analyze` include an `opportunity_chain` object when snapshots are provided. It treats the opportunity flow as a funnel:

1. `feed`: latest snapshots are available.
2. `candidate_generation`: strategies can generate evaluable candidates.
3. `actionability_filter`: candidates are not blocked by wording, verification, or diagnostic-only status.
4. `edge_filter`: actionable candidates clear the configured net-edge threshold.
5. `stability_filter`: realtime opportunities survive the stability window.
6. `paper_filter`: stable opportunities survive ROI, size, bankroll, and liquidity filters.

The report also includes `strategy_chain_breakdown`, which applies the same logic per strategy kind. Use `dominant_blocker` and `next_action` to decide which link to optimize first.

`optimization_targets` ranks the highest-leverage improvements currently visible from the data:

- `maker_fee_avoidance`: taker fees erase the edge, but maker-style execution may restore it.
- `price_improvement`: the candidate is close and needs a quantified price improvement.
- `rule_verification`: a diagnostic basket has high apparent edge but must be verified before promotion.
- `paper_filter_debugging`: stable opportunities exist but fail paper filters; inspect rejection reasons.
- `feed_coverage`: the watchlist has many tokens without current snapshots.

## Focused Maker Fee-Avoidance Loop

When the top blocker is `maker_fee_avoidance`, the next loop is deliberately narrow:

1. Extract the market IDs from `optimization_targets`.
2. Refresh only those books, optionally expanding the full `negRiskMarketID` group.
3. Run `maker-hybrid-scan` on the focused snapshot file.
4. Validate passive fill assumptions with `maker-hybrid-tape-sim`.
5. Read the no-fill diagnostics before making quotes more aggressive.

Useful one-shot commands:

```bash
python3 -m poly_strategy.cli optimization-target-markets \
  data/realtime-monitor-24h-v1-analysis.json \
  --lever maker_fee_avoidance \
  --top-targets 1 \
  --max-markets 120 \
  --out data/optimization-target-market-ids.txt

MAX_TARGET_MARKETS=120 TOP=50 scripts/run_maker_focus_from_analysis_once.sh
```

The tape report is diagnostic-only. It now includes:

- `rejection_by_reason`: whether candidates fail because maker legs do not fill or because the hedge is no longer profitable.
- `maker_fill_progress_distribution`: how many maker legs filled before rejection.
- `top_unfilled_maker_legs`: repeated unfilled markets, quote levels, spread, distance to ask, and expected edge.

This is the guardrail that prevents treating theoretical maker savings as a tradeable opportunity.
