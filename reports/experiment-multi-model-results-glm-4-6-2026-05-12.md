# T2 多模型对比实验报告（2026-05-12T08:48:17.704098+00:00）

**Sample**: n=30 markets stratified by description length
**Models**: 1 via OpenRouter
**Total cost**: $0.0000

## 1. 自动指标对比

| 模型 | 调用 | schema_ok | grounding_ok | nonempty | clauses/市场 | 平均 in/out tok | 平均延迟 | 总成本 | $/call |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| GLM-4.6 (elysiver) | 30 | 29/29 | 29/29 | 29/29 | 3.3 | 537/409 | 13.0s | $0.0000 | $0.00000 |

## 2. 按 description 长度桶分布（clauses/市场）

| 模型 | short (100-300) | medium (300-700) | long (700+) |
|---|---:|---:|---:|
| GLM-4.6 (elysiver) | 2.1 | 3.6 | 4.2 |

## 3. 错误清单

- `glm-4.6` on `579379`: URL error: [WinError 10060] 由于连接方在一段时间后没有正确答复或连接的主机没有反应，连接尝试失败。

## 4. 数据归档

完整 per-call 结果在 `data\experiments\2026-05-12\multi-model-results-glm-4-6.ndjson` (30 行)。
下一步：人工 + Claude 裁判模式，按 actionable / structural / trivial 评分各模型 clauses。

---
*Snapshot: 2026-05-12T08:48:17.704098+00:00*