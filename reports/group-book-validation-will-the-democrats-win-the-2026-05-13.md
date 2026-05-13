# Group Book Validation: will-the-democrats-win-the (2026-05-13T03:20:27.443159+00:00)

Real-orderbook depth check of basket arb candidate.
Group: `0xa8574c0caacc...`  (members=2)

## Per-member top-of-book

| # | Question | bestAsk | depth @ bestAsk | bestBid | gamma_ask | fee | vol24hr | liq |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Will the Democrats win the South Carolina governor race | 0.059 | 77 | 0.031 | 0.0590 | 0.040 | $0 | $7,244 |
| 2 | Will the Republicans win the South Carolina governor ra | 0.91 | 4 | 0.9 | 0.9100 | 0.040 | $1 | $3,402 |

## Marginal (1-unit) edge

- bestAsk basket sum: **0.9690**
- marginal fee: 0.00550
- marginal edge_after_fee: **+0.0255**

## Fill simulation

| Basket size (units) | Avg basket cost | Total fee | Edge $ | Edge % | Max fillable |
|---:|---:|---:|---:|---:|---:|
| 50 | 0.9846 | $0.25 | $+0.52 | +1.04% | 50 |
| 200 | 0.9934 | $1.01 | $+0.31 | +0.15% | 200 |
| 500 | 1.0371 | $2.88 | $-21.44 | -4.29% | 500 |
| 1000 | 1.0644 | $5.75 | $-70.15 | -7.01% | 870 |
| 2000 | 1.0987 | $13.53 | $-211.00 | -10.55% | 870 |
| 5000 | 1.3646 | $57.38 | $-1,880.37 | -37.61% | 870 |

---
*Snapshot: 2026-05-13T03:20:27.443159+00:00*