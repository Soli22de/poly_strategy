# Refined Binary-tier Analysis (2026-05-13T03:15:56.289910+00:00)

**Source**: today's `markets.ndjson` (question text) + 14-day backfill (`groups.ndjson`).
**Threshold**: edge_after_fee > 2.00%

## 1. Sub-tier counts (today's 2-member groups)

- `dvr`: 71 groups
- `yes_no`: 0 groups
- `pseudo`: 21 groups

## 2. Event metrics by sub-tier

| sub_tier | events | distinct groups | median persistence (min) | top peak edge |
|---|---:|---:|---:|---:|
| `dvr` | 7 | 71 | 15 | +0.1979 |
| `yes_no` | 0 | 0 | — | — |
| `pseudo` | 7 | 20 | 570 | +0.0704 |

## 3. Top 15 `dvr` events (real D vs R races)

| group | peak_edge | persistence (min) | min_liq | start | end |
|---|---:|---:|---:|---|---|
| `0x5f4893a285ad...` (Will the Democrats win the Wes vs ...) | +0.1979 | 792 | $86 | 2026-05-12T13:53:18 | 2026-05-13T03:05:04 |
| `0xb17c29a2fb22...` (Will the Democrats win the Ten vs ...) | +0.1042 | 177 | $2,082 | 2026-05-12T13:53:18 | 2026-05-12T16:50:04 |
| `0xa8574c0caacc...` (Will the Democrats win the Sou vs ...) | +0.0369 | 765 | $2,125 | 2026-05-12T14:20:04 | 2026-05-13T03:05:04 |
| `0x50a317c8d911...` (Will the Democrats win the Okl vs ...) | +0.0355 | 15 | $187 | 2026-05-12T15:35:04 | 2026-05-12T15:50:03 |
| `0x50a317c8d911...` (Will the Democrats win the Okl vs ...) | +0.0335 | 15 | $143 | 2026-05-12T16:20:04 | 2026-05-12T16:35:04 |
| `0x50a317c8d911...` (Will the Democrats win the Okl vs ...) | +0.0310 | 0 | $1,205 | 2026-05-12T18:50:03 | 2026-05-12T18:50:03 |
| `0x50a317c8d911...` (Will the Democrats win the Okl vs ...) | +0.0259 | 0 | $192 | 2026-05-12T18:05:03 | 2026-05-12T18:05:03 |

## 4. Notes

- `dvr` (D vs R) is the only sub-tier that is structurally exhaustive in US politics — third parties get < 1% of vote in modern Senate/Governor general elections.
- `yes_no` heuristic is naive (negation-substring + similarity). Likely under-counts.
- `pseudo` events are NOT tradeable as basket arb — the listed 2 members are a sample, not the whole universe.
- Verdict on dvr depends on event count AND median persistence AND a depth check (NOT done yet — same trap as James Bond, where mid edge > bestAsk edge after slippage).

---
*Generated at 2026-05-13T03:15:56.289910+00:00*