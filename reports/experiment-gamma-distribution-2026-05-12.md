# Gamma 分布 + 结构化关系 实验报告（2026-05-12T06:16:23.751849+00:00）

**来源**：`scripts/experiment_gamma_distribution.py` 一次性实验，不是 DS pkg #02 的最终实现。
**用途**：回填 §9 Q1（长尾 tier 阈值）+ T4 $0 corpus 可行性验证 + T2 fixture 数据。

---

## 1. 基本统计

- 拉取总市场数：2000
- 通过过滤的活跃市场：2000
  (active=true & enableOrderBook!=false & acceptingOrders!=false & closed!=true)

## 2. 总体分布百分位（活跃市场）

- **volume24hr**：P5=$0 | P10=$0 | P25=$0 | P50=$40 | P75=$1,483 | P90=$18,333 | P95=$46,489 | P99=$471,419
- **volume1wk**：P5=$0 | P10=$0 | P25=$0 | P50=$379 | P75=$12,730 | P90=$185,724 | P95=$435,886 | P99=$1,485,768
- **liquidity**：P5=$346 | P10=$787 | P25=$2,634 | P50=$10,138 | P75=$29,733 | P90=$221,690 | P95=$940,321 | P99=$6,003,525
- **spread** (n=2000): P5=0.0010 | P10=0.0010 | P25=0.0010 | P50=0.0100 | P75=0.0300 | P90=0.1001 | P95=0.1900 | P99=0.7101

## 3. 距 resolution 分布

- `<7d`: 18 (0.9%)
- `7-14d`: 16 (0.8%)
- `14-30d`: 326 (16.3%)
- `30-90d`: 367 (18.4%)
- `90-180d`: 152 (7.6%)
- `>180d`: 907 (45.4%)
- `expired`: 54 (2.7%)
- `unknown`: 160 (8.0%)

## 4. Top 10 series（Gamma 无 first-class category，用 `events[0].series` 代理）

- `untagged`: 1499 (75.0%)
- `yearly-ipos`: 22 (1.1%)
- `trump-countries-visited`: 18 (0.9%)
- `trump-monthly-meeting`: 16 (0.8%)
- `trump-trade-deal-countries`: 16 (0.8%)
- `top-ai-company-style-on`: 15 (0.8%)
- `best-ai-company`: 15 (0.8%)
- `second-best-ai-company`: 15 (0.8%)
- `largest-company`: 15 (0.8%)
- `bitcoin-hit-price-monthly`: 15 (0.8%)

## 5. Q1 数据驱动 tier 阈值候选

**直接可填进 §9 Q1 Decision**：

- `headline` tier (P90+): volume24hr ≥ $18,333, liquidity ≥ $221,690, spread ≤ 0.0010
- `mid` tier (P50-P90):   volume24hr $40–$18,333, liquidity $10,138–$221,690, spread ≤ 0.0100
- `longtail` tier (P10-P50): volume24hr $0–$40, liquidity $787–$10,138, spread ≤ 0.1001
- `dead` tier (<P10):     volume24hr ≤ $0, liquidity < $787

**注意**：因 P10 = $0，`longtail` 和 `dead` 的边界在 volume24hr 上重合（都从 0 起）。实务建议：用 **liquidity ≥ $791** 区分 longtail 和 dead；vol24hr=0 但 liquidity 在 $791-$10k 区间的市场是真长尾（做市商不来但有底子），vol24hr=0 且 liquidity<$791 才算 dead。

**对比方案初稿**：

| Tier | 方案初稿 | 数据驱动 (实测) | 差距 |
|---|---|---|---|
| headline (vol24h) | ≥ $50,000 | ≥ $18,333 | 初稿偏高 |
| mid 下限 (vol24h) | ≥ $5,000  | ≥ $40 | 初稿偏高 |
| longtail 下限 (vol24h) | ≥ $100  | ≥ $0 | 初稿偏高 |

## 6. T4 $0 corpus 可行性验证

- **Neg-risk 组数（≥2 市场）**：171
- **派生 mutex pairs**：10122
- **完全相同 question+endDate 组数**：1
- **派生 equivalent pairs**：1

✅ **T4 $0 corpus 可行**：mutex pairs (10122) ≥ 50 个，足够采样作 T4 judge 校准 ground truth。

## 7. 数据质量警告

- `unknown` 距 resolution 桶 = 160 个市场缺 endDate
- 总数（2000）vs 活跃数（2000）差距 = 0 个被过滤掉

---

*Snapshot: 2026-05-12T06:16:23.751849+00:00, source: gamma-api.polymarket.com/markets*