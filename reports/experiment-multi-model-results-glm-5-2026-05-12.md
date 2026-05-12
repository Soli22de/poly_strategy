# T2 多模型对比实验报告（2026-05-12T08:55:14.783393+00:00）

**Sample**: n=30 markets stratified by description length
**Models**: 1 via OpenRouter
**Total cost**: $0.0000

## 1. 自动指标对比

| 模型 | 调用 | schema_ok | grounding_ok | nonempty | clauses/市场 | 平均 in/out tok | 平均延迟 | 总成本 | $/call |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| GLM-5 (elysiver) | 30 | 16/16 | 16/16 | 16/16 | 3.9 | 448/402 | 40.9s | $0.0000 | $0.00000 |

## 2. 按 description 长度桶分布（clauses/市场）

| 模型 | short (100-300) | medium (300-700) | long (700+) |
|---|---:|---:|---:|
| GLM-5 (elysiver) | 3.0 | 4.2 | 4.6 |

## 3. 错误清单

- `glm-5` on `631187`: HTTP 504: error code: 504
- `glm-5` on `676843`: HTTP 504: error code: 504
- `glm-5` on `676745`: HTTP 504: error code: 504
- `glm-5` on `676741`: HTTP 504: error code: 504
- `glm-5` on `679504`: HTTP 504: error code: 504
- `glm-5` on `687272`: HTTP 504: error code: 504
- `glm-5` on `620682`: HTTP 504: error code: 504
- `glm-5` on `678930`: HTTP 504: error code: 504
- `glm-5` on `558975`: HTTP 504: error code: 504
- `glm-5` on `631125`: HTTP 504: error code: 504
- `glm-5` on `701757`: HTTP 504: error code: 504
- `glm-5` on `679028`: HTTP 504: error code: 504
- `glm-5` on `577177`: HTTP 504: error code: 504
- `glm-5` on `618508`: HTTP 504: error code: 504

## 4. 数据归档

完整 per-call 结果在 `data\experiments\2026-05-12\multi-model-results-glm-5.ndjson` (30 行)。
下一步：人工 + Claude 裁判模式，按 actionable / structural / trivial 评分各模型 clauses。

---
*Snapshot: 2026-05-12T08:55:14.783393+00:00*