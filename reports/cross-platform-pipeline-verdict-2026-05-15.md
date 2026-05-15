# Cross-platform Polymarket↔Kalshi pipeline verdict (2026-05-15)

**Verdict**: no real cross-platform arbs in tested cohort. 0 candidates pass
WW's deterministic option-match check across 1,000 Jaccard-matched pairs.
For the 10 pairs where the question is unambiguously the same event
(NHL Stanley Cup individual team championships), every cross-platform edge
is negative (−2.77% to −97%).

Three-hour effort with two phases:
1. Feasibility audit (`cross-platform-feasibility-2026-05-15.md`) —
   discovered Kalshi API quirks (parlay pollution, bids-not-asks ordering).
2. Pipeline bootstrap + run (this report) — generated all 6 stages.

## What I ran

Bootstrapped WW's `scripts/run_cross_platform_scan_once.sh` pipeline. Key
detour: the default `poly-strategy collect-kalshi` is dominated by
KXMVE*/KXMVS* multivariate parlay markets (99.86% of first 10,000 pages).
Wrote `scripts/collect_kalshi_targeted.py` to pull by series instead. That
pull yielded 584 real markets across 9 active series (KXFED, KXCPI, KXBTC,
KXETH, KXGDP, KXNHL, KXEUROVISION, KXNEWPOPE).

Then:
- `match-cross-platform` (Jaccard, --min-score 0.3, --top 1000) → 1,558
  raw matches in pool, top 1,000 kept
- `scan-cross-platform-once --include-unverified` → 1,202 opportunities
  across 1,000 pairs
- `filter-cross-platform-opportunities` (the deterministic
  `option_match` check, no LLM) → **0 pass with option_match=True + edge>=0**

## Where the "positive edges" come from

The scan found 165 of 892 Eurovision rows with positive edge and 63 of
264 "Other" with positive edge. All of them fail option_match. The
patterns:

| Apparent edge | Real cause |
|---:|---|
| +0.635 | Polymarket "Will inflation reach more than **4%** in 2026?" vs Kalshi `KXCPI-26MAY-T0.9` "Will CPI rise more than **0.9%** in May" — different numeric thresholds + annual vs monthly window |
| +0.498 | Same pattern with negative threshold (`T-0.1`) |
| +0.384 | Polymarket "Will **Austria** win Eurovision 2026?" vs Kalshi `KXEUROVISION-26-FIN` (**Finland**) — Jaccard matched on "Eurovision Winner 2026" but the ticker suffix is the specific country (and `-AUS` is **Australia**, not Austria — IOC code, verified via Kalshi `rules_primary` text "If Australia wins the Eurovision Song Contest...") |

The deterministic option-match check correctly catches all these (option
mismatch on numeric tokens or required tokens).

## TRUE same-event matches: all negative

10 NHL Stanley Cup individual-team pairs where Polymarket "Will [Team]
win the 2026 NHL Stanley Cup?" matches Kalshi `KXNHL-26-[Team]`:

| Team | Net edge per share | Cost per share |
|---|---:|---:|
| Buffalo | -2.77% | $1.0277 |
| Colorado | -19.22% | $1.1922 |
| Montreal | -21.61% | $1.2161 |
| Carolina | -24.90% | $1.2490 |
| Buffalo (alt fill) | -29.49% | $1.2949 |
| Vegas | -49.55% | $1.4955 |
| Carolina (alt fill) | -91.87% | $1.9187 |
| Colorado (alt fill) | -94.89% | $1.9489 |
| Montreal (alt fill) | -95.66% | $1.9566 |
| Vegas (alt fill) | -97.03% | $1.9703 |

Best Buffalo at -2.77%. This is the no-arb world: Polymarket YES + Kalshi
NO costs more than $1 by exactly the bid-ask spread + fees on both sides.
The −90% entries are book-walking artifacts (we walked deep enough on
one side that the worst price was $0.99).

## Why the LLM verification step is unnecessary here

The deterministic `_option_match` check (in
`poly_strategy/cross_platform.py:_option_match`) compares:
- exact normalized title match
- numeric tokens (e.g., 4% must equal 0.9%, fails fast)
- required tokens (e.g., country names must appear on both sides
  in compatible way)

For our cohort, the deterministic check is sufficient. None of the
positive-edge candidates pass option_match. The LLM second pass would
also reject them (the question structures genuinely differ), so spending
LLM budget on confirmation is unnecessary.

## What this generalizes to

The bottleneck isn't access to cross-platform arb opportunities. It's that
matched events at different venues are nearly always priced consistently
*because anyone seeing a real gap would close it*. The same dynamic that
killed Polymarket-internal taker arb (sub-minute half-life on the
Anatomy-of-Polymarket paper) applies cross-venue: well-known events on
two major venues will not have persistent gaps for retail.

Where this thesis might still live, but we did not test:
- **Sub-1-minute timing arbs** — but those need market-making infra we
  don't have, and Kalshi is US-only for execution anyway.
- **Resolution-criteria arbs** — events that resolve differently on the
  two venues (UMA dispute, Kalshi review). Outside scope.
- **Long-tail venues** beyond Kalshi (Predicit, Manifold) — different
  question.

## What's in the repo from this effort

- `scripts/collect_kalshi_targeted.py` — bypasses the parlay-saturated
  default pull by iterating known-active series.
- `scripts/probe_cross_platform.py` — manual-pairs probe from the
  feasibility audit phase (unused after Path A took over).
- `reports/cross-platform-feasibility-2026-05-15.md` — Kalshi API quirks
  audit.
- `reports/cross-platform-pipeline-verdict-2026-05-15.md` — this report.

All NDJSON intermediates in `data/` are gitignored.

---
*Snapshot: 2026-05-15T08:30:00+00:00*
