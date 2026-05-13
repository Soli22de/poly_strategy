# Maker-strategy Basket Simulation (2026-05-13T03:42:38.816895+00:00)

**Method**: for each (group, UTC-day, markup-level), check if every leg's mid-price touched (today's bestAsk - markup) at some point during the day. If ALL legs filled, compute basket cost at maker target prices + fee. Aggregate fill_rate * avg_edge as proxy for expected daily $income.

**Window**: 14 days, 15 distinct UTC days seen in tick data.
**Basket size for $income estimate**: $100 of payout per fill.

## Caveats (read first)

- Mid-touching `target` is a proxy for fill, not a guarantee. Real fill requires someone to hit our resting order at that price.
- Per-leg fill events treated as independent within a day. For correlated markets (D/R move together) this overestimates basket fill rate.
- Today's bestAsk/bestBid used as reference; historical spread may differ.
- Fee = taker rate from feeSchedule. Real maker fee may be 0 or negative (rebate), so this is a CONSERVATIVE estimate.

## Top 20 groups by best expected daily income

| Group | Q (short) | Best markup | Fill rate | Avg edge | Exp daily $ |
|---|---|---:|---:|---:|---:|
| `0x2aa7cf1991dd...` | Will the Democrats win the Kan vs Will the Republicans  | $0.050 | 80.0% | +6.091% | $+4.873 |
| `0xa7f79f468a16...` | Will the Democrats win the Sou vs Will the Republicans  | $0.030 | 80.0% | +4.733% | $+3.787 |
| `0x6473c875a3d6...` | Will the Democrats win the New vs Will the Republicans  | $0.050 | 60.0% | +4.307% | $+2.584 |
| `0x5f4893a285ad...` | Will the Democrats win the Wes vs Will the Republicans  | $0.010 | 46.7% | +4.941% | $+2.306 |
| `0xbd54b57c63ad...` | Will the Democrats win the Ida vs Will the Republicans  | $0.010 | 100.0% | +2.198% | $+2.198 |
| `0xa8574c0caacc...` | Will the Democrats win the Sou vs Will the Republicans  | $0.005 | 46.7% | +4.484% | $+2.093 |
| `0x7146f4aff656...` | Will the Democrats win the Ill vs Will the Republicans  | $0.030 | 53.3% | +3.663% | $+1.953 |
| `0x2ecd963d91df...` | Will the Democrats win the Iow vs Will the Republicans  | $0.020 | 60.0% | +3.223% | $+1.934 |
| `0x7bd878bdc3cd...` | Will the Democrats win the Nev vs Will the Republicans  | $0.050 | 60.0% | +2.829% | $+1.697 |
| `0xffde13841676...` | Will the Democrats win the Min vs Will the Republicans  | $0.020 | 73.3% | +2.247% | $+1.647 |
| `0xb17c29a2fb22...` | Will the Democrats win the Ten vs Will the Republicans  | $0.020 | 26.7% | +5.345% | $+1.425 |
| `0xfb7720a6bbf3...` | Will the Democrats win the Rho vs Will the Republicans  | $0.030 | 33.3% | +4.111% | $+1.370 |
| `0x5cddfa5bafea...` | Will the Democrats win the Geo vs Will the Republicans  | $0.030 | 33.3% | +3.887% | $+1.296 |
| `0x8397b62d3e02...` | Will the Democrats win the Neb vs Will the Republicans  | $0.020 | 66.7% | +1.867% | $+1.245 |
| `0x12dddaa9289c...` | Will the Democrats win the Ken vs Will the Republicans  | $0.050 | 26.7% | +4.527% | $+1.207 |
| `0x266416597e36...` | Will the Republican Party win  vs Will the Democratic P | $0.050 | 93.3% | +1.218% | $+1.136 |
| `0xe0ff15139f33...` | Will the Democrats win the Min vs Will the Republicans  | $0.010 | 60.0% | +1.764% | $+1.058 |
| `0x64111969ce49...` | Will the Democrats win the New vs Will the Republicans  | $0.010 | 93.3% | +1.059% | $+0.988 |
| `0x9bb9ed087667...` | Will the Democrats win the Ark vs Will the Republicans  | $0.005 | 73.3% | +1.346% | $+0.987 |
| `0x4e43ba407ed4...` | Will the Democrats win the Wis vs Will the Republicans  | $0.020 | 60.0% | +1.554% | $+0.932 |

## Aggregate (all groups combined)

- Total expected daily income (sum across 72 groups, $100 basket each): **$+42.59/day**
- Annualized: **$+15,546/yr**
- Groups with positive expected income at any markup: **49/72**

## Markup-level summary (averaged across all groups)

| Markup | Avg fill rate | Avg edge given fill | Groups with positive exp daily | Total exp daily $ |
|---:|---:|---:|---:|---:|
| $0.005 | 69.4% | -0.776% | 26/72 | $-47.62 |
| $0.010 | 40.4% | -0.204% | 25/72 | $-12.66 |
| $0.020 | 28.7% | +0.682% | 33/72 | $+7.45 |
| $0.030 | 25.5% | +1.107% | 32/72 | $+17.25 |
| $0.050 | 23.5% | +1.661% | 34/72 | $+28.53 |

## Comparison to previous taker depth check

Taker: SC Gov bestAsk basket, single $50 fill → +$0.52 profit (one-time).
Taker: James Bond bestAsk basket, single $80 fill → +$3.78 profit (one-time).

Maker (this sim): $+42.59/day across 72 groups at $100 basket each = up to $+15,546/yr theoretical.

Important: this is the OPTIMISTIC bound. Real fill rates are likely 2-5x lower than mid-touch rates because mid touching doesn't equal trade at that price.

---
*Snapshot: 2026-05-13T03:42:38.816895+00:00*