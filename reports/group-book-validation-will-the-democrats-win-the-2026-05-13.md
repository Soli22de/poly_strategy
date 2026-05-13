# Group Book Validation: will-the-democrats-win-the (2026-05-13T06:27:27.152124+00:00)

Real-orderbook depth check of basket arb candidate.
Group: `0xa8574c0caacc...`  (members=2)

## Per-member top-of-book

| # | Question | bestAsk | depth @ bestAsk | bestBid | gamma_ask | fee | vol24hr | liq |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Will the Democrats win the South Carolina governor race | 0.059 | 77 | 0.022 | 0.0590 | 0.040 | $0 | $4,664 |
| 2 | Will the Republicans win the South Carolina governor ra | 0.91 | 4 | 0.89 | 0.9100 | 0.040 | $1 | $5,585 |

## Marginal (1-unit) edge

- bestAsk basket sum: **0.9690**
- marginal fee: 0.00550
- marginal edge_after_fee: **+0.0255**

## Fill simulation (fix: cost & edge computed at ACTUAL fillable size, not intended)

| Intended size | Actual fillable | Avg cost/unit | Total fee | Edge $ | Edge % |
|---:|---:|---:|---:|---:|---:|
| 50 | 50.0 | 0.9782 | $0.26 | $+0.83 | +1.66% |
| 200 | 200.0 | 0.9845 | $1.07 | $+2.02 | +1.01% |
| 500 | 500.0 | 1.0178 | $3.24 | $-12.12 | -2.42% |
| 1000 | 1000.0 | 1.0430 | $6.53 | $-49.48 | -4.95% |
| 2000 | 1303.9 ⚠️ | 1.0566 | $8.26 | $-82.06 | -6.29% |
| 5000 | 1303.9 ⚠️ | 1.0566 | $8.26 | $-82.06 | -6.29% |

---
*Snapshot: 2026-05-13T06:27:27.152124+00:00*