# T2 多模型对比实验报告（2026-05-12T07:11:20.627041+00:00）

**Sample**: n=30 markets stratified by description length
**Models**: 4 via OpenRouter
**Total cost**: $0.0336

## 1. 自动指标对比

| 模型 | 调用 | schema_ok | grounding_ok | nonempty | clauses/市场 | 平均 in/out tok | 平均延迟 | 总成本 | $/call |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Gemini 2.0 Flash | 30 | 30/30 | 30/30 | 30/30 | 2.5 | 518/343 | 3.1s | $0.0057 | $0.00019 |
| DeepSeek V3 | 30 | 30/30 | 30/30 | 30/30 | 2.8 | 490/325 | 16.9s | $0.0147 | $0.00049 |
| GPT-4o-mini | 30 | 30/30 | 28/30 | 30/30 | 2.3 | 491/290 | 5.2s | $0.0074 | $0.00025 |
| Llama 3.3 70B | 30 | 28/30 | 27/30 | 28/30 | 3.1 | 500/320 | 9.8s | $0.0058 | $0.00019 |

## 2. 按 description 长度桶分布（clauses/市场）

| 模型 | short (100-300) | medium (300-700) | long (700+) |
|---|---:|---:|---:|
| Gemini 2.0 Flash | 2.0 | 2.7 | 2.7 |
| DeepSeek V3 | 2.1 | 2.9 | 3.5 |
| GPT-4o-mini | 2.0 | 2.4 | 2.6 |
| Llama 3.3 70B | 1.7 | 3.7 | 3.8 |

## 3. 错误清单

无错误。

## 4. 数据归档

完整 per-call 结果在 `data\experiments\2026-05-12\multi-model-results.ndjson` (120 行)。
下一步：人工 + Claude 裁判模式，按 actionable / structural / trivial 评分各模型 clauses。

---
*Snapshot: 2026-05-12T07:11:20.627041+00:00*