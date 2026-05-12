# Windhub / Elysiver Endpoint Format 实验报告（2026-05-12T16:49:50.883687+00:00）

## 1. 模型枚举

### windhub
- `deepseek-v3-2-251201` (unknown_or_mid) owned_by=volcengine
- `doubao-1-5-pro-32k-250115` (likely_high) owned_by=volcengine
- `doubao-seed-1-6-251015` (unknown_or_mid) owned_by=volcengine
- `doubao-seed-1-8-251228` (unknown_or_mid) owned_by=volcengine
- `doubao-seed-2-0-lite-260428` (likely_low) owned_by=custom
- `doubao-seedream-4-5-251128` (unknown_or_mid) owned_by=seedream
- `glm-5.1` (unknown_or_mid) owned_by=custom
- `kimi-k2.6` (unknown_or_mid) owned_by=custom
- `mimo-v2.5` (likely_low) owned_by=custom
- `mimo-v2.5-pro` (likely_low) owned_by=custom

## 2. 实测模型范围

- windhub: `deepseek-v3-2-251201`, `doubao-1-5-pro-32k-250115`

## 3. 自动指标对比

| provider | model | format | calls | success | schema | grounding | nonempty | clauses/market | median latency | token in/out | cost class | first error |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| windhub | `deepseek-v3-2-251201` | `chat` | 3 | 3 | 3 | 3 | 3 | 2.0 | 12.80s | 475/261 | unknown_or_mid |  |
| windhub | `deepseek-v3-2-251201` | `messages` | 3 | 3 | 3 | 3 | 3 | 3.0 | 12.81s | 475/316 | unknown_or_mid |  |
| windhub | `doubao-1-5-pro-32k-250115` | `chat` | 3 | 3 | 3 | 3 | 3 | 2.0 | 6.47s | 515/332 | likely_high |  |
| windhub | `doubao-1-5-pro-32k-250115` | `messages` | 3 | 3 | 3 | 3 | 3 | 2.0 | 6.40s | 515/323 | likely_high |  |

## 4. 推荐

1. `windhub` / `doubao-1-5-pro-32k-250115` / `messages`: median 6.40s, schema 3/3, grounding 3/3, cost_class=likely_high.
2. `windhub` / `doubao-1-5-pro-32k-250115` / `chat`: median 6.47s, schema 3/3, grounding 3/3, cost_class=likely_high.
3. `windhub` / `deepseek-v3-2-251201` / `chat`: median 12.80s, schema 3/3, grounding 3/3, cost_class=unknown_or_mid.
4. `windhub` / `deepseek-v3-2-251201` / `messages`: median 12.81s, schema 3/3, grounding 3/3, cost_class=unknown_or_mid.

说明：`cost_class` 是按模型名的保守启发式分类，因为这两个 `/models` 返回没有暴露 pricing 字段；真实价格仍需以服务商后台为准。

## 5. 数据归档

- per-call NDJSON: `data/experiments/2026-05-12/llm-endpoint-format-windhub-candidates.ndjson`
- rows: 12

---
*Snapshot: 2026-05-12T16:49:50.883687+00:00*