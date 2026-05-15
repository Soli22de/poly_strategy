# Builder-fee + makerBaseFee investigation (2026-05-15)

WW's review on PR #10 added a caveat to all v4 reports:
> Builder fees are not modeled. The maker-fee-zero assumption is for
> direct Polymarket platform fees; orders routed through a builder with
> `builder_maker_fee_bps` could pay a separate builder fee.

This investigation checked whether that caveat could flip the v4 verdict.

## Three checks

### 1. Does `builder_maker_fee_bps` exist in Gamma market data today?

Queried the 8 D/R markets we used in v4 (562793/4, 562802/3, 565064/5,
629337/8). Each market returned 88 distinct top-level fields. None contained
`builder`, `Builder`, or `routing` in the name. The full fee-related field
set was:

```
makerBaseFee: 1000
takerBaseFee: 1000
feesEnabled: True
feeType: politics_fees
feeSchedule: {exponent: 1, rate: 0.04, takerOnly: True, rebateRate: 0.25}
```

**No builder fee field exists on these markets.** WW's caveat references
a field that doesn't currently exist in the Gamma payload.

### 2. What does `makerBaseFee: 1000` mean?

Per docs.polymarket.com/trading/fees, fetched 2026-05-15:
- "**Makers are never charged fees.**"
- "Only takers pay fees."
- Maker rate is 0% across all categories.

The docs do not mention `makerBaseFee` at all. The on-chain query method
documented is `getClobMarketInfo(conditionID)`, which returns `fd`
(fee data) containing:
- `r` (feeRate) ← matches `feeSchedule.rate`
- `e` (exponent) ← matches `feeSchedule.exponent`
- `to` (takerOnly) ← matches `feeSchedule.takerOnly`

The Gamma `makerBaseFee: 1000` is not referenced in the active fee
contract. Most likely a legacy field from a prior fee model; the live
fee schedule is governed by `feeSchedule.rate` + `feeSchedule.takerOnly`.

Cross-check: `poly_strategy/maker.py:1625` sets `"fee_rate_assumption": 0.0`
for maker legs in production. Production code, docs, and the live
`takerOnly: True` flag all agree: maker fee = 0.

### 3. Could there still be hidden fees we miss?

Possible unmodeled costs:
- **Polygon gas** per order (~$0.001-0.01 per tx). Small but real;
  on 5%-edge basket arbs this is ~10-20% of edge.
- **USDC bridge/withdrawal costs** if we ever exit funds.
- **Builder fees on FUTURE markets** if Polymarket adds them — WW's
  caveat is good future-proofing. Not currently relevant.

## Conclusion

WW's caveat is defensive future-proofing, not a fix that flips the v4
verdict. The maker_fee=0 assumption is correct for current Polymarket
markets, per docs + on-chain fee structure + production code agreement.

The v4 final verdict from PR #10 stands:
- Long-tail D/R (71 groups): -$183 naive mean OOS, 0/64 persistent winners
- High-vol multi-member (50 groups): structurally infeasible (96% skip)
- High-vol binary (6 groups): -$22 naive mean OOS, 0/3 persistent
- Cross-platform Polymarket-Kalshi: 0 candidates pass deterministic
  option_match check; 10/10 NHL same-event pairs negative

Maker basket arb thesis is dead across all 4 tested cohorts.

---
*Snapshot: 2026-05-15T08:50:00+00:00*
