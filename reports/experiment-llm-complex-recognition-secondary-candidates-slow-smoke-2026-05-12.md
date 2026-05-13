# LLM 复杂场景识别能力实验报告（2026-05-12T17:31:07.493386+00:00）

## 1. 总体排名

| rank | provider | model | format | cases | success | schema | grounding | pass recall | avg recall | min recall | median latency | first error |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | secondary | `gemini-2.5-flash-nothinking` | `messages` | 2 | 1 | 1 | 1 | 0 / perfect 0 | 0.71 | 0.71 | 15.15s | HTTP 554:  |
| 2 | secondary | `gemini-2.5-flash-nothinking` | `chat` | 2 | 1 | 1 | 0 | 0 / perfect 0 | 1.00 | 1.00 | 15.03s | HTTP 554:  |
| 3 | secondary | `gemini-2.5-flash` | `chat` | 2 | 0 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 0.00s | HTTP 554:  |
| 4 | secondary | `gemini-2.5-flash` | `messages` | 2 | 0 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 0.00s | HTTP 554:  |
| 5 | secondary | `gemini-2.5-pro` | `chat` | 2 | 0 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 0.00s | HTTP 554:  |
| 6 | secondary | `gemini-3-flash-preview` | `chat` | 2 | 0 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 0.00s | HTTP 554:  |
| 7 | secondary | `mimo-v2.5` | `chat` | 2 | 0 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 0.00s | HTTP 429: {"error":{"message":"quota exhausted","type":"limitation","param":"","code":"429"}} |
| 8 | secondary | `mimo-v2.5-pro` | `chat` | 2 | 0 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 0.00s | HTTP 429: {"error":{"message":"quota exhausted","type":"limitation","param":"","code":"429"}} |

## 2. 按 case 明细

| provider | model | format | case | recall | met/total | pass | missed | latency |
|---|---|---|---|---:|---:|---|---|---:|
| secondary | `gemini-2.5-flash` | `chat` | `ipo_openai_bracket` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-2.5-flash` | `chat` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-2.5-flash-nothinking` | `chat` | `ipo_openai_bracket` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-2.5-flash-nothinking` | `chat` | `gpt6_before_gta_vi` | 1.00 | 9/9 | no |  | 15.03s |
| secondary | `gemini-3-flash-preview` | `chat` | `ipo_openai_bracket` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-3-flash-preview` | `chat` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-2.5-pro` | `chat` | `ipo_openai_bracket` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-2.5-pro` | `chat` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `mimo-v2.5` | `chat` | `ipo_openai_bracket` | 0.00 | 0/0 | no | HTTP 429: {"error":{"message":"quota exhausted","type":"limitation","param":"","code":"429"}} | 0.00s |
| secondary | `mimo-v2.5` | `chat` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | HTTP 429: {"error":{"message":"quota exhausted","type":"limitation","param":"","code":"429"}} | 0.00s |
| secondary | `mimo-v2.5-pro` | `chat` | `ipo_openai_bracket` | 0.00 | 0/0 | no | HTTP 429: {"error":{"message":"quota exhausted","type":"limitation","param":"","code":"429"}} | 0.00s |
| secondary | `mimo-v2.5-pro` | `chat` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | HTTP 429: {"error":{"message":"quota exhausted","type":"limitation","param":"","code":"429"}} | 0.00s |
| secondary | `gemini-2.5-flash` | `messages` | `ipo_openai_bracket` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-2.5-flash` | `messages` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-2.5-flash-nothinking` | `messages` | `ipo_openai_bracket` | 0.71 | 5/7 | no | threshold_lt_500b, interruption_next_trading_day | 15.15s |
| secondary | `gemini-2.5-flash-nothinking` | `messages` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |

## 3. 解释

- 这个实验比 endpoint-format benchmark 更严格：必须命中人工标注的真实复杂 resolution 规则。
- `pass recall` 表示某模型在多少个 case 上达到该 case 的最低语义召回阈值，同时 schema 和 grounding 合格。
- `perfect` 表示该 case 的人工 golden requirements 全部命中；这是最严格排序的第一优先级。
- 真实自动套利系统应优先选择 `perfect`、`pass recall`、`min recall` 更高的模型，而不是只看 latency。

## 4. 数据归档

- per-call NDJSON: `data/experiments/2026-05-12/llm-complex-recognition-secondary-candidates-slow-smoke.ndjson`
- rows: 16

---
*Snapshot: 2026-05-12T17:31:07.493386+00:00*