# James Bond CLOB Book Validation (2026-05-12T14:56:28.043386+00:00)

Real-orderbook check of the long-tail explicit_other arb candidate.
This is the truth test of the +8.93% mid-edge the backfill found.

Group: `0xb23e25438839...`  (size=15)

## Per-member top-of-book

| # | Question | bestAsk | depth @ bestAsk | bestBid | gamma_ask | fee_rate |
|---|---|---:|---:|---:|---:|---:|
| 1 | Aaron Taylor-Johnson announced as next James Bond? | 0.016 | 46 | 0.005 | 0.0160 | 0.050 |
| 2 | James Norton announced as next James Bond? | 0.004 | 152 | 0.002 | 0.0040 | 0.050 |
| 3 | Paul Mescal announced as next James Bond? | 0.002 | 1604 | 0.001 | 0.0020 | 0.050 |
| 4 | Jacob Elordi announced as next James Bond? | 0.037 | 21 | 0.035 | 0.0370 | 0.050 |
| 5 | Harris Dickinson announced as next James Bond? | 0.009 | 120 | 0.002 | 0.0090 | 0.050 |
| 6 | Tom Hardy announced as next James Bond? | 0.009 | 115 | 0.001 | 0.0090 | 0.050 |
| 7 | Pierce Brosnan announced as next James Bond? | 0.002 | 2198 | 0.001 | 0.0020 | 0.050 |
| 8 | Tom Holland announced as next James Bond? | 0.012 | 337 | 0.007 | 0.0120 | 0.050 |
| 9 | Henry Cavill announced as next James Bond? | 0.002 | 1731 | 0.001 | 0.0020 | 0.050 |
| 10 | Callum Turner announced as next James Bond? | 0.062 | 40 | 0.032 | 0.0620 | 0.050 |
| 11 | Jack Lowdon announced as next James Bond? | 0.002 | 1689 | 0.001 | 0.0020 | 0.050 |
| 12 | Theo James announced as next James Bond? | 0.002 | 48 | 0.001 | 0.0020 | 0.050 |
| 13 | James Collier announced as next James Bond? | 0.002 | 2361 | 0.001 | 0.0020 | 0.050 |
| 14 |  Josh O'Connor announced as next James Bond? | 0.002 | 640 | 0.001 | 0.0020 | 0.050 |
| 15 | No one announced as next James Bond? | 0.73 | 30 | 0.7 | 0.7300 | 0.050 |

## Marginal (1-unit) edge

- bestAsk basket sum:    **0.8930**
- marginal fee:          0.01771
- marginal edge_after_fee: **+0.0893**

(For comparison: Gamma snapshot mid-based edge was around +0.0893)

## Fill simulation

Buy `size` units of EACH member (so basket payout = size when one wins). Avg basket cost walks up each ask ladder. Edge after fee is the realized dollar profit.

| Basket size (units = $payout) | Avg basket cost | Total fee | Edge $ | Edge % | Max fillable units |
|---:|---:|---:|---:|---:|---:|
| 10 | 0.8930 | $0.18 | $+0.89 | +8.93% | 10 |
| 30 | 0.8948 | $0.53 | $+2.62 | +8.74% | 30 |
| 50 | 0.9096 | $0.91 | $+3.61 | +7.22% | 50 |
| 80 | 0.9337 | $1.53 | $+3.78 | +4.72% | 80 |
| 100 | 0.9505 | $1.97 | $+2.98 | +2.98% | 100 |
| 150 | 1.0391 | $3.52 | $-9.38 | -6.25% | 150 |

## How to read this

- `Max fillable units` = the size at which the thinnest member's ask ladder runs out. If you order more than this, the basket can't be assembled at any price (book is empty above).
- `Edge %` is the actual return on the bought basket if exactly one member wins (which is the explicit_other assumption).
- A positive edge here = bestAsk-tradeable arb. A negative edge here = the backfill mid-edge was an artifact of bid-ask spread.
- Real-world frictions NOT modeled: gas, withdrawal cost, time-to-resolution opportunity cost, neg-risk adapter contract behavior.

---
*Snapshot: 2026-05-12T14:56:28.043386+00:00*