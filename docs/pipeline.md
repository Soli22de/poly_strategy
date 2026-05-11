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

