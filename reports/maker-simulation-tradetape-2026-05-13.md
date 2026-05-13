# Maker Simulation v3 — Trade Tape + Size-capped (2026-05-13T06:26:16.072251+00:00)

**Method (v3 = v2 + 3 fixes WW caught)**: real Polymarket trade tape.
For each (group, day, markup), check if any SELL Yes trade at price <= target occurred on each leg. **Realized basket units per fill = min(intended_basket, min-over-legs of sum of qualifying-trade sizes that day)**. Maker target strictly clamped below bestAsk and above bestBid; groups with spread < 0.002 skipped.

**Window**: 14 days (2026-04-29 -> 2026-05-13)
**Intended basket size**: $100 of payout per fill (capped by trade size)
**Trades fetched**: 48033 raw -> 1603 qualifying (SELL Yes in window)
**Days with activity**: 15
**Markup levels with no valid maker (spread too narrow)**: 20

## Fixes vs prior version (v2 from earlier today)

1. **Income now capped by realized basket units, not intended size.** Previous formula `fill_rate * avg_edge * intended_basket` assumed every fill captured the full $100. Per WW's review, that overstates by 5-20x when avg trade size is 5-9 units.
2. **Maker target clamped strictly below bestAsk.** Previously `max(target, bestBid+0.001)` could produce target = bestAsk for narrow spreads (crossing/taker, not maker).
3. **Per-leg fill size = sum of qualifying SELL Yes trade sizes at price <= target**, not total all SELL Yes sizes regardless of price.

## v3 results

- Total expected daily income: **$-0.72/day** across 72 groups @ $100 intended basket
- Annualized: **$-263/yr**
- Groups with positive expected income at any markup: **18/72**

## Top 20 by best expected daily income (v3)

| Group | Q | Best markup | Fill rate | Edge/unit | Avg realized units | Exp daily $ |
|---|---|---:|---:|---:|---:|---:|
| `0x5cddfa5bafea...` | Will the Democrats win the Geo vs Will the Re | $0.030 | 20.0% | +3.887% | 9.4 | $+0.073 |
| `0xb61918837517...` | Will the Democrats win the Nor vs Will the Re | $0.010 | 6.7% | +0.725% | 100.0 | $+0.048 |
| `0x2ecd963d91df...` | Will the Democrats win the Iow vs Will the Re | $0.030 | 20.0% | +5.027% | 4.0 | $+0.040 |
| `0x2aa7cf1991dd...` | Will the Democrats win the Kan vs Will the Re | $0.050 | 6.7% | +5.992% | 10.0 | $+0.040 |
| `0x4e43ba407ed4...` | Will the Democrats win the Wis vs Will the Re | $0.030 | 6.7% | +2.476% | 10.9 | $+0.018 |
| `0x6473c875a3d6...` | Will the Democrats win the New vs Will the Re | $0.030 | 13.3% | +2.442% | 5.0 | $+0.016 |
| `0x7146f4aff656...` | Will the Democrats win the Ill vs Will the Re | $0.050 | 6.7% | +4.772% | 5.0 | $+0.016 |
| `0xb17c29a2fb22...` | Will the Democrats win the Ten vs Will the Re | $0.010 | 6.7% | +3.341% | 6.0 | $+0.013 |
| `0x195e8f642b07...` | Will the Democrats win the Tex vs Will the Re | $0.020 | 13.3% | +2.728% | 3.4 | $+0.012 |
| `0xd4118b02b567...` | Will the Democrats win the Pen vs Will the Re | $0.020 | 6.7% | +3.282% | 5.0 | $+0.011 |
| `0x209eca0d8c37...` | Will the Democrats win the Wyo vs Will the Re | $0.030 | 6.7% | +2.391% | 6.2 | $+0.010 |
| `0x7bd878bdc3cd...` | Will the Democrats win the Nev vs Will the Re | $0.050 | 6.7% | +1.012% | 10.0 | $+0.007 |
| `0x2a010ed53626...` | Will the Democrats win the Flo vs Will the Re | $0.020 | 6.7% | +1.498% | 5.0 | $+0.005 |
| `0x12dddaa9289c...` | Will the Democrats win the Ken vs Will the Re | $0.030 | 6.7% | +0.426% | 16.3 | $+0.005 |
| `0x8941a4153cb2...` | Will the Democrats win the Ver vs Will the Re | $0.020 | 6.7% | +0.521% | 5.0 | $+0.002 |
| `0x82cc8472987c...` | Will the Democrats win the Kan vs Will the Re | $0.010 | 6.7% | +0.672% | 3.9 | $+0.002 |
| `0xac17bb3e2188...` | Will the Democrats win the New vs Will the Re | $0.020 | 13.3% | +1.732% | 0.7 | $+0.002 |
| `0x1304dee4404b...` | Will the Democrats win the Ari vs Will the Re | $0.010 | 6.7% | +0.341% | 5.0 | $+0.001 |
| `0xb23e25438839...` | Aaron Taylor-Johnson announced vs James Norto | $0.005 | 0.0% | +0.000% | 0.0 | $+0.000 |
| `0x07311e10dac6...` | Will the Democrats win the Ala vs Will the Re | $0.005 | 0.0% | +0.000% | 0.0 | $+0.000 |

## Markup-level aggregate (v3)

| Markup | Avg fill rate | Avg edge/unit | Avg realized units | Groups positive | Total daily $ |
|---:|---:|---:|---:|---:|---:|
| $0.005 | 5.9% | -1.266% | 19.7 | 7/72 | $-2.09 |
| $0.010 | 5.8% | -0.382% | 19.8 | 13/72 | $-1.04 |
| $0.020 | 5.7% | +0.241% | 20.1 | 15/72 | $-0.88 |
| $0.030 | 5.6% | +0.656% | 19.4 | 16/72 | $-0.78 |
| $0.050 | 5.4% | +0.903% | 20.0 | 15/72 | $-0.75 |

## Notes / honest disclaimers

- Real Polymarket trade tape. SELL Yes trades at price <= target are the only ones that would have hit a resting maker bid.
- Realized basket units = min(intended_basket, min_over_legs of total qualifying-trade size that day). This is the **upper bound** on what we could have filled.
- Still optimistic on (a) queue priority — assumes our bid was first in line at our price level, (b) per-leg fills are independent within a day.
- Maker fee assumed = taker fee_rate from feeSchedule. Polymarket maker fees are sometimes lower or rebated — actual income could be slightly HIGHER from fees alone.
- Realistic adjustment: discount by 0.4-0.6x for queue priority + correlation + gas, additional partial-fill hedging risk.

## Comparison to prior versions

| Version | Method | Annualized | Issue |
|---|---|---:|---|
| v1 (mid-touch) | did mid touch target on day d | $15,546 | Massively over-counted; mid touching != fill |
| v2 (trade tape, size-uncapped) | sum SELL-Yes sizes regardless of target | $918 | Income computed at full $100/fill regardless of trade size |
| **v3 (this run)** | per-target qualifying sizes, capped income | **$-263** | Honest within stated assumptions |

---
*Snapshot: 2026-05-13T06:26:16.072251+00:00*