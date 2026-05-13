# Arb-persistence Analysis (2026-05-12T14:25:31.893181+00:00)

**Filter**: tier=`explicit_other`, edge_after_fee > 5.00%, max gap 35min
**Snapshot range**: 2026-04-28T21:15:00+00:00  ->  2026-05-12T14:20:04.551587+00:00
**Window**: 329.1 hours across 963 unique snapshots

## Pass / kill metrics

- **Distinct edge events**: 4  (with longtail member: 4)
- **Median persistence (min)**: 2235.0  (P25: 466.4, P75: 3360.0)

**Verdict**: BORDERLINE (extend window or pivot to binary tier)

## Top events by peak edge

| neg_risk_market_id | size | peak_edge | persistence (min) | min_liq seen | longtail | start_ts | end_ts |
|---|---:|---:|---:|---:|:---:|---|---|
| `0xb23e25438839...` | 15 | +0.1823 | 3585.0 | $824 | Y | 2026-05-08T06:15:00+00:00 | 2026-05-10T18:00:00+00:00 |
| `0xb23e25438839...` | 15 | +0.1236 | 1785.0 | $824 | Y | 2026-04-30T18:15:00+00:00 | 2026-05-02T00:00:00+00:00 |
| `0xb23e25438839...` | 15 | +0.0914 | 2685.0 | $824 | Y | 2026-05-05T18:15:00+00:00 | 2026-05-07T15:00:00+00:00 |
| `0xb23e25438839...` | 15 | +0.0893 | 26.8 | $496 | Y | 2026-05-12T13:53:18.607759+00:00 | 2026-05-12T14:20:04.551587+00:00 |

## Notes

- An *event* = contiguous run of snapshots where this group's `edge_after_fee` stayed above the threshold. Gap > max_gap_minutes splits a run.
- `persistence_minutes` = end_ts - start_ts. A one-snapshot flash shows 0 min.
- `min_liquidity_seen` = the minimum group-wide min_liquidity across the event (proxy for thinnest leg).
- For thesis decision use `tier=explicit_other --min-edge 0.05`; rerun with `--tier binary --min-edge 0.02` for the pivot view.

---
*Analyzed at 2026-05-12T14:25:31.893181+00:00*