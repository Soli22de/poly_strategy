# LLM 复杂场景识别能力实验报告（2026-05-13T03:12:28.097774+00:00）

## 1. 总体排名

| rank | provider | model | format | cases | success | schema | grounding | pass recall | avg recall | min recall | median latency | first error |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | secondary | `gemini-2.5-flash-nothinking` | `messages` | 8 | 8 | 8 | 8 | 7 / perfect 4 | 0.91 | 0.71 | 9.20s |  |
| 2 | secondary | `gemini-2.5-flash-nothinking` | `chat_stream_plain` | 8 | 5 | 5 | 5 | 4 / perfect 3 | 0.92 | 0.71 | 23.58s | HTTP 554:  |
| 3 | secondary | `gemini-3.1-pro-preview` | `chat_stream` | 8 | 8 | 8 | 8 | 6 / perfect 1 | 0.81 | 0.57 | 9.71s |  |
| 4 | secondary | `gemini-3.1-pro-preview` | `messages` | 8 | 7 | 7 | 7 | 6 / perfect 0 | 0.80 | 0.57 | 10.72s | HTTP 554:  |
| 5 | secondary | `gemini-3.1-pro-preview` | `chat_plain` | 8 | 6 | 6 | 6 | 4 / perfect 0 | 0.78 | 0.57 | 10.07s | HTTP 554:  |
| 6 | secondary | `glm-5` | `chat_stream_plain` | 8 | 8 | 6 | 3 | 3 / perfect 0 | 0.66 | 0.00 | 59.11s |  |
| 7 | secondary | `gemini-2.5-flash-nothinking` | `chat` | 8 | 3 | 3 | 2 | 2 / perfect 0 | 0.92 | 0.88 | 9.46s | HTTP 554:  |
| 8 | secondary | `gemini-3-flash-preview` | `messages` | 8 | 4 | 2 | 2 | 2 / perfect 0 | 0.42 | 0.00 | 15.86s | HTTP 554:  |
| 9 | secondary | `gemini-3-flash-preview` | `chat_stream` | 8 | 6 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 14.11s | HTTP 554:  |
| 10 | secondary | `gemini-2.5-pro` | `chat_stream` | 8 | 5 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 14.94s | HTTP 554:  |
| 11 | secondary | `gemini-2.5-pro` | `messages` | 8 | 1 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 15.63s | HTTP 554:  |
| 12 | secondary | `glm-5` | `messages` | 8 | 0 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 0.00s | HTTP 554:  |

## 2. 按 case 明细

| provider | model | format | case | recall | met/total | pass | missed | latency |
|---|---|---|---|---:|---:|---|---|---:|
| secondary | `gemini-2.5-flash-nothinking` | `messages` | `ipo_openai_bracket` | 0.71 | 5/7 | no | threshold_lt_500b, interruption_next_trading_day | 6.58s |
| secondary | `gemini-2.5-flash-nothinking` | `messages` | `weinstein_sentencing_bracket` | 0.88 | 7/8 | yes | threshold_less_than_5 | 9.02s |
| secondary | `gemini-2.5-flash-nothinking` | `messages` | `mamdani_rent_freeze` | 1.00 | 9/9 | yes |  | 10.24s |
| secondary | `gemini-2.5-flash-nothinking` | `messages` | `canada_recession_dual_path` | 1.00 | 7/7 | yes |  | 9.81s |
| secondary | `gemini-2.5-flash-nothinking` | `messages` | `gpt6_before_gta_vi` | 1.00 | 9/9 | yes |  | 7.93s |
| secondary | `gemini-2.5-flash-nothinking` | `messages` | `esports_odd_even_kills` | 0.78 | 7/9 | yes | odd_even_game2, champion_kills_include | 9.37s |
| secondary | `gemini-2.5-flash-nothinking` | `messages` | `balance_of_power_resolution` | 1.00 | 7/7 | yes |  | 9.74s |
| secondary | `gemini-2.5-flash-nothinking` | `messages` | `ukraine_peace_deal_signature` | 0.89 | 8/9 | yes | written_instrument | 8.69s |
| secondary | `gemini-2.5-flash-nothinking` | `chat_stream_plain` | `ipo_openai_bracket` | 0.71 | 5/7 | no | threshold_lt_500b, interruption_next_trading_day | 11.16s |
| secondary | `gemini-2.5-flash-nothinking` | `chat_stream_plain` | `weinstein_sentencing_bracket` | 0.88 | 7/8 | yes | threshold_less_than_5 | 17.00s |
| secondary | `gemini-2.5-flash-nothinking` | `chat_stream_plain` | `mamdani_rent_freeze` | 1.00 | 9/9 | yes |  | 23.62s |
| secondary | `gemini-2.5-flash-nothinking` | `chat_stream_plain` | `canada_recession_dual_path` | 1.00 | 7/7 | yes |  | 23.90s |
| secondary | `gemini-2.5-flash-nothinking` | `chat_stream_plain` | `gpt6_before_gta_vi` | 1.00 | 9/9 | yes |  | 23.58s |
| secondary | `gemini-2.5-flash-nothinking` | `chat_stream_plain` | `esports_odd_even_kills` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-2.5-flash-nothinking` | `chat_stream_plain` | `balance_of_power_resolution` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-2.5-flash-nothinking` | `chat_stream_plain` | `ukraine_peace_deal_signature` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-2.5-flash-nothinking` | `chat` | `ipo_openai_bracket` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-2.5-flash-nothinking` | `chat` | `weinstein_sentencing_bracket` | 0.88 | 7/8 | yes | threshold_less_than_5 | 16.32s |
| secondary | `gemini-2.5-flash-nothinking` | `chat` | `mamdani_rent_freeze` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-2.5-flash-nothinking` | `chat` | `canada_recession_dual_path` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-2.5-flash-nothinking` | `chat` | `gpt6_before_gta_vi` | 1.00 | 9/9 | no |  | 9.46s |
| secondary | `gemini-2.5-flash-nothinking` | `chat` | `esports_odd_even_kills` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-2.5-flash-nothinking` | `chat` | `balance_of_power_resolution` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-2.5-flash-nothinking` | `chat` | `ukraine_peace_deal_signature` | 0.89 | 8/9 | yes | written_instrument | 6.61s |
| secondary | `gemini-3.1-pro-preview` | `chat_stream` | `ipo_openai_bracket` | 0.71 | 5/7 | no | no_ipo_fallback, interruption_next_trading_day | 9.03s |
| secondary | `gemini-3.1-pro-preview` | `chat_stream` | `weinstein_sentencing_bracket` | 0.75 | 6/8 | yes | threshold_less_than_5, concurrent_consecutive_total | 9.04s |
| secondary | `gemini-3.1-pro-preview` | `chat_stream` | `mamdani_rent_freeze` | 0.78 | 7/9 | yes | both_conditions, announcement_not_qualify | 10.74s |
| secondary | `gemini-3.1-pro-preview` | `chat_stream` | `canada_recession_dual_path` | 0.57 | 4/7 | no | cd_howe_path, statcan_two_quarters, concurrent_vintages | 9.51s |
| secondary | `gemini-3.1-pro-preview` | `chat_stream` | `gpt6_before_gta_vi` | 0.89 | 8/9 | yes | race_condition | 9.37s |
| secondary | `gemini-3.1-pro-preview` | `chat_stream` | `esports_odd_even_kills` | 0.89 | 8/9 | yes | odd_even_game2 | 9.91s |
| secondary | `gemini-3.1-pro-preview` | `chat_stream` | `balance_of_power_resolution` | 1.00 | 7/7 | yes |  | 10.43s |
| secondary | `gemini-3.1-pro-preview` | `chat_stream` | `ukraine_peace_deal_signature` | 0.89 | 8/9 | yes | written_instrument | 12.35s |
| secondary | `gemini-3.1-pro-preview` | `chat_plain` | `ipo_openai_bracket` | 0.71 | 5/7 | no | no_ipo_fallback, interruption_next_trading_day | 10.13s |
| secondary | `gemini-3.1-pro-preview` | `chat_plain` | `weinstein_sentencing_bracket` | 0.75 | 6/8 | yes | threshold_less_than_5, concurrent_consecutive_total | 10.88s |
| secondary | `gemini-3.1-pro-preview` | `chat_plain` | `mamdani_rent_freeze` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-3.1-pro-preview` | `chat_plain` | `canada_recession_dual_path` | 0.57 | 4/7 | no | cd_howe_path, statcan_two_quarters, concurrent_vintages | 10.02s |
| secondary | `gemini-3.1-pro-preview` | `chat_plain` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-3.1-pro-preview` | `chat_plain` | `esports_odd_even_kills` | 0.89 | 8/9 | yes | odd_even_game2 | 8.72s |
| secondary | `gemini-3.1-pro-preview` | `chat_plain` | `balance_of_power_resolution` | 0.86 | 6/7 | yes | house_control | 9.02s |
| secondary | `gemini-3.1-pro-preview` | `chat_plain` | `ukraine_peace_deal_signature` | 0.89 | 8/9 | yes | written_instrument | 12.24s |
| secondary | `gemini-3.1-pro-preview` | `messages` | `ipo_openai_bracket` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-3.1-pro-preview` | `messages` | `weinstein_sentencing_bracket` | 0.75 | 6/8 | yes | threshold_less_than_5, concurrent_consecutive_total | 8.55s |
| secondary | `gemini-3.1-pro-preview` | `messages` | `mamdani_rent_freeze` | 0.78 | 7/9 | yes | both_conditions, announcement_not_qualify | 12.16s |
| secondary | `gemini-3.1-pro-preview` | `messages` | `canada_recession_dual_path` | 0.57 | 4/7 | no | cd_howe_path, statcan_two_quarters, concurrent_vintages | 9.19s |
| secondary | `gemini-3.1-pro-preview` | `messages` | `gpt6_before_gta_vi` | 0.89 | 8/9 | yes | race_condition | 14.02s |
| secondary | `gemini-3.1-pro-preview` | `messages` | `esports_odd_even_kills` | 0.89 | 8/9 | yes | odd_even_game2 | 11.00s |
| secondary | `gemini-3.1-pro-preview` | `messages` | `balance_of_power_resolution` | 0.86 | 6/7 | yes | house_control | 10.15s |
| secondary | `gemini-3.1-pro-preview` | `messages` | `ukraine_peace_deal_signature` | 0.89 | 8/9 | yes | written_instrument | 10.72s |
| secondary | `gemini-2.5-pro` | `chat_stream` | `ipo_openai_bracket` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-2.5-pro` | `chat_stream` | `weinstein_sentencing_bracket` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-2.5-pro` | `chat_stream` | `mamdani_rent_freeze` | 0.00 | 0/9 | no | both_conditions, zero_percent_both_terms, deadline, announcement_not_qualify, blocked_not_qualify, other_mechanism_qualifies, one_term_specific_units_not_qualify, loss_immediate_no | 12.56s |
| secondary | `gemini-2.5-pro` | `chat_stream` | `canada_recession_dual_path` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-2.5-pro` | `chat_stream` | `gpt6_before_gta_vi` | 0.00 | 0/9 | no | race_condition, neither_50_50, gta_exclusions, console_counts, gta_source, gpt_public_access, closed_private_not, gpt55_not_count | 17.17s |
| secondary | `gemini-2.5-pro` | `chat_stream` | `esports_odd_even_kills` | 0.00 | 0/9 | no | odd_even_game2, champion_kills_include, executions_exclude, no_kills_50_50, canceled_delay_50_50, forfeit_walkover_50_50, series_already_determined, remade_game_only | 15.00s |
| secondary | `gemini-2.5-pro` | `chat_stream` | `balance_of_power_resolution` | 0.00 | 0/7 | no | house_control, senate_control, candidate_party, house_ambiguity_speaker, senate_ambiguity_majority_leader, three_sources, no_consensus_certification | 12.03s |
| secondary | `gemini-2.5-pro` | `chat_stream` | `ukraine_peace_deal_signature` | 0.00 | 0/9 | no | written_instrument, ceasefire_or_defined_process, deadline, ukraine_signature_only, localized_not_qualify, issue_specific_not, wet_ink_e_signature, unsigned_not | 14.94s |
| secondary | `gemini-2.5-pro` | `messages` | `ipo_openai_bracket` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-2.5-pro` | `messages` | `weinstein_sentencing_bracket` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-2.5-pro` | `messages` | `mamdani_rent_freeze` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-2.5-pro` | `messages` | `canada_recession_dual_path` | 0.00 | 0/7 | no | cd_howe_path, announcement_deadline, statcan_two_quarters, negative_gdp_threshold, concurrent_vintages, stay_open_q4, sources | 15.63s |
| secondary | `gemini-2.5-pro` | `messages` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-2.5-pro` | `messages` | `esports_odd_even_kills` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-2.5-pro` | `messages` | `balance_of_power_resolution` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-2.5-pro` | `messages` | `ukraine_peace_deal_signature` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-3-flash-preview` | `chat_stream` | `ipo_openai_bracket` | 0.00 | 0/7 | no | threshold_lt_500b, no_ipo_deadline, no_ipo_fallback, market_cap_calculation, bracket_tiebreaker, primary_exchange_source, interruption_next_trading_day | 18.59s |
| secondary | `gemini-3-flash-preview` | `chat_stream` | `weinstein_sentencing_bracket` | 0.00 | 0/8 | no | threshold_less_than_5, deadline, first_sentence_no_appeals, not_guilty_mistrial_no_prison, no_sentencing_fallback, higher_range_tiebreaker, concurrent_consecutive_total, ny_court_source | 12.05s |
| secondary | `gemini-3-flash-preview` | `chat_stream` | `mamdani_rent_freeze` | 0.00 | 0/9 | no | both_conditions, zero_percent_both_terms, deadline, announcement_not_qualify, blocked_not_qualify, other_mechanism_qualifies, one_term_specific_units_not_qualify, loss_immediate_no | 11.85s |
| secondary | `gemini-3-flash-preview` | `chat_stream` | `canada_recession_dual_path` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-3-flash-preview` | `chat_stream` | `gpt6_before_gta_vi` | 0.00 | 0/9 | no | race_condition, neither_50_50, gta_exclusions, console_counts, gta_source, gpt_public_access, closed_private_not, gpt55_not_count | 12.80s |
| secondary | `gemini-3-flash-preview` | `chat_stream` | `esports_odd_even_kills` | 0.00 | 0/9 | no | odd_even_game2, champion_kills_include, executions_exclude, no_kills_50_50, canceled_delay_50_50, forfeit_walkover_50_50, series_already_determined, remade_game_only | 16.88s |
| secondary | `gemini-3-flash-preview` | `chat_stream` | `balance_of_power_resolution` | 0.00 | 0/7 | no | house_control, senate_control, candidate_party, house_ambiguity_speaker, senate_ambiguity_majority_leader, three_sources, no_consensus_certification | 15.42s |
| secondary | `gemini-3-flash-preview` | `chat_stream` | `ukraine_peace_deal_signature` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-3-flash-preview` | `messages` | `ipo_openai_bracket` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-3-flash-preview` | `messages` | `weinstein_sentencing_bracket` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-3-flash-preview` | `messages` | `mamdani_rent_freeze` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `gemini-3-flash-preview` | `messages` | `canada_recession_dual_path` | 0.00 | 0/7 | no | cd_howe_path, announcement_deadline, statcan_two_quarters, negative_gdp_threshold, concurrent_vintages, stay_open_q4, sources | 15.78s |
| secondary | `gemini-3-flash-preview` | `messages` | `gpt6_before_gta_vi` | 0.89 | 8/9 | yes | race_condition | 16.23s |
| secondary | `gemini-3-flash-preview` | `messages` | `esports_odd_even_kills` | 0.78 | 7/9 | yes | odd_even_game2, champion_kills_include | 15.94s |
| secondary | `gemini-3-flash-preview` | `messages` | `balance_of_power_resolution` | 0.00 | 0/7 | no | house_control, senate_control, candidate_party, house_ambiguity_speaker, senate_ambiguity_majority_leader, three_sources, no_consensus_certification | 15.36s |
| secondary | `gemini-3-flash-preview` | `messages` | `ukraine_peace_deal_signature` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `glm-5` | `messages` | `ipo_openai_bracket` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `glm-5` | `messages` | `weinstein_sentencing_bracket` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `glm-5` | `messages` | `mamdani_rent_freeze` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `glm-5` | `messages` | `canada_recession_dual_path` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `glm-5` | `messages` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `glm-5` | `messages` | `esports_odd_even_kills` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `glm-5` | `messages` | `balance_of_power_resolution` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `glm-5` | `messages` | `ukraine_peace_deal_signature` | 0.00 | 0/0 | no | HTTP 554:  | 0.00s |
| secondary | `glm-5` | `chat_stream_plain` | `ipo_openai_bracket` | 0.71 | 5/7 | no | threshold_lt_500b, interruption_next_trading_day | 28.01s |
| secondary | `glm-5` | `chat_stream_plain` | `weinstein_sentencing_bracket` | 0.88 | 7/8 | yes | concurrent_consecutive_total | 84.51s |
| secondary | `glm-5` | `chat_stream_plain` | `mamdani_rent_freeze` | 0.89 | 8/9 | yes | both_conditions | 98.66s |
| secondary | `glm-5` | `chat_stream_plain` | `canada_recession_dual_path` | 0.00 | 0/7 | no | cd_howe_path, announcement_deadline, statcan_two_quarters, negative_gdp_threshold, concurrent_vintages, stay_open_q4, sources | 51.26s |
| secondary | `glm-5` | `chat_stream_plain` | `gpt6_before_gta_vi` | 1.00 | 9/9 | no |  | 66.96s |
| secondary | `glm-5` | `chat_stream_plain` | `esports_odd_even_kills` | 0.89 | 8/9 | yes | odd_even_game2 | 82.18s |
| secondary | `glm-5` | `chat_stream_plain` | `balance_of_power_resolution` | 0.00 | 0/7 | no | house_control, senate_control, candidate_party, house_ambiguity_speaker, senate_ambiguity_majority_leader, three_sources, no_consensus_certification | 44.77s |
| secondary | `glm-5` | `chat_stream_plain` | `ukraine_peace_deal_signature` | 0.89 | 8/9 | no | written_instrument | 32.33s |

## 3. 解释

- 这个实验比 endpoint-format benchmark 更严格：必须命中人工标注的真实复杂 resolution 规则。
- `pass recall` 表示某模型在多少个 case 上达到该 case 的最低语义召回阈值，同时 schema 和 grounding 合格。
- `perfect` 表示该 case 的人工 golden requirements 全部命中；这是最严格排序的第一优先级。
- 真实自动套利系统应优先选择 `perfect`、`pass recall`、`min recall` 更高的模型，而不是只看 latency。

## 4. 数据归档

- per-call NDJSON: `data/experiments/2026-05-13/llm-complex-recognition-secondary-candidates-strict-v2.ndjson`
- rows: 96

---
*Snapshot: 2026-05-13T03:12:28.097774+00:00*