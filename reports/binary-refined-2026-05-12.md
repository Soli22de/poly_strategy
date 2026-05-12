# Refined Binary-tier Analysis (2026-05-12T18:03:42.612726+00:00)

**Source**: today's `markets.ndjson` (question text) + 14-day backfill (`groups.ndjson`).
**Threshold**: edge_after_fee > 2.00%

## 1. Sub-tier counts (today's 2-member groups)

- `dvr`: 71 groups
- `yes_no`: 0 groups
- `pseudo`: 21 groups

## 2. Event metrics by sub-tier

| sub_tier | events | distinct groups | median persistence (min) | top peak edge |
|---|---:|---:|---:|---:|
| `dvr` | 98 | 71 | 1335 | +0.4172 |
| `yes_no` | 0 | 0 | — | — |
| `pseudo` | 27 | 21 | 885 | +0.5192 |

## 3. Top 15 `dvr` events (real D vs R races)

| group | peak_edge | persistence (min) | min_liq | start | end |
|---|---:|---:|---:|---|---|
| `0xc715465f2204...` (Will the Democrats win the Ore vs ...) | +0.4172 | 1785 | $411 | 2026-04-28T21:15:00 | 2026-04-30T03:00:00 |
| `0xa7f79f468a16...` (Will the Democrats win the Sou vs ...) | +0.3849 | 17085 | $367 | 2026-04-28T21:15:00 | 2026-05-10T18:00:00 |
| `0x9bb9ed087667...` (Will the Democrats win the Ark vs ...) | +0.3275 | 885 | $215 | 2026-04-28T21:15:00 | 2026-04-29T12:00:00 |
| `0x266416597e36...` (Will the Republican Party win  vs ...) | +0.3251 | 12585 | $206 | 2026-04-28T21:15:00 | 2026-05-07T15:00:00 |
| `0x50a317c8d911...` (Will the Democrats win the Okl vs ...) | +0.2730 | 885 | $122 | 2026-05-03T21:15:00 | 2026-05-04T12:00:00 |
| `0x2aa7cf1991dd...` (Will the Democrats win the Kan vs ...) | +0.2262 | 3585 | $200 | 2026-04-29T12:15:00 | 2026-05-02T00:00:00 |
| `0x5f4893a285ad...` (Will the Democrats win the Wes vs ...) | +0.1979 | 237 | $86 | 2026-05-12T13:53:18 | 2026-05-12T17:50:03 |
| `0x266416597e36...` (Will the Republican Party win  vs ...) | +0.1420 | 3585 | $206 | 2026-05-08T06:15:00 | 2026-05-10T18:00:00 |
| `0xf2c1f951aeee...` (Will the Republican Party win  vs ...) | +0.1357 | 1785 | $248 | 2026-05-02T15:15:00 | 2026-05-03T21:00:00 |
| `0x9bb9ed087667...` (Will the Democrats win the Ark vs ...) | +0.1296 | 885 | $215 | 2026-04-30T03:15:00 | 2026-04-30T18:00:00 |
| `0xf2c1f951aeee...` (Will the Republican Party win  vs ...) | +0.1210 | 4485 | $248 | 2026-05-07T15:15:00 | 2026-05-10T18:00:00 |
| `0xf2c1f951aeee...` (Will the Republican Party win  vs ...) | +0.1113 | 3585 | $248 | 2026-05-04T12:15:00 | 2026-05-07T00:00:00 |
| `0x9bb9ed087667...` (Will the Democrats win the Ark vs ...) | +0.1063 | 3585 | $215 | 2026-05-08T06:15:00 | 2026-05-10T18:00:00 |
| `0xb17c29a2fb22...` (Will the Democrats win the Ten vs ...) | +0.1042 | 177 | $2,082 | 2026-05-12T13:53:18 | 2026-05-12T16:50:04 |
| `0x67d0d210eee8...` (Will the Democrats win the Sou vs ...) | +0.0964 | 2685 | $2,176 | 2026-04-28T21:15:00 | 2026-04-30T18:00:00 |

## 4. Notes

- `dvr` (D vs R) is the only sub-tier that is structurally exhaustive in US politics — third parties get < 1% of vote in modern Senate/Governor general elections.
- `yes_no` heuristic is naive (negation-substring + similarity). Likely under-counts.
- `pseudo` events are NOT tradeable as basket arb — the listed 2 members are a sample, not the whole universe.
- Verdict on dvr depends on event count AND median persistence AND a depth check (NOT done yet — same trap as James Bond, where mid edge > bestAsk edge after slippage).

---
*Generated at 2026-05-12T18:03:42.612726+00:00*