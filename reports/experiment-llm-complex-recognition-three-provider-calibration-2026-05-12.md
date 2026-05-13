# LLM 复杂场景识别能力实验报告（2026-05-12T17:22:03.482567+00:00）

## 1. 总体排名

| rank | provider | model | format | cases | success | schema | grounding | pass recall | avg recall | min recall | median latency | first error |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | windhub | `doubao-1-5-pro-32k-250115` | `messages` | 2 | 2 | 2 | 0 | 0 / perfect 0 | 0.76 | 0.67 | 27.64s |  |
| 2 | elysiver | `gemini-2.5-flash` | `messages` | 2 | 1 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 17.68s | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloud |
| 3 | secondary | `gemini-2.5-flash` | `messages` | 2 | 0 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 0.00s | HTTP 554:  |

## 2. 按 case 明细

| provider | model | format | case | recall | met/total | pass | missed | latency |
|---|---|---|---|---:|---:|---|---|---:|
| windhub | `doubao-1-5-pro-32k-250115` | `messages` | `ipo_openai_bracket` | 0.86 | 6/7 | no | threshold_lt_500b | 25.11s |
| windhub | `doubao-1-5-pro-32k-250115` | `messages` | `gpt6_before_gta_vi` | 0.67 | 6/9 | no | neither_50_50, gta_source, gpt55_not_count | 30.16s |
| secondary | `gemini-2.5-flash` | `messages` | `ipo_openai_bracket` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-2.5-flash` | `messages` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| elysiver | `gemini-2.5-flash` | `messages` | `ipo_openai_bracket` | 0.00 | 0/7 | no | threshold_lt_500b, no_ipo_deadline, no_ipo_fallback, market_cap_calculation, bracket_tiebreaker, primary_exchange_source, interruption_next_trading_day | 17.68s |
| elysiver | `gemini-2.5-flash` | `messages` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-504/","title":"Er | 0.00s |

## 3. 解释

- 这个实验比 endpoint-format benchmark 更严格：必须命中人工标注的真实复杂 resolution 规则。
- `pass recall` 表示某模型在多少个 case 上达到该 case 的最低语义召回阈值，同时 schema 和 grounding 合格。
- `perfect` 表示该 case 的人工 golden requirements 全部命中；这是最严格排序的第一优先级。
- 真实自动套利系统应优先选择 `perfect`、`pass recall`、`min recall` 更高的模型，而不是只看 latency。

## 4. 数据归档

- per-call NDJSON: `data/experiments/2026-05-12/llm-complex-recognition-three-provider-calibration.ndjson`
- rows: 6

---
*Snapshot: 2026-05-12T17:22:03.482567+00:00*