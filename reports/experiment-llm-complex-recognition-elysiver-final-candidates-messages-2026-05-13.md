# LLM 复杂场景识别能力实验报告（2026-05-13T04:38:42.184556+00:00）

## 1. 总体排名

| rank | provider | model | format | cases | success | schema | grounding | pass recall | avg recall | min recall | median latency | first error |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | elysiver | `qwen3-max` | `messages` | 8 | 8 | 8 | 8 | 7 / perfect 3 | 0.87 | 0.71 | 41.96s |  |
| 2 | elysiver | `glm-4.6` | `messages` | 8 | 8 | 8 | 4 | 4 / perfect 2 | 0.88 | 0.71 | 29.55s |  |
| 3 | elysiver | `qwen3.6-plus` | `messages` | 8 | 6 | 6 | 3 | 3 / perfect 2 | 0.84 | 0.67 | 45.45s | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloud |
| 4 | elysiver | `qwen3.5-plus` | `messages` | 8 | 7 | 6 | 5 | 5 / perfect 1 | 0.74 | 0.00 | 43.71s | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloud |
| 5 | elysiver | `qwen3.5-flash` | `messages` | 8 | 7 | 7 | 3 | 3 / perfect 1 | 0.89 | 0.86 | 14.72s | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloud |
| 6 | elysiver | `42-pro` | `messages` | 8 | 8 | 8 | 2 | 1 / perfect 0 | 0.44 | 0.00 | 8.19s |  |
| 7 | elysiver | `deepseek-v4-flash-2cc` | `messages` | 8 | 1 | 1 | 1 | 1 / perfect 0 | 0.88 | 0.88 | 59.13s | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloud |
| 8 | elysiver | `42-mini` | `messages` | 8 | 8 | 7 | 2 | 0 / perfect 0 | 0.39 | 0.00 | 8.00s |  |
| 9 | elysiver | `gpt-5.5-web-auto` | `messages` | 8 | 0 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 0.00s | HTTP 400: {"error":{"type":"MODERATION_BLOCKED","message":"Smart moderation blocked by hashlinear_mo |

## 2. 按 case 明细

| provider | model | format | case | recall | met/total | pass | missed | latency |
|---|---|---|---|---:|---:|---|---|---:|
| elysiver | `qwen3.5-flash` | `messages` | `ipo_openai_bracket` | 0.86 | 6/7 | no | interruption_next_trading_day | 13.26s |
| elysiver | `qwen3.5-flash` | `messages` | `weinstein_sentencing_bracket` | 0.88 | 7/8 | yes | threshold_less_than_5 | 13.14s |
| elysiver | `qwen3.5-flash` | `messages` | `mamdani_rent_freeze` | 0.00 | 0/0 | no | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-504/","title":"Er | 0.00s |
| elysiver | `qwen3.5-flash` | `messages` | `canada_recession_dual_path` | 0.86 | 6/7 | no | statcan_two_quarters | 16.77s |
| elysiver | `qwen3.5-flash` | `messages` | `gpt6_before_gta_vi` | 0.89 | 8/9 | no | race_condition | 15.14s |
| elysiver | `qwen3.5-flash` | `messages` | `esports_odd_even_kills` | 0.89 | 8/9 | yes | odd_even_game2 | 14.72s |
| elysiver | `qwen3.5-flash` | `messages` | `balance_of_power_resolution` | 1.00 | 7/7 | yes |  | 34.27s |
| elysiver | `qwen3.5-flash` | `messages` | `ukraine_peace_deal_signature` | 0.89 | 8/9 | no | written_instrument | 14.39s |
| elysiver | `qwen3-max` | `messages` | `ipo_openai_bracket` | 0.86 | 6/7 | yes | interruption_next_trading_day | 39.27s |
| elysiver | `qwen3-max` | `messages` | `weinstein_sentencing_bracket` | 0.75 | 6/8 | yes | threshold_less_than_5, concurrent_consecutive_total | 39.62s |
| elysiver | `qwen3-max` | `messages` | `mamdani_rent_freeze` | 1.00 | 9/9 | yes |  | 52.80s |
| elysiver | `qwen3-max` | `messages` | `canada_recession_dual_path` | 0.71 | 5/7 | no | cd_howe_path, statcan_two_quarters | 47.05s |
| elysiver | `qwen3-max` | `messages` | `gpt6_before_gta_vi` | 1.00 | 9/9 | yes |  | 49.89s |
| elysiver | `qwen3-max` | `messages` | `esports_odd_even_kills` | 0.78 | 7/9 | yes | odd_even_game2, champion_kills_include | 40.23s |
| elysiver | `qwen3-max` | `messages` | `balance_of_power_resolution` | 1.00 | 7/7 | yes |  | 43.68s |
| elysiver | `qwen3-max` | `messages` | `ukraine_peace_deal_signature` | 0.89 | 8/9 | yes | written_instrument | 38.47s |
| elysiver | `qwen3.5-plus` | `messages` | `ipo_openai_bracket` | 0.86 | 6/7 | yes | interruption_next_trading_day | 46.00s |
| elysiver | `qwen3.5-plus` | `messages` | `weinstein_sentencing_bracket` | 0.75 | 6/8 | yes | threshold_less_than_5, concurrent_consecutive_total | 38.24s |
| elysiver | `qwen3.5-plus` | `messages` | `mamdani_rent_freeze` | 0.89 | 8/9 | yes | both_conditions | 55.22s |
| elysiver | `qwen3.5-plus` | `messages` | `canada_recession_dual_path` | 0.00 | 0/7 | no | cd_howe_path, announcement_deadline, statcan_two_quarters, negative_gdp_threshold, concurrent_vintages, stay_open_q4, sources | 4.11s |
| elysiver | `qwen3.5-plus` | `messages` | `gpt6_before_gta_vi` | 0.89 | 8/9 | yes | race_condition | 43.71s |
| elysiver | `qwen3.5-plus` | `messages` | `esports_odd_even_kills` | 0.78 | 7/9 | no | odd_even_game2, champion_kills_include | 30.64s |
| elysiver | `qwen3.5-plus` | `messages` | `balance_of_power_resolution` | 1.00 | 7/7 | yes |  | 47.95s |
| elysiver | `qwen3.5-plus` | `messages` | `ukraine_peace_deal_signature` | 0.00 | 0/0 | no | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-504/","title":"Er | 0.00s |
| elysiver | `qwen3.6-plus` | `messages` | `ipo_openai_bracket` | 0.00 | 0/0 | no | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-504/","title":"Er | 0.00s |
| elysiver | `qwen3.6-plus` | `messages` | `weinstein_sentencing_bracket` | 0.75 | 6/8 | yes | threshold_less_than_5, concurrent_consecutive_total | 39.20s |
| elysiver | `qwen3.6-plus` | `messages` | `mamdani_rent_freeze` | 0.78 | 7/9 | no | both_conditions, one_term_specific_units_not_qualify | 51.98s |
| elysiver | `qwen3.6-plus` | `messages` | `canada_recession_dual_path` | 0.86 | 6/7 | no | concurrent_vintages | 43.05s |
| elysiver | `qwen3.6-plus` | `messages` | `gpt6_before_gta_vi` | 1.00 | 9/9 | yes |  | 48.37s |
| elysiver | `qwen3.6-plus` | `messages` | `esports_odd_even_kills` | 0.67 | 6/9 | no | odd_even_game2, champion_kills_include, canceled_delay_50_50 | 32.72s |
| elysiver | `qwen3.6-plus` | `messages` | `balance_of_power_resolution` | 1.00 | 7/7 | yes |  | 47.84s |
| elysiver | `qwen3.6-plus` | `messages` | `ukraine_peace_deal_signature` | 0.00 | 0/0 | no | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-504/","title":"Er | 0.00s |
| elysiver | `42-mini` | `messages` | `ipo_openai_bracket` | 0.57 | 4/7 | no | threshold_lt_500b, market_cap_calculation, interruption_next_trading_day | 8.15s |
| elysiver | `42-mini` | `messages` | `weinstein_sentencing_bracket` | 0.50 | 4/8 | no | threshold_less_than_5, not_guilty_mistrial_no_prison, concurrent_consecutive_total, ny_court_source | 8.16s |
| elysiver | `42-mini` | `messages` | `mamdani_rent_freeze` | 0.33 | 3/9 | no | both_conditions, announcement_not_qualify, other_mechanism_qualifies, one_term_specific_units_not_qualify, loss_immediate_no, source | 6.87s |
| elysiver | `42-mini` | `messages` | `canada_recession_dual_path` | 0.14 | 1/7 | no | cd_howe_path, statcan_two_quarters, negative_gdp_threshold, concurrent_vintages, stay_open_q4, sources | 6.47s |
| elysiver | `42-mini` | `messages` | `gpt6_before_gta_vi` | 0.00 | 0/9 | no | race_condition, neither_50_50, gta_exclusions, console_counts, gta_source, gpt_public_access, closed_private_not, gpt55_not_count | 6.70s |
| elysiver | `42-mini` | `messages` | `esports_odd_even_kills` | 0.56 | 5/9 | no | odd_even_game2, champion_kills_include, executions_exclude, remade_game_only | 13.20s |
| elysiver | `42-mini` | `messages` | `balance_of_power_resolution` | 0.57 | 4/7 | no | candidate_party, house_ambiguity_speaker, senate_ambiguity_majority_leader | 7.85s |
| elysiver | `42-mini` | `messages` | `ukraine_peace_deal_signature` | 0.44 | 4/9 | no | written_instrument, ukraine_signature_only, localized_not_qualify, issue_specific_not, source | 8.94s |
| elysiver | `42-pro` | `messages` | `ipo_openai_bracket` | 0.71 | 5/7 | no | primary_exchange_source, interruption_next_trading_day | 8.38s |
| elysiver | `42-pro` | `messages` | `weinstein_sentencing_bracket` | 0.38 | 3/8 | no | threshold_less_than_5, first_sentence_no_appeals, not_guilty_mistrial_no_prison, concurrent_consecutive_total, ny_court_source | 8.23s |
| elysiver | `42-pro` | `messages` | `mamdani_rent_freeze` | 0.22 | 2/9 | no | both_conditions, zero_percent_both_terms, announcement_not_qualify, blocked_not_qualify, other_mechanism_qualifies, one_term_specific_units_not_qualify, loss_immediate_no | 7.53s |
| elysiver | `42-pro` | `messages` | `canada_recession_dual_path` | 0.43 | 3/7 | no | announcement_deadline, statcan_two_quarters, concurrent_vintages, stay_open_q4 | 7.11s |
| elysiver | `42-pro` | `messages` | `gpt6_before_gta_vi` | 0.00 | 0/9 | no | race_condition, neither_50_50, gta_exclusions, console_counts, gta_source, gpt_public_access, closed_private_not, gpt55_not_count | 7.19s |
| elysiver | `42-pro` | `messages` | `esports_odd_even_kills` | 0.78 | 7/9 | no | executions_exclude, series_already_determined | 8.15s |
| elysiver | `42-pro` | `messages` | `balance_of_power_resolution` | 0.86 | 6/7 | yes | candidate_party | 14.00s |
| elysiver | `42-pro` | `messages` | `ukraine_peace_deal_signature` | 0.11 | 1/9 | no | written_instrument, ceasefire_or_defined_process, ukraine_signature_only, localized_not_qualify, issue_specific_not, wet_ink_e_signature, unsigned_not, source | 8.88s |
| elysiver | `glm-4.6` | `messages` | `ipo_openai_bracket` | 0.86 | 6/7 | no | bracket_tiebreaker | 26.05s |
| elysiver | `glm-4.6` | `messages` | `weinstein_sentencing_bracket` | 0.88 | 7/8 | yes | higher_range_tiebreaker | 36.56s |
| elysiver | `glm-4.6` | `messages` | `mamdani_rent_freeze` | 0.89 | 8/9 | no | both_conditions | 29.68s |
| elysiver | `glm-4.6` | `messages` | `canada_recession_dual_path` | 0.71 | 5/7 | no | cd_howe_path, statcan_two_quarters | 28.11s |
| elysiver | `glm-4.6` | `messages` | `gpt6_before_gta_vi` | 1.00 | 9/9 | yes |  | 32.67s |
| elysiver | `glm-4.6` | `messages` | `esports_odd_even_kills` | 0.78 | 7/9 | yes | odd_even_game2, champion_kills_include | 26.72s |
| elysiver | `glm-4.6` | `messages` | `balance_of_power_resolution` | 1.00 | 7/7 | yes |  | 29.43s |
| elysiver | `glm-4.6` | `messages` | `ukraine_peace_deal_signature` | 0.89 | 8/9 | no | written_instrument | 30.16s |
| elysiver | `gpt-5.5-web-auto` | `messages` | `ipo_openai_bracket` | 0.00 | 0/0 | no | HTTP 400: {"error":{"type":"MODERATION_BLOCKED","message":"Smart moderation blocked by hashlinear_model (confidence: 0.535) (request id: 202 | 0.00s |
| elysiver | `gpt-5.5-web-auto` | `messages` | `weinstein_sentencing_bracket` | 0.00 | 0/0 | no | HTTP 400: {"error":{"type":"MODERATION_BLOCKED","message":"Smart moderation blocked by hashlinear_model (confidence: 0.578) (request id: 202 | 0.00s |
| elysiver | `gpt-5.5-web-auto` | `messages` | `mamdani_rent_freeze` | 0.00 | 0/0 | no | HTTP 400: {"error":{"type":"MODERATION_BLOCKED","message":"Smart moderation blocked by hashlinear_model (confidence: 0.576) (request id: 202 | 0.00s |
| elysiver | `gpt-5.5-web-auto` | `messages` | `canada_recession_dual_path` | 0.00 | 0/0 | no | HTTP 400: {"error":{"type":"MODERATION_BLOCKED","message":"Smart moderation blocked by hashlinear_model (confidence: 0.538) (request id: 202 | 0.00s |
| elysiver | `gpt-5.5-web-auto` | `messages` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | HTTP 400: {"error":{"type":"MODERATION_BLOCKED","message":"Smart moderation blocked by hashlinear_model (confidence: 0.524) (request id: 202 | 0.00s |
| elysiver | `gpt-5.5-web-auto` | `messages` | `esports_odd_even_kills` | 0.00 | 0/0 | no | HTTP 400: {"error":{"type":"MODERATION_BLOCKED","message":"Smart moderation blocked by hashlinear_model (confidence: 0.517) (request id: 202 | 0.00s |
| elysiver | `gpt-5.5-web-auto` | `messages` | `balance_of_power_resolution` | 0.00 | 0/0 | no | HTTP 400: {"error":{"type":"MODERATION_BLOCKED","message":"Smart moderation blocked by hashlinear_model (confidence: 0.606) (request id: 202 | 0.00s |
| elysiver | `gpt-5.5-web-auto` | `messages` | `ukraine_peace_deal_signature` | 0.00 | 0/0 | no | HTTP 400: {"error":{"type":"MODERATION_BLOCKED","message":"Smart moderation blocked by hashlinear_model (confidence: 0.618) (request id: 202 | 0.00s |
| elysiver | `deepseek-v4-flash-2cc` | `messages` | `ipo_openai_bracket` | 0.00 | 0/0 | no | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-504/","title":"Er | 0.00s |
| elysiver | `deepseek-v4-flash-2cc` | `messages` | `weinstein_sentencing_bracket` | 0.88 | 7/8 | yes | threshold_less_than_5 | 59.13s |
| elysiver | `deepseek-v4-flash-2cc` | `messages` | `mamdani_rent_freeze` | 0.00 | 0/0 | no | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-504/","title":"Er | 0.00s |
| elysiver | `deepseek-v4-flash-2cc` | `messages` | `canada_recession_dual_path` | 0.00 | 0/0 | no | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-504/","title":"Er | 0.00s |
| elysiver | `deepseek-v4-flash-2cc` | `messages` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-504/","title":"Er | 0.00s |
| elysiver | `deepseek-v4-flash-2cc` | `messages` | `esports_odd_even_kills` | 0.00 | 0/0 | no | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-504/","title":"Er | 0.00s |
| elysiver | `deepseek-v4-flash-2cc` | `messages` | `balance_of_power_resolution` | 0.00 | 0/0 | no | HTTP 502: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-502/","title":"Er | 0.00s |
| elysiver | `deepseek-v4-flash-2cc` | `messages` | `ukraine_peace_deal_signature` | 0.00 | 0/0 | no | HTTP 502: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-502/","title":"Er | 0.00s |

## 3. 解释

- 这个实验比 endpoint-format benchmark 更严格：必须命中人工标注的真实复杂 resolution 规则。
- `pass recall` 表示某模型在多少个 case 上达到该 case 的最低语义召回阈值，同时 schema 和 grounding 合格。
- `perfect` 表示该 case 的人工 golden requirements 全部命中；这是最严格排序的第一优先级。
- 真实自动套利系统应优先选择 `perfect`、`pass recall`、`min recall` 更高的模型，而不是只看 latency。

## 4. 数据归档

- per-call NDJSON: `data/experiments/2026-05-13/llm-complex-recognition-elysiver-final-candidates-messages.ndjson`
- rows: 72

---
*Snapshot: 2026-05-13T04:38:42.184556+00:00*