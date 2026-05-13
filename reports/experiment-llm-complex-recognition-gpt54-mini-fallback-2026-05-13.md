# LLM 复杂场景识别能力实验报告（2026-05-13T10:24:50.562664+00:00）

> 注：表中的 provider label `windhub` 是 benchmark 脚本复用的环境槽位；本次运行实际把 `OPENAI_BASE_URL`/`OPENAI_API_KEY` 指向原 responses fallback 端点，测试对象是 `gpt-5.4-mini/responses`。

## 1. 总体排名

| rank | provider | model | format | cases | success | schema | grounding | pass recall | avg recall | min recall | median latency | first error |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | windhub | `gpt-5.4-mini` | `responses` | 8 | 8 | 8 | 8 | 7 / perfect 3 | 0.90 | 0.71 | 11.03s |  |

## 2. 按 case 明细

| provider | model | format | case | recall | met/total | pass | missed | latency |
|---|---|---|---|---:|---:|---|---|---:|
| windhub | `gpt-5.4-mini` | `responses` | `ipo_openai_bracket` | 0.71 | 5/7 | no | threshold_lt_500b, interruption_next_trading_day | 11.53s |
| windhub | `gpt-5.4-mini` | `responses` | `weinstein_sentencing_bracket` | 0.88 | 7/8 | yes | concurrent_consecutive_total | 11.65s |
| windhub | `gpt-5.4-mini` | `responses` | `mamdani_rent_freeze` | 0.89 | 8/9 | yes | both_conditions | 12.64s |
| windhub | `gpt-5.4-mini` | `responses` | `canada_recession_dual_path` | 0.86 | 6/7 | yes | statcan_two_quarters | 10.11s |
| windhub | `gpt-5.4-mini` | `responses` | `gpt6_before_gta_vi` | 1.00 | 9/9 | yes |  | 15.02s |
| windhub | `gpt-5.4-mini` | `responses` | `esports_odd_even_kills` | 1.00 | 9/9 | yes |  | 9.24s |
| windhub | `gpt-5.4-mini` | `responses` | `balance_of_power_resolution` | 1.00 | 7/7 | yes |  | 10.53s |
| windhub | `gpt-5.4-mini` | `responses` | `ukraine_peace_deal_signature` | 0.89 | 8/9 | yes | written_instrument | 9.90s |

## 3. 解释

- 这个实验比 endpoint-format benchmark 更严格：必须命中人工标注的真实复杂 resolution 规则。
- `pass recall` 表示某模型在多少个 case 上达到该 case 的最低语义召回阈值，同时 schema 和 grounding 合格。
- `perfect` 表示该 case 的人工 golden requirements 全部命中；这是最严格排序的第一优先级。
- 真实自动套利系统应优先选择 `perfect`、`pass recall`、`min recall` 更高的模型，而不是只看 latency。

## 4. 数据归档

- per-call NDJSON: `data/experiments/2026-05-13/llm-complex-recognition-gpt54-mini-fallback.ndjson`
- rows: 8

---
*Snapshot: 2026-05-13T10:24:50.562664+00:00*
