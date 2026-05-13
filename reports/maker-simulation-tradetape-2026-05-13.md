# Maker Simulation v2 — Trade Tape (2026-05-13T03:50:03.951692+00:00)

> **Post-review correction (2026-05-13)**: this report was generated before the simulator capped PnL by the thinnest at-or-below-target leg trade size and before maker quotes were forced to stay strictly below bestAsk. Treat the dollar figures below as a stale upper bound. Re-run `scripts/simulate_maker_basket_v2.py` with the corrected code before making any trade/no-trade decision.

**Method**: real Polymarket trade tape. For each (group, day, markup), check if any SELL Yes trade at price <= target occurred on each leg that day. If ALL legs had a qualifying trade, basket fills.

**Window**: 14 days (2026-04-29 -> 2026-05-13)
**Basket size**: $100
**Trades fetched**: 48030 raw -> 1602 qualifying (SELL Yes in window)
**Days with activity**: 15

## v1 (mid-touch) vs v2 (trade tape) comparison

v1 mid-touch results from earlier today (see `maker-simulation-2026-05-13.md`):
- Total daily $: $+42.59 across 72 groups
- Annualized: $+15,546/yr
- Caveat: mid touching != trade happening at that price

## v2 results (this run)

- Total expected daily income: **$+2.51/day** across 72 groups @ $100 basket
- Annualized: **$+918/yr**
- Groups with positive expected income at any markup: **17/72**

## Top 20 by best expected daily income (v2)

| Group | Q | Best markup | Fill rate | Avg edge | Avg sell size | Exp daily $ |
|---|---|---:|---:|---:|---:|---:|
| `0x2ecd963d91df...` | Will the Democrats win the Iow vs Will the Re | $0.030 | 20.0% | +5.027% | 77 | $+1.005 |
| `0x5cddfa5bafea...` | Will the Democrats win the Geo vs Will the Re | $0.030 | 20.0% | +3.887% | 9 | $+0.777 |
| `0x7146f4aff656...` | Will the Democrats win the Ill vs Will the Re | $0.050 | 6.7% | +5.738% | 5 | $+0.383 |
| `0x195e8f642b07...` | Will the Democrats win the Tex vs Will the Re | $0.020 | 13.3% | +2.728% | 3 | $+0.364 |
| `0xb17c29a2fb22...` | Will the Democrats win the Ten vs Will the Re | $0.020 | 6.7% | +5.138% | 6 | $+0.343 |
| `0x2aa7cf1991dd...` | Will the Democrats win the Kan vs Will the Re | $0.050 | 6.7% | +5.001% | 10 | $+0.333 |
| `0x6473c875a3d6...` | Will the Democrats win the New vs Will the Re | $0.030 | 13.3% | +2.442% | 5 | $+0.326 |
| `0xac17bb3e2188...` | Will the Democrats win the New vs Will the Re | $0.020 | 13.3% | +1.732% | 1 | $+0.231 |
| `0xd4118b02b567...` | Will the Democrats win the Pen vs Will the Re | $0.020 | 6.7% | +3.282% | 5 | $+0.219 |
| `0x4e43ba407ed4...` | Will the Democrats win the Wis vs Will the Re | $0.030 | 6.7% | +2.476% | 11 | $+0.165 |
| `0x209eca0d8c37...` | Will the Democrats win the Wyo vs Will the Re | $0.030 | 6.7% | +2.183% | 6 | $+0.146 |
| `0x7bd878bdc3cd...` | Will the Democrats win the Nev vs Will the Re | $0.050 | 6.7% | +1.823% | 10 | $+0.122 |
| `0x8941a4153cb2...` | Will the Democrats win the Ver vs Will the Re | $0.010 | 6.7% | +1.546% | 5 | $+0.103 |
| `0x2a010ed53626...` | Will the Democrats win the Flo vs Will the Re | $0.020 | 6.7% | +1.498% | 5 | $+0.100 |
| `0xb61918837517...` | Will the Democrats win the Nor vs Will the Re | $0.010 | 6.7% | +0.725% | 343 | $+0.048 |
| `0x82cc8472987c...` | Will the Democrats win the Kan vs Will the Re | $0.010 | 6.7% | +0.672% | 12 | $+0.045 |
| `0x1304dee4404b...` | Will the Democrats win the Ari vs Will the Re | $0.010 | 6.7% | +0.341% | 5 | $+0.023 |
| `0xb23e25438839...` | Aaron Taylor-Johnson announced vs James Norto | $0.005 | 0.0% | +0.000% | 0 | $+0.000 |
| `0x07311e10dac6...` | Will the Democrats win the Ala vs Will the Re | $0.005 | 0.0% | +0.000% | 0 | $+0.000 |
| `0x25025e1a8d9b...` | Will the Democrats win the Ark vs Will the Re | $0.005 | 0.0% | +0.000% | 0 | $+0.000 |

## Markup-level aggregate (v2)

| Markup | Avg fill rate | Avg edge given fill | Groups positive | Total daily $ |
|---:|---:|---:|---:|---:|
| $0.005 | 5.5% | -1.067% | 8/72 | $-5.02 |
| $0.010 | 5.5% | -0.180% | 13/72 | $-1.62 |
| $0.020 | 5.4% | +0.638% | 16/72 | $+0.98 |
| $0.030 | 5.1% | +0.932% | 15/72 | $+1.79 |
| $0.050 | 4.9% | +1.102% | 15/72 | $+1.85 |

## Notes

- This uses the REAL trade tape — every SELL Yes trade in the past 14 days at price <= target is counted as a potential fill.
- Still optimistic: assumes (a) our resting bid was first in queue, (b) our size was always available, (c) per-leg fills are independent within a day.
- avg_min_leg_sell_size = avg of (min sell-size across legs on filled days). If this is < intended basket size, we couldn't have filled in full.
- Maker fee assumed equal to taker fee_rate from feeSchedule. Polymarket maker fees may be lower or rebated — actual income could be HIGHER.
- v2 vs v1 mismatch: v2 < v1 means mid-touch over-counts (less real trade activity at target); v2 > v1 means mid-touch under-counts (trades happened that mid-snapshot didn't capture).

---
*Snapshot: 2026-05-13T03:50:03.951692+00:00*
