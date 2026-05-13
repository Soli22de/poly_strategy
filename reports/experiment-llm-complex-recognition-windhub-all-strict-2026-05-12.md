# LLM 复杂场景识别能力实验报告（2026-05-12T17:35:42.425027+00:00）

## 1. 总体排名

| rank | provider | model | format | cases | success | schema | grounding | pass recall | avg recall | min recall | median latency | first error |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | windhub | `doubao-seed-1-8-251228` | `messages` | 8 | 8 | 8 | 8 | 7 / perfect 6 | 0.95 | 0.71 | 76.47s |  |
| 2 | windhub | `doubao-seed-2-0-lite-260428` | `messages` | 8 | 8 | 8 | 8 | 8 / perfect 5 | 0.95 | 0.86 | 77.05s |  |
| 3 | windhub | `deepseek-v3-2-251201` | `responses` | 8 | 8 | 8 | 7 | 7 / perfect 4 | 0.94 | 0.86 | 35.61s |  |
| 4 | windhub | `doubao-seed-2-0-lite-260428` | `responses` | 8 | 7 | 5 | 5 | 4 / perfect 4 | 0.67 | 0.00 | 79.70s | TimeoutError: The read operation timed out |
| 5 | windhub | `deepseek-v3-2-251201` | `messages` | 8 | 8 | 8 | 8 | 8 / perfect 3 | 0.91 | 0.75 | 44.28s |  |
| 6 | windhub | `doubao-seed-1-6-251015` | `messages` | 8 | 7 | 7 | 7 | 6 / perfect 3 | 0.91 | 0.71 | 83.52s | TimeoutError: The read operation timed out |
| 7 | windhub | `deepseek-v3-2-251201` | `chat` | 8 | 8 | 8 | 7 | 7 / perfect 2 | 0.91 | 0.78 | 31.26s |  |
| 8 | windhub | `doubao-seed-1-8-251228` | `chat` | 8 | 4 | 4 | 4 | 4 / perfect 2 | 0.94 | 0.86 | 98.06s | TimeoutError: The read operation timed out |
| 9 | windhub | `doubao-seed-1-6-251015` | `chat` | 8 | 6 | 6 | 5 | 3 / perfect 1 | 0.80 | 0.62 | 85.54s | TimeoutError: The read operation timed out |
| 10 | windhub | `doubao-seed-1-8-251228` | `responses` | 8 | 8 | 1 | 1 | 1 / perfect 1 | 0.12 | 0.00 | 81.94s |  |
| 11 | windhub | `doubao-1-5-pro-32k-250115` | `chat` | 8 | 8 | 8 | 2 | 2 / perfect 0 | 0.87 | 0.78 | 30.66s |  |
| 12 | windhub | `doubao-1-5-pro-32k-250115` | `messages` | 8 | 8 | 8 | 2 | 2 / perfect 0 | 0.83 | 0.67 | 29.12s |  |
| 13 | windhub | `glm-5.1` | `chat` | 8 | 2 | 2 | 0 | 0 / perfect 0 | 0.87 | 0.86 | 60.80s | TimeoutError: The read operation timed out |
| 14 | windhub | `doubao-seed-1-6-251015` | `responses` | 8 | 2 | 1 | 0 | 0 / perfect 0 | 0.38 | 0.00 | 90.12s | TimeoutError: The read operation timed out |
| 15 | windhub | `doubao-seedream-4-5-251128` | `chat` | 8 | 8 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 24.10s |  |
| 16 | windhub | `mimo-v2.5` | `messages` | 8 | 8 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 27.33s |  |
| 17 | windhub | `mimo-v2.5` | `chat` | 8 | 8 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 28.31s |  |
| 18 | windhub | `kimi-k2.6` | `messages` | 8 | 4 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 27.68s | TimeoutError: The read operation timed out |
| 19 | windhub | `kimi-k2.6` | `chat` | 8 | 4 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 28.42s | TimeoutError: The read operation timed out |
| 20 | windhub | `doubao-1-5-pro-32k-250115` | `responses` | 8 | 0 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 0.00s | HTTP 403: {"error":{"message":"The request failed because model `doubao-1-5-pro-32k-250115` does not |
| 21 | windhub | `doubao-seed-2-0-lite-260428` | `chat` | 8 | 0 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 0.00s | HTTP 400: {"error":{"message":"The parameter `response_format.type` specified in the request are not |
| 22 | windhub | `doubao-seedream-4-5-251128` | `messages` | 8 | 0 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 0.00s | HTTP 500: {"error":{"type":"new_api_error","message":"not implemented (request id: 20260512183700215 |
| 23 | windhub | `doubao-seedream-4-5-251128` | `responses` | 8 | 0 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 0.00s | HTTP 500: {"error":{"message":"not implemented (request id: 202605121837033390325312kKTdXhq)","type" |
| 24 | windhub | `glm-5.1` | `messages` | 8 | 0 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 0.00s | TimeoutError: The read operation timed out |
| 25 | windhub | `glm-5.1` | `responses` | 8 | 0 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 0.00s | HTTP 404: {"error":{"message":"openai_error","type":"bad_response_status_code","param":"","code":"ba |
| 26 | windhub | `kimi-k2.6` | `responses` | 8 | 0 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 0.00s | HTTP 404: {"error":{"message":"openai_error","type":"bad_response_status_code","param":"","code":"ba |
| 27 | windhub | `mimo-v2.5` | `responses` | 8 | 0 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 0.00s | HTTP 500: {"error":{"message":"not implemented (request id: 20260512190558929079309msjkUESB)","type" |
| 28 | windhub | `mimo-v2.5-pro` | `chat` | 8 | 0 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 0.00s | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloud |
| 29 | windhub | `mimo-v2.5-pro` | `messages` | 8 | 0 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 0.00s | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloud |
| 30 | windhub | `mimo-v2.5-pro` | `responses` | 8 | 0 | 0 | 0 | 0 / perfect 0 | 0.00 | 0.00 | 0.00s | HTTP 500: {"error":{"message":"not implemented (request id: 20260512191805663486407rGaSfdbN)","type" |

## 2. 按 case 明细

| provider | model | format | case | recall | met/total | pass | missed | latency |
|---|---|---|---|---:|---:|---|---|---:|
| windhub | `deepseek-v3-2-251201` | `chat` | `ipo_openai_bracket` | 1.00 | 7/7 | yes |  | 28.56s |
| windhub | `deepseek-v3-2-251201` | `chat` | `weinstein_sentencing_bracket` | 0.88 | 7/8 | yes | threshold_less_than_5 | 28.89s |
| windhub | `deepseek-v3-2-251201` | `chat` | `canada_recession_dual_path` | 0.86 | 6/7 | yes | statcan_two_quarters | 34.42s |
| windhub | `deepseek-v3-2-251201` | `chat` | `mamdani_rent_freeze` | 0.89 | 8/9 | yes | both_conditions | 37.12s |
| windhub | `deepseek-v3-2-251201` | `chat` | `esports_odd_even_kills` | 0.78 | 7/9 | yes | odd_even_game2, champion_kills_include | 31.20s |
| windhub | `deepseek-v3-2-251201` | `chat` | `gpt6_before_gta_vi` | 1.00 | 9/9 | yes |  | 38.06s |
| windhub | `deepseek-v3-2-251201` | `chat` | `balance_of_power_resolution` | 1.00 | 7/7 | no |  | 31.32s |
| windhub | `deepseek-v3-2-251201` | `chat` | `ukraine_peace_deal_signature` | 0.89 | 8/9 | yes | written_instrument | 27.38s |
| windhub | `deepseek-v3-2-251201` | `messages` | `weinstein_sentencing_bracket` | 0.75 | 6/8 | yes | threshold_less_than_5, concurrent_consecutive_total | 38.60s |
| windhub | `deepseek-v3-2-251201` | `messages` | `ipo_openai_bracket` | 0.86 | 6/7 | yes | interruption_next_trading_day | 39.18s |
| windhub | `deepseek-v3-2-251201` | `messages` | `canada_recession_dual_path` | 1.00 | 7/7 | yes |  | 46.31s |
| windhub | `deepseek-v3-2-251201` | `messages` | `mamdani_rent_freeze` | 0.89 | 8/9 | yes | both_conditions | 55.68s |
| windhub | `deepseek-v3-2-251201` | `messages` | `esports_odd_even_kills` | 0.89 | 8/9 | yes | odd_even_game2 | 42.34s |
| windhub | `deepseek-v3-2-251201` | `messages` | `gpt6_before_gta_vi` | 1.00 | 9/9 | yes |  | 54.34s |
| windhub | `deepseek-v3-2-251201` | `messages` | `ukraine_peace_deal_signature` | 0.89 | 8/9 | yes | written_instrument | 38.61s |
| windhub | `deepseek-v3-2-251201` | `messages` | `balance_of_power_resolution` | 1.00 | 7/7 | yes |  | 46.22s |
| windhub | `deepseek-v3-2-251201` | `responses` | `ipo_openai_bracket` | 0.86 | 6/7 | no | interruption_next_trading_day | 28.15s |
| windhub | `deepseek-v3-2-251201` | `responses` | `weinstein_sentencing_bracket` | 0.88 | 7/8 | yes | threshold_less_than_5 | 27.76s |
| windhub | `deepseek-v3-2-251201` | `responses` | `mamdani_rent_freeze` | 0.89 | 8/9 | yes | both_conditions | 39.74s |
| windhub | `deepseek-v3-2-251201` | `responses` | `canada_recession_dual_path` | 1.00 | 7/7 | yes |  | 38.18s |
| windhub | `deepseek-v3-2-251201` | `responses` | `esports_odd_even_kills` | 0.89 | 8/9 | yes | odd_even_game2 | 31.19s |
| windhub | `deepseek-v3-2-251201` | `responses` | `gpt6_before_gta_vi` | 1.00 | 9/9 | yes |  | 50.89s |
| windhub | `deepseek-v3-2-251201` | `responses` | `balance_of_power_resolution` | 1.00 | 7/7 | yes |  | 33.03s |
| windhub | `doubao-1-5-pro-32k-250115` | `chat` | `ipo_openai_bracket` | 0.86 | 6/7 | no | threshold_lt_500b | 22.83s |
| windhub | `deepseek-v3-2-251201` | `responses` | `ukraine_peace_deal_signature` | 1.00 | 9/9 | yes |  | 41.90s |
| windhub | `doubao-1-5-pro-32k-250115` | `chat` | `weinstein_sentencing_bracket` | 0.88 | 7/8 | yes | threshold_less_than_5 | 29.25s |
| windhub | `doubao-1-5-pro-32k-250115` | `chat` | `mamdani_rent_freeze` | 0.89 | 8/9 | no | zero_percent_both_terms | 43.67s |
| windhub | `doubao-1-5-pro-32k-250115` | `chat` | `canada_recession_dual_path` | 1.00 | 7/7 | no |  | 32.08s |
| windhub | `doubao-1-5-pro-32k-250115` | `chat` | `gpt6_before_gta_vi` | 0.78 | 7/9 | no | gta_source, gpt55_not_count | 32.16s |
| windhub | `doubao-1-5-pro-32k-250115` | `chat` | `esports_odd_even_kills` | 0.89 | 8/9 | yes | odd_even_game2 | 33.35s |
| windhub | `doubao-1-5-pro-32k-250115` | `chat` | `balance_of_power_resolution` | 0.86 | 6/7 | no | candidate_party | 27.31s |
| windhub | `doubao-1-5-pro-32k-250115` | `chat` | `ukraine_peace_deal_signature` | 0.78 | 7/9 | no | issue_specific_not, wet_ink_e_signature | 24.56s |
| windhub | `doubao-1-5-pro-32k-250115` | `messages` | `ipo_openai_bracket` | 0.86 | 6/7 | no | threshold_lt_500b | 19.83s |
| windhub | `doubao-1-5-pro-32k-250115` | `messages` | `weinstein_sentencing_bracket` | 0.88 | 7/8 | yes | threshold_less_than_5 | 24.89s |
| windhub | `doubao-1-5-pro-32k-250115` | `messages` | `mamdani_rent_freeze` | 0.89 | 8/9 | no | zero_percent_both_terms | 28.56s |
| windhub | `doubao-1-5-pro-32k-250115` | `messages` | `canada_recession_dual_path` | 0.86 | 6/7 | no | concurrent_vintages | 35.95s |
| windhub | `doubao-1-5-pro-32k-250115` | `messages` | `gpt6_before_gta_vi` | 0.67 | 6/9 | no | neither_50_50, gta_source, gpt55_not_count | 31.99s |
| windhub | `doubao-1-5-pro-32k-250115` | `messages` | `esports_odd_even_kills` | 0.89 | 8/9 | yes | odd_even_game2 | 29.67s |
| windhub | `doubao-1-5-pro-32k-250115` | `messages` | `balance_of_power_resolution` | 0.86 | 6/7 | no | candidate_party | 33.34s |
| windhub | `doubao-1-5-pro-32k-250115` | `responses` | `ipo_openai_bracket` | 0.00 | 0/0 | no | HTTP 403: {"error":{"message":"The request failed because model `doubao-1-5-pro-32k-250115` does not have access to responses api Request id | 0.00s |
| windhub | `doubao-1-5-pro-32k-250115` | `responses` | `weinstein_sentencing_bracket` | 0.00 | 0/0 | no | HTTP 403: {"error":{"message":"The request failed because model `doubao-1-5-pro-32k-250115` does not have access to responses api Request id | 0.00s |
| windhub | `doubao-1-5-pro-32k-250115` | `responses` | `mamdani_rent_freeze` | 0.00 | 0/0 | no | HTTP 403: {"error":{"message":"The request failed because model `doubao-1-5-pro-32k-250115` does not have access to responses api Request id | 0.00s |
| windhub | `doubao-1-5-pro-32k-250115` | `responses` | `canada_recession_dual_path` | 0.00 | 0/0 | no | HTTP 403: {"error":{"message":"The request failed because model `doubao-1-5-pro-32k-250115` does not have access to responses api Request id | 0.00s |
| windhub | `doubao-1-5-pro-32k-250115` | `responses` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | HTTP 403: {"error":{"message":"The request failed because model `doubao-1-5-pro-32k-250115` does not have access to responses api Request id | 0.00s |
| windhub | `doubao-1-5-pro-32k-250115` | `responses` | `esports_odd_even_kills` | 0.00 | 0/0 | no | HTTP 403: {"error":{"message":"The request failed because model `doubao-1-5-pro-32k-250115` does not have access to responses api Request id | 0.00s |
| windhub | `doubao-1-5-pro-32k-250115` | `responses` | `balance_of_power_resolution` | 0.00 | 0/0 | no | HTTP 403: {"error":{"message":"The request failed because model `doubao-1-5-pro-32k-250115` does not have access to responses api Request id | 0.00s |
| windhub | `doubao-1-5-pro-32k-250115` | `responses` | `ukraine_peace_deal_signature` | 0.00 | 0/0 | no | HTTP 403: {"error":{"message":"The request failed because model `doubao-1-5-pro-32k-250115` does not have access to responses api Request id | 0.00s |
| windhub | `doubao-1-5-pro-32k-250115` | `messages` | `ukraine_peace_deal_signature` | 0.78 | 7/9 | no | issue_specific_not, wet_ink_e_signature | 22.30s |
| windhub | `doubao-seed-1-6-251015` | `chat` | `ipo_openai_bracket` | 0.86 | 6/7 | yes | threshold_lt_500b | 80.77s |
| windhub | `doubao-seed-1-6-251015` | `chat` | `weinstein_sentencing_bracket` | 0.62 | 5/8 | no | threshold_less_than_5, higher_range_tiebreaker, concurrent_consecutive_total | 80.94s |
| windhub | `doubao-seed-1-6-251015` | `chat` | `mamdani_rent_freeze` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `doubao-seed-1-6-251015` | `chat` | `canada_recession_dual_path` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `doubao-seed-1-6-251015` | `chat` | `gpt6_before_gta_vi` | 0.78 | 7/9 | no | gpt55_not_count, openai_source | 71.18s |
| windhub | `doubao-seed-1-6-251015` | `chat` | `esports_odd_even_kills` | 0.67 | 6/9 | no | odd_even_game2, canceled_delay_50_50, series_already_determined | 96.90s |
| windhub | `doubao-seed-1-6-251015` | `chat` | `balance_of_power_resolution` | 1.00 | 7/7 | yes |  | 90.14s |
| windhub | `doubao-seed-1-6-251015` | `chat` | `ukraine_peace_deal_signature` | 0.89 | 8/9 | yes | unsigned_not | 102.04s |
| windhub | `doubao-seed-1-6-251015` | `messages` | `ipo_openai_bracket` | 0.71 | 5/7 | no | threshold_lt_500b, interruption_next_trading_day | 72.59s |
| windhub | `doubao-seed-1-6-251015` | `messages` | `weinstein_sentencing_bracket` | 0.88 | 7/8 | yes | threshold_less_than_5 | 83.52s |
| windhub | `doubao-seed-1-6-251015` | `messages` | `mamdani_rent_freeze` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `doubao-seed-1-6-251015` | `messages` | `canada_recession_dual_path` | 1.00 | 7/7 | yes |  | 79.76s |
| windhub | `doubao-seed-1-6-251015` | `messages` | `esports_odd_even_kills` | 0.89 | 8/9 | yes | odd_even_game2 | 70.64s |
| windhub | `doubao-seed-1-6-251015` | `messages` | `gpt6_before_gta_vi` | 1.00 | 9/9 | yes |  | 110.05s |
| windhub | `doubao-seed-1-6-251015` | `messages` | `balance_of_power_resolution` | 1.00 | 7/7 | yes |  | 101.50s |
| windhub | `doubao-seed-1-6-251015` | `messages` | `ukraine_peace_deal_signature` | 0.89 | 8/9 | yes | written_instrument | 86.35s |
| windhub | `doubao-seed-1-6-251015` | `responses` | `weinstein_sentencing_bracket` | 0.75 | 6/8 | no | threshold_less_than_5, deadline | 64.22s |
| windhub | `doubao-seed-1-6-251015` | `responses` | `ipo_openai_bracket` | 0.00 | 0/7 | no | threshold_lt_500b, no_ipo_deadline, no_ipo_fallback, market_cap_calculation, bracket_tiebreaker, primary_exchange_source, interruption_next_trading_day | 116.02s |
| windhub | `doubao-seed-1-6-251015` | `responses` | `mamdani_rent_freeze` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `doubao-seed-1-6-251015` | `responses` | `canada_recession_dual_path` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `doubao-seed-1-6-251015` | `responses` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `doubao-seed-1-6-251015` | `responses` | `esports_odd_even_kills` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `doubao-seed-1-6-251015` | `responses` | `balance_of_power_resolution` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `doubao-seed-1-6-251015` | `responses` | `ukraine_peace_deal_signature` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `doubao-seed-1-8-251228` | `chat` | `ipo_openai_bracket` | 0.86 | 6/7 | yes | interruption_next_trading_day | 71.91s |
| windhub | `doubao-seed-1-8-251228` | `chat` | `weinstein_sentencing_bracket` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `doubao-seed-1-8-251228` | `chat` | `mamdani_rent_freeze` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `doubao-seed-1-8-251228` | `chat` | `canada_recession_dual_path` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `doubao-seed-1-8-251228` | `chat` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `doubao-seed-1-8-251228` | `chat` | `esports_odd_even_kills` | 0.89 | 8/9 | yes | odd_even_game2 | 88.92s |
| windhub | `doubao-seed-1-8-251228` | `chat` | `balance_of_power_resolution` | 1.00 | 7/7 | yes |  | 109.75s |
| windhub | `doubao-seed-1-8-251228` | `chat` | `ukraine_peace_deal_signature` | 1.00 | 9/9 | yes |  | 107.19s |
| windhub | `doubao-seed-1-8-251228` | `messages` | `ipo_openai_bracket` | 0.71 | 5/7 | no | threshold_lt_500b, interruption_next_trading_day | 79.41s |
| windhub | `doubao-seed-1-8-251228` | `messages` | `weinstein_sentencing_bracket` | 0.88 | 7/8 | yes | threshold_less_than_5 | 85.58s |
| windhub | `doubao-seed-1-8-251228` | `messages` | `mamdani_rent_freeze` | 1.00 | 9/9 | yes |  | 85.41s |
| windhub | `doubao-seed-1-8-251228` | `messages` | `canada_recession_dual_path` | 1.00 | 7/7 | yes |  | 73.54s |
| windhub | `doubao-seed-1-8-251228` | `messages` | `gpt6_before_gta_vi` | 1.00 | 9/9 | yes |  | 109.16s |
| windhub | `doubao-seed-1-8-251228` | `messages` | `esports_odd_even_kills` | 1.00 | 9/9 | yes |  | 61.66s |
| windhub | `doubao-seed-1-8-251228` | `messages` | `ukraine_peace_deal_signature` | 1.00 | 9/9 | yes |  | 40.17s |
| windhub | `doubao-seed-1-8-251228` | `messages` | `balance_of_power_resolution` | 1.00 | 7/7 | yes |  | 55.16s |
| windhub | `doubao-seed-1-8-251228` | `responses` | `weinstein_sentencing_bracket` | 0.00 | 0/8 | no | threshold_less_than_5, deadline, first_sentence_no_appeals, not_guilty_mistrial_no_prison, no_sentencing_fallback, higher_range_tiebreaker, concurrent_consecutive_total, ny_court_source | 79.30s |
| windhub | `doubao-seed-1-8-251228` | `responses` | `ipo_openai_bracket` | 0.00 | 0/7 | no | threshold_lt_500b, no_ipo_deadline, no_ipo_fallback, market_cap_calculation, bracket_tiebreaker, primary_exchange_source, interruption_next_trading_day | 89.69s |
| windhub | `doubao-seed-1-8-251228` | `responses` | `canada_recession_dual_path` | 1.00 | 7/7 | yes |  | 83.66s |
| windhub | `doubao-seed-1-8-251228` | `responses` | `mamdani_rent_freeze` | 0.00 | 0/9 | no | both_conditions, zero_percent_both_terms, deadline, announcement_not_qualify, blocked_not_qualify, other_mechanism_qualifies, one_term_specific_units_not_qualify, loss_immediate_no | 99.42s |
| windhub | `doubao-seed-1-8-251228` | `responses` | `gpt6_before_gta_vi` | 0.00 | 0/9 | no | race_condition, neither_50_50, gta_exclusions, console_counts, gta_source, gpt_public_access, closed_private_not, gpt55_not_count | 80.21s |
| windhub | `doubao-seed-1-8-251228` | `responses` | `esports_odd_even_kills` | 0.00 | 0/9 | no | odd_even_game2, champion_kills_include, executions_exclude, no_kills_50_50, canceled_delay_50_50, forfeit_walkover_50_50, series_already_determined, remade_game_only | 74.75s |
| windhub | `doubao-seed-1-8-251228` | `responses` | `balance_of_power_resolution` | 0.00 | 0/7 | no | house_control, senate_control, candidate_party, house_ambiguity_speaker, senate_ambiguity_majority_leader, three_sources, no_consensus_certification | 77.46s |
| windhub | `doubao-seed-2-0-lite-260428` | `chat` | `ipo_openai_bracket` | 0.00 | 0/0 | no | HTTP 400: {"error":{"message":"The parameter `response_format.type` specified in the request are not valid: `json_object` is not supported b | 0.00s |
| windhub | `doubao-seed-2-0-lite-260428` | `chat` | `weinstein_sentencing_bracket` | 0.00 | 0/0 | no | HTTP 400: {"error":{"message":"The parameter `response_format.type` specified in the request are not valid: `json_object` is not supported b | 0.00s |
| windhub | `doubao-seed-2-0-lite-260428` | `chat` | `mamdani_rent_freeze` | 0.00 | 0/0 | no | HTTP 400: {"error":{"message":"The parameter `response_format.type` specified in the request are not valid: `json_object` is not supported b | 0.00s |
| windhub | `doubao-seed-2-0-lite-260428` | `chat` | `canada_recession_dual_path` | 0.00 | 0/0 | no | HTTP 400: {"error":{"message":"The parameter `response_format.type` specified in the request are not valid: `json_object` is not supported b | 0.00s |
| windhub | `doubao-seed-2-0-lite-260428` | `chat` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | HTTP 400: {"error":{"message":"The parameter `response_format.type` specified in the request are not valid: `json_object` is not supported b | 0.00s |
| windhub | `doubao-seed-2-0-lite-260428` | `chat` | `esports_odd_even_kills` | 0.00 | 0/0 | no | HTTP 400: {"error":{"message":"The parameter `response_format.type` specified in the request are not valid: `json_object` is not supported b | 0.00s |
| windhub | `doubao-seed-2-0-lite-260428` | `chat` | `balance_of_power_resolution` | 0.00 | 0/0 | no | HTTP 400: {"error":{"message":"The parameter `response_format.type` specified in the request are not valid: `json_object` is not supported b | 0.00s |
| windhub | `doubao-seed-2-0-lite-260428` | `chat` | `ukraine_peace_deal_signature` | 0.00 | 0/0 | no | HTTP 400: {"error":{"message":"The parameter `response_format.type` specified in the request are not valid: `json_object` is not supported b | 0.00s |
| windhub | `doubao-seed-1-8-251228` | `responses` | `ukraine_peace_deal_signature` | 0.00 | 0/9 | no | written_instrument, ceasefire_or_defined_process, deadline, ukraine_signature_only, localized_not_qualify, issue_specific_not, wet_ink_e_signature, unsigned_not | 85.58s |
| windhub | `doubao-seed-2-0-lite-260428` | `messages` | `ipo_openai_bracket` | 0.86 | 6/7 | yes | interruption_next_trading_day | 76.00s |
| windhub | `doubao-seed-2-0-lite-260428` | `messages` | `weinstein_sentencing_bracket` | 0.88 | 7/8 | yes | threshold_less_than_5 | 74.94s |
| windhub | `doubao-seed-2-0-lite-260428` | `messages` | `mamdani_rent_freeze` | 0.89 | 8/9 | yes | both_conditions | 82.87s |
| windhub | `doubao-seed-2-0-lite-260428` | `messages` | `canada_recession_dual_path` | 1.00 | 7/7 | yes |  | 78.10s |
| windhub | `doubao-seed-2-0-lite-260428` | `messages` | `gpt6_before_gta_vi` | 1.00 | 9/9 | yes |  | 86.50s |
| windhub | `doubao-seed-2-0-lite-260428` | `messages` | `esports_odd_even_kills` | 1.00 | 9/9 | yes |  | 87.42s |
| windhub | `doubao-seed-2-0-lite-260428` | `messages` | `ukraine_peace_deal_signature` | 1.00 | 9/9 | yes |  | 50.48s |
| windhub | `doubao-seed-2-0-lite-260428` | `messages` | `balance_of_power_resolution` | 1.00 | 7/7 | yes |  | 75.67s |
| windhub | `doubao-seed-2-0-lite-260428` | `responses` | `ipo_openai_bracket` | 0.71 | 5/7 | no | threshold_lt_500b, interruption_next_trading_day | 71.27s |
| windhub | `doubao-seed-2-0-lite-260428` | `responses` | `weinstein_sentencing_bracket` | 1.00 | 8/8 | yes |  | 61.30s |
| windhub | `doubao-seed-2-0-lite-260428` | `responses` | `mamdani_rent_freeze` | 0.00 | 0/9 | no | both_conditions, zero_percent_both_terms, deadline, announcement_not_qualify, blocked_not_qualify, other_mechanism_qualifies, one_term_specific_units_not_qualify, loss_immediate_no | 87.36s |
| windhub | `doubao-seed-2-0-lite-260428` | `responses` | `canada_recession_dual_path` | 1.00 | 7/7 | yes |  | 85.20s |
| windhub | `doubao-seed-2-0-lite-260428` | `responses` | `gpt6_before_gta_vi` | 0.00 | 0/9 | no | race_condition, neither_50_50, gta_exclusions, console_counts, gta_source, gpt_public_access, closed_private_not, gpt55_not_count | 79.70s |
| windhub | `doubao-seed-2-0-lite-260428` | `responses` | `esports_odd_even_kills` | 1.00 | 9/9 | yes |  | 74.46s |
| windhub | `doubao-seed-2-0-lite-260428` | `responses` | `balance_of_power_resolution` | 1.00 | 7/7 | yes |  | 80.95s |
| windhub | `doubao-seedream-4-5-251128` | `chat` | `ipo_openai_bracket` | 0.00 | 0/7 | no | threshold_lt_500b, no_ipo_deadline, no_ipo_fallback, market_cap_calculation, bracket_tiebreaker, primary_exchange_source, interruption_next_trading_day | 24.07s |
| windhub | `doubao-seed-2-0-lite-260428` | `responses` | `ukraine_peace_deal_signature` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `doubao-seedream-4-5-251128` | `chat` | `weinstein_sentencing_bracket` | 0.00 | 0/8 | no | threshold_less_than_5, deadline, first_sentence_no_appeals, not_guilty_mistrial_no_prison, no_sentencing_fallback, higher_range_tiebreaker, concurrent_consecutive_total, ny_court_source | 22.73s |
| windhub | `doubao-seedream-4-5-251128` | `chat` | `mamdani_rent_freeze` | 0.00 | 0/9 | no | both_conditions, zero_percent_both_terms, deadline, announcement_not_qualify, blocked_not_qualify, other_mechanism_qualifies, one_term_specific_units_not_qualify, loss_immediate_no | 23.74s |
| windhub | `doubao-seedream-4-5-251128` | `chat` | `canada_recession_dual_path` | 0.00 | 0/7 | no | cd_howe_path, announcement_deadline, statcan_two_quarters, negative_gdp_threshold, concurrent_vintages, stay_open_q4, sources | 25.91s |
| windhub | `doubao-seedream-4-5-251128` | `chat` | `gpt6_before_gta_vi` | 0.00 | 0/9 | no | race_condition, neither_50_50, gta_exclusions, console_counts, gta_source, gpt_public_access, closed_private_not, gpt55_not_count | 24.14s |
| windhub | `doubao-seedream-4-5-251128` | `chat` | `esports_odd_even_kills` | 0.00 | 0/9 | no | odd_even_game2, champion_kills_include, executions_exclude, no_kills_50_50, canceled_delay_50_50, forfeit_walkover_50_50, series_already_determined, remade_game_only | 21.12s |
| windhub | `doubao-seedream-4-5-251128` | `chat` | `balance_of_power_resolution` | 0.00 | 0/7 | no | house_control, senate_control, candidate_party, house_ambiguity_speaker, senate_ambiguity_majority_leader, three_sources, no_consensus_certification | 24.63s |
| windhub | `doubao-seedream-4-5-251128` | `messages` | `ipo_openai_bracket` | 0.00 | 0/0 | no | HTTP 500: {"error":{"type":"new_api_error","message":"not implemented (request id: 20260512183700215224010Gdx6XbHv)"},"type":"error"} | 0.00s |
| windhub | `doubao-seedream-4-5-251128` | `messages` | `weinstein_sentencing_bracket` | 0.00 | 0/0 | no | HTTP 500: {"error":{"type":"new_api_error","message":"not implemented (request id: 20260512183700619555798ngiCUobH)"},"type":"error"} | 0.00s |
| windhub | `doubao-seedream-4-5-251128` | `messages` | `mamdani_rent_freeze` | 0.00 | 0/0 | no | HTTP 500: {"error":{"type":"new_api_error","message":"not implemented (request id: 2026051218370122768090cln2JuOX)"},"type":"error"} | 0.00s |
| windhub | `doubao-seedream-4-5-251128` | `messages` | `canada_recession_dual_path` | 0.00 | 0/0 | no | HTTP 500: {"error":{"type":"new_api_error","message":"not implemented (request id: 20260512183701518037209YAt0QzHt)"},"type":"error"} | 0.00s |
| windhub | `doubao-seedream-4-5-251128` | `messages` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | HTTP 500: {"error":{"type":"new_api_error","message":"not implemented (request id: 20260512183701900822762hfsBudzO)"},"type":"error"} | 0.00s |
| windhub | `doubao-seedream-4-5-251128` | `messages` | `esports_odd_even_kills` | 0.00 | 0/0 | no | HTTP 500: {"error":{"type":"new_api_error","message":"not implemented (request id: 20260512183702233487878PfItrNzU)"},"type":"error"} | 0.00s |
| windhub | `doubao-seedream-4-5-251128` | `messages` | `balance_of_power_resolution` | 0.00 | 0/0 | no | HTTP 500: {"error":{"type":"new_api_error","message":"not implemented (request id: 202605121837025774302394CyHMPR5)"},"type":"error"} | 0.00s |
| windhub | `doubao-seedream-4-5-251128` | `messages` | `ukraine_peace_deal_signature` | 0.00 | 0/0 | no | HTTP 500: {"error":{"type":"new_api_error","message":"not implemented (request id: 20260512183702931575420xFgLDbEH)"},"type":"error"} | 0.00s |
| windhub | `doubao-seedream-4-5-251128` | `responses` | `ipo_openai_bracket` | 0.00 | 0/0 | no | HTTP 500: {"error":{"message":"not implemented (request id: 202605121837033390325312kKTdXhq)","type":"new_api_error","param":"","code":"conv | 0.00s |
| windhub | `doubao-seedream-4-5-251128` | `responses` | `weinstein_sentencing_bracket` | 0.00 | 0/0 | no | HTTP 500: {"error":{"message":"not implemented (request id: 202605121837039481780722WinF1Bl)","type":"new_api_error","param":"","code":"conv | 0.00s |
| windhub | `doubao-seedream-4-5-251128` | `responses` | `mamdani_rent_freeze` | 0.00 | 0/0 | no | HTTP 500: {"error":{"message":"not implemented (request id: 20260512183704374163729XuPYThf5)","type":"new_api_error","param":"","code":"conv | 0.00s |
| windhub | `doubao-seedream-4-5-251128` | `responses` | `canada_recession_dual_path` | 0.00 | 0/0 | no | HTTP 500: {"error":{"message":"not implemented (request id: 20260512183704814604321SRILbG3I)","type":"new_api_error","param":"","code":"conv | 0.00s |
| windhub | `doubao-seedream-4-5-251128` | `responses` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | HTTP 500: {"error":{"message":"not implemented (request id: 20260512183705169550891b8B4K7r8)","type":"new_api_error","param":"","code":"conv | 0.00s |
| windhub | `doubao-seedream-4-5-251128` | `responses` | `esports_odd_even_kills` | 0.00 | 0/0 | no | HTTP 500: {"error":{"message":"not implemented (request id: 202605121837056589723286YWvVHAD)","type":"new_api_error","param":"","code":"conv | 0.00s |
| windhub | `doubao-seedream-4-5-251128` | `responses` | `balance_of_power_resolution` | 0.00 | 0/0 | no | HTTP 500: {"error":{"message":"not implemented (request id: 2026051218370666635818IUhKe98M)","type":"new_api_error","param":"","code":"conve | 0.00s |
| windhub | `doubao-seedream-4-5-251128` | `responses` | `ukraine_peace_deal_signature` | 0.00 | 0/0 | no | HTTP 500: {"error":{"message":"not implemented (request id: 20260512183706450508025m5nbTNOV)","type":"new_api_error","param":"","code":"conv | 0.00s |
| windhub | `doubao-seedream-4-5-251128` | `chat` | `ukraine_peace_deal_signature` | 0.00 | 0/9 | no | written_instrument, ceasefire_or_defined_process, deadline, ukraine_signature_only, localized_not_qualify, issue_specific_not, wet_ink_e_signature, unsigned_not | 27.23s |
| windhub | `glm-5.1` | `chat` | `ipo_openai_bracket` | 0.86 | 6/7 | no | interruption_next_trading_day | 73.36s |
| windhub | `glm-5.1` | `chat` | `weinstein_sentencing_bracket` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `glm-5.1` | `chat` | `mamdani_rent_freeze` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `glm-5.1` | `chat` | `canada_recession_dual_path` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `glm-5.1` | `chat` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `glm-5.1` | `chat` | `esports_odd_even_kills` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `glm-5.1` | `chat` | `ukraine_peace_deal_signature` | 0.89 | 8/9 | no | written_instrument | 48.25s |
| windhub | `glm-5.1` | `chat` | `balance_of_power_resolution` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `glm-5.1` | `messages` | `ipo_openai_bracket` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `glm-5.1` | `messages` | `weinstein_sentencing_bracket` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `glm-5.1` | `messages` | `mamdani_rent_freeze` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `glm-5.1` | `messages` | `canada_recession_dual_path` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `glm-5.1` | `messages` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `glm-5.1` | `messages` | `esports_odd_even_kills` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `glm-5.1` | `messages` | `balance_of_power_resolution` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `glm-5.1` | `responses` | `ipo_openai_bracket` | 0.00 | 0/0 | no | HTTP 404: {"error":{"message":"openai_error","type":"bad_response_status_code","param":"","code":"bad_response_status_code"}} | 0.00s |
| windhub | `glm-5.1` | `responses` | `weinstein_sentencing_bracket` | 0.00 | 0/0 | no | HTTP 404: {"error":{"message":"openai_error","type":"bad_response_status_code","param":"","code":"bad_response_status_code"}} | 0.00s |
| windhub | `glm-5.1` | `responses` | `mamdani_rent_freeze` | 0.00 | 0/0 | no | HTTP 404: {"error":{"message":"openai_error","type":"bad_response_status_code","param":"","code":"bad_response_status_code"}} | 0.00s |
| windhub | `glm-5.1` | `responses` | `canada_recession_dual_path` | 0.00 | 0/0 | no | HTTP 404: {"error":{"message":"openai_error","type":"bad_response_status_code","param":"","code":"bad_response_status_code"}} | 0.00s |
| windhub | `glm-5.1` | `responses` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | HTTP 404: {"error":{"message":"openai_error","type":"bad_response_status_code","param":"","code":"bad_response_status_code"}} | 0.00s |
| windhub | `glm-5.1` | `responses` | `esports_odd_even_kills` | 0.00 | 0/0 | no | HTTP 404: {"error":{"message":"openai_error","type":"bad_response_status_code","param":"","code":"bad_response_status_code"}} | 0.00s |
| windhub | `glm-5.1` | `responses` | `balance_of_power_resolution` | 0.00 | 0/0 | no | HTTP 404: {"error":{"message":"openai_error","type":"bad_response_status_code","param":"","code":"bad_response_status_code"}} | 0.00s |
| windhub | `glm-5.1` | `responses` | `ukraine_peace_deal_signature` | 0.00 | 0/0 | no | HTTP 404: {"error":{"message":"openai_error","type":"bad_response_status_code","param":"","code":"bad_response_status_code"}} | 0.00s |
| windhub | `glm-5.1` | `messages` | `ukraine_peace_deal_signature` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `kimi-k2.6` | `chat` | `ipo_openai_bracket` | 0.00 | 0/7 | no | threshold_lt_500b, no_ipo_deadline, no_ipo_fallback, market_cap_calculation, bracket_tiebreaker, primary_exchange_source, interruption_next_trading_day | 28.40s |
| windhub | `kimi-k2.6` | `chat` | `weinstein_sentencing_bracket` | 0.00 | 0/8 | no | threshold_less_than_5, deadline, first_sentence_no_appeals, not_guilty_mistrial_no_prison, no_sentencing_fallback, higher_range_tiebreaker, concurrent_consecutive_total, ny_court_source | 28.45s |
| windhub | `kimi-k2.6` | `chat` | `canada_recession_dual_path` | 0.00 | 0/7 | no | cd_howe_path, announcement_deadline, statcan_two_quarters, negative_gdp_threshold, concurrent_vintages, stay_open_q4, sources | 27.90s |
| windhub | `kimi-k2.6` | `chat` | `mamdani_rent_freeze` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `kimi-k2.6` | `chat` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `kimi-k2.6` | `chat` | `esports_odd_even_kills` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `kimi-k2.6` | `chat` | `ukraine_peace_deal_signature` | 0.00 | 0/9 | no | written_instrument, ceasefire_or_defined_process, deadline, ukraine_signature_only, localized_not_qualify, issue_specific_not, wet_ink_e_signature, unsigned_not | 28.71s |
| windhub | `kimi-k2.6` | `chat` | `balance_of_power_resolution` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `kimi-k2.6` | `messages` | `weinstein_sentencing_bracket` | 0.00 | 0/8 | no | threshold_less_than_5, deadline, first_sentence_no_appeals, not_guilty_mistrial_no_prison, no_sentencing_fallback, higher_range_tiebreaker, concurrent_consecutive_total, ny_court_source | 27.44s |
| windhub | `kimi-k2.6` | `messages` | `ipo_openai_bracket` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `kimi-k2.6` | `messages` | `canada_recession_dual_path` | 0.00 | 0/7 | no | cd_howe_path, announcement_deadline, statcan_two_quarters, negative_gdp_threshold, concurrent_vintages, stay_open_q4, sources | 28.21s |
| windhub | `kimi-k2.6` | `messages` | `mamdani_rent_freeze` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `kimi-k2.6` | `messages` | `esports_odd_even_kills` | 0.00 | 0/9 | no | odd_even_game2, champion_kills_include, executions_exclude, no_kills_50_50, canceled_delay_50_50, forfeit_walkover_50_50, series_already_determined, remade_game_only | 27.87s |
| windhub | `kimi-k2.6` | `messages` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `kimi-k2.6` | `messages` | `ukraine_peace_deal_signature` | 0.00 | 0/9 | no | written_instrument, ceasefire_or_defined_process, deadline, ukraine_signature_only, localized_not_qualify, issue_specific_not, wet_ink_e_signature, unsigned_not | 27.48s |
| windhub | `kimi-k2.6` | `responses` | `ipo_openai_bracket` | 0.00 | 0/0 | no | HTTP 404: {"error":{"message":"openai_error","type":"bad_response_status_code","param":"","code":"bad_response_status_code"}} | 0.00s |
| windhub | `kimi-k2.6` | `responses` | `weinstein_sentencing_bracket` | 0.00 | 0/0 | no | HTTP 404: {"error":{"message":"openai_error","type":"bad_response_status_code","param":"","code":"bad_response_status_code"}} | 0.00s |
| windhub | `kimi-k2.6` | `responses` | `mamdani_rent_freeze` | 0.00 | 0/0 | no | HTTP 404: {"error":{"message":"openai_error","type":"bad_response_status_code","param":"","code":"bad_response_status_code"}} | 0.00s |
| windhub | `kimi-k2.6` | `responses` | `canada_recession_dual_path` | 0.00 | 0/0 | no | HTTP 404: {"error":{"message":"openai_error","type":"bad_response_status_code","param":"","code":"bad_response_status_code"}} | 0.00s |
| windhub | `kimi-k2.6` | `responses` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | HTTP 404: {"error":{"message":"openai_error","type":"bad_response_status_code","param":"","code":"bad_response_status_code"}} | 0.00s |
| windhub | `kimi-k2.6` | `responses` | `esports_odd_even_kills` | 0.00 | 0/0 | no | HTTP 404: {"error":{"message":"openai_error","type":"bad_response_status_code","param":"","code":"bad_response_status_code"}} | 0.00s |
| windhub | `kimi-k2.6` | `responses` | `balance_of_power_resolution` | 0.00 | 0/0 | no | HTTP 404: {"error":{"message":"openai_error","type":"bad_response_status_code","param":"","code":"bad_response_status_code"}} | 0.00s |
| windhub | `kimi-k2.6` | `responses` | `ukraine_peace_deal_signature` | 0.00 | 0/0 | no | HTTP 404: {"error":{"message":"openai_error","type":"bad_response_status_code","param":"","code":"bad_response_status_code"}} | 0.00s |
| windhub | `kimi-k2.6` | `messages` | `balance_of_power_resolution` | 0.00 | 0/0 | no | TimeoutError: The read operation timed out | 0.00s |
| windhub | `mimo-v2.5` | `chat` | `weinstein_sentencing_bracket` | 0.00 | 0/8 | no | threshold_less_than_5, deadline, first_sentence_no_appeals, not_guilty_mistrial_no_prison, no_sentencing_fallback, higher_range_tiebreaker, concurrent_consecutive_total, ny_court_source | 28.33s |
| windhub | `mimo-v2.5` | `chat` | `ipo_openai_bracket` | 0.00 | 0/7 | no | threshold_lt_500b, no_ipo_deadline, no_ipo_fallback, market_cap_calculation, bracket_tiebreaker, primary_exchange_source, interruption_next_trading_day | 57.18s |
| windhub | `mimo-v2.5` | `chat` | `mamdani_rent_freeze` | 0.00 | 0/9 | no | both_conditions, zero_percent_both_terms, deadline, announcement_not_qualify, blocked_not_qualify, other_mechanism_qualifies, one_term_specific_units_not_qualify, loss_immediate_no | 28.08s |
| windhub | `mimo-v2.5` | `chat` | `canada_recession_dual_path` | 0.00 | 0/7 | no | cd_howe_path, announcement_deadline, statcan_two_quarters, negative_gdp_threshold, concurrent_vintages, stay_open_q4, sources | 27.72s |
| windhub | `mimo-v2.5` | `chat` | `gpt6_before_gta_vi` | 0.00 | 0/9 | no | race_condition, neither_50_50, gta_exclusions, console_counts, gta_source, gpt_public_access, closed_private_not, gpt55_not_count | 28.29s |
| windhub | `mimo-v2.5` | `chat` | `esports_odd_even_kills` | 0.00 | 0/9 | no | odd_even_game2, champion_kills_include, executions_exclude, no_kills_50_50, canceled_delay_50_50, forfeit_walkover_50_50, series_already_determined, remade_game_only | 27.28s |
| windhub | `mimo-v2.5` | `chat` | `balance_of_power_resolution` | 0.00 | 0/7 | no | house_control, senate_control, candidate_party, house_ambiguity_speaker, senate_ambiguity_majority_leader, three_sources, no_consensus_certification | 30.33s |
| windhub | `mimo-v2.5` | `chat` | `ukraine_peace_deal_signature` | 0.00 | 0/9 | no | written_instrument, ceasefire_or_defined_process, deadline, ukraine_signature_only, localized_not_qualify, issue_specific_not, wet_ink_e_signature, unsigned_not | 29.33s |
| windhub | `mimo-v2.5` | `messages` | `ipo_openai_bracket` | 0.00 | 0/7 | no | threshold_lt_500b, no_ipo_deadline, no_ipo_fallback, market_cap_calculation, bracket_tiebreaker, primary_exchange_source, interruption_next_trading_day | 28.65s |
| windhub | `mimo-v2.5` | `messages` | `weinstein_sentencing_bracket` | 0.00 | 0/8 | no | threshold_less_than_5, deadline, first_sentence_no_appeals, not_guilty_mistrial_no_prison, no_sentencing_fallback, higher_range_tiebreaker, concurrent_consecutive_total, ny_court_source | 27.13s |
| windhub | `mimo-v2.5` | `messages` | `mamdani_rent_freeze` | 0.00 | 0/9 | no | both_conditions, zero_percent_both_terms, deadline, announcement_not_qualify, blocked_not_qualify, other_mechanism_qualifies, one_term_specific_units_not_qualify, loss_immediate_no | 25.67s |
| windhub | `mimo-v2.5` | `messages` | `canada_recession_dual_path` | 0.00 | 0/7 | no | cd_howe_path, announcement_deadline, statcan_two_quarters, negative_gdp_threshold, concurrent_vintages, stay_open_q4, sources | 27.20s |
| windhub | `mimo-v2.5` | `messages` | `gpt6_before_gta_vi` | 0.00 | 0/9 | no | race_condition, neither_50_50, gta_exclusions, console_counts, gta_source, gpt_public_access, closed_private_not, gpt55_not_count | 29.62s |
| windhub | `mimo-v2.5` | `messages` | `esports_odd_even_kills` | 0.00 | 0/9 | no | odd_even_game2, champion_kills_include, executions_exclude, no_kills_50_50, canceled_delay_50_50, forfeit_walkover_50_50, series_already_determined, remade_game_only | 28.80s |
| windhub | `mimo-v2.5` | `messages` | `balance_of_power_resolution` | 0.00 | 0/7 | no | house_control, senate_control, candidate_party, house_ambiguity_speaker, senate_ambiguity_majority_leader, three_sources, no_consensus_certification | 25.74s |
| windhub | `mimo-v2.5` | `responses` | `ipo_openai_bracket` | 0.00 | 0/0 | no | HTTP 500: {"error":{"message":"not implemented (request id: 20260512190558929079309msjkUESB)","type":"new_api_error","param":"","code":"conv | 0.00s |
| windhub | `mimo-v2.5` | `responses` | `weinstein_sentencing_bracket` | 0.00 | 0/0 | no | HTTP 500: {"error":{"message":"not implemented (request id: 20260512190559296876165qSFBk8gZ)","type":"new_api_error","param":"","code":"conv | 0.00s |
| windhub | `mimo-v2.5` | `responses` | `mamdani_rent_freeze` | 0.00 | 0/0 | no | HTTP 500: {"error":{"message":"not implemented (request id: 20260512190559790894757KOVjrvUs)","type":"new_api_error","param":"","code":"conv | 0.00s |
| windhub | `mimo-v2.5` | `responses` | `canada_recession_dual_path` | 0.00 | 0/0 | no | HTTP 500: {"error":{"message":"not implemented (request id: 20260512190600151989337F7L3qQGw)","type":"new_api_error","param":"","code":"conv | 0.00s |
| windhub | `mimo-v2.5` | `responses` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | HTTP 500: {"error":{"message":"not implemented (request id: 20260512190600532234354rdCUSHPY)","type":"new_api_error","param":"","code":"conv | 0.00s |
| windhub | `mimo-v2.5` | `responses` | `esports_odd_even_kills` | 0.00 | 0/0 | no | HTTP 500: {"error":{"message":"not implemented (request id: 20260512190600901741537mQHAhLmH)","type":"new_api_error","param":"","code":"conv | 0.00s |
| windhub | `mimo-v2.5` | `responses` | `balance_of_power_resolution` | 0.00 | 0/0 | no | HTTP 500: {"error":{"message":"not implemented (request id: 20260512190601255997168X083ZaSG)","type":"new_api_error","param":"","code":"conv | 0.00s |
| windhub | `mimo-v2.5` | `responses` | `ukraine_peace_deal_signature` | 0.00 | 0/0 | no | HTTP 500: {"error":{"message":"not implemented (request id: 20260512190601624390487g2C3ppWY)","type":"new_api_error","param":"","code":"conv | 0.00s |
| windhub | `mimo-v2.5` | `messages` | `ukraine_peace_deal_signature` | 0.00 | 0/9 | no | written_instrument, ceasefire_or_defined_process, deadline, ukraine_signature_only, localized_not_qualify, issue_specific_not, wet_ink_e_signature, unsigned_not | 27.46s |
| windhub | `mimo-v2.5-pro` | `chat` | `ipo_openai_bracket` | 0.00 | 0/0 | no | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-504/","title":"Er | 0.00s |
| windhub | `mimo-v2.5-pro` | `chat` | `weinstein_sentencing_bracket` | 0.00 | 0/0 | no | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-504/","title":"Er | 0.00s |
| windhub | `mimo-v2.5-pro` | `chat` | `mamdani_rent_freeze` | 0.00 | 0/0 | no | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-504/","title":"Er | 0.00s |
| windhub | `mimo-v2.5-pro` | `chat` | `canada_recession_dual_path` | 0.00 | 0/0 | no | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-504/","title":"Er | 0.00s |
| windhub | `mimo-v2.5-pro` | `chat` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-504/","title":"Er | 0.00s |
| windhub | `mimo-v2.5-pro` | `chat` | `esports_odd_even_kills` | 0.00 | 0/0 | no | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-504/","title":"Er | 0.00s |
| windhub | `mimo-v2.5-pro` | `chat` | `balance_of_power_resolution` | 0.00 | 0/0 | no | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-504/","title":"Er | 0.00s |
| windhub | `mimo-v2.5-pro` | `chat` | `ukraine_peace_deal_signature` | 0.00 | 0/0 | no | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-504/","title":"Er | 0.00s |
| windhub | `mimo-v2.5-pro` | `messages` | `ipo_openai_bracket` | 0.00 | 0/0 | no | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-504/","title":"Er | 0.00s |
| windhub | `mimo-v2.5-pro` | `messages` | `weinstein_sentencing_bracket` | 0.00 | 0/0 | no | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-504/","title":"Er | 0.00s |
| windhub | `mimo-v2.5-pro` | `messages` | `mamdani_rent_freeze` | 0.00 | 0/0 | no | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-504/","title":"Er | 0.00s |
| windhub | `mimo-v2.5-pro` | `messages` | `canada_recession_dual_path` | 0.00 | 0/0 | no | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-504/","title":"Er | 0.00s |
| windhub | `mimo-v2.5-pro` | `messages` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-504/","title":"Er | 0.00s |
| windhub | `mimo-v2.5-pro` | `messages` | `esports_odd_even_kills` | 0.00 | 0/0 | no | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-504/","title":"Er | 0.00s |
| windhub | `mimo-v2.5-pro` | `messages` | `balance_of_power_resolution` | 0.00 | 0/0 | no | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-504/","title":"Er | 0.00s |
| windhub | `mimo-v2.5-pro` | `responses` | `ipo_openai_bracket` | 0.00 | 0/0 | no | HTTP 500: {"error":{"message":"not implemented (request id: 20260512191805663486407rGaSfdbN)","type":"new_api_error","param":"","code":"conv | 0.00s |
| windhub | `mimo-v2.5-pro` | `responses` | `weinstein_sentencing_bracket` | 0.00 | 0/0 | no | HTTP 500: {"error":{"message":"not implemented (request id: 2026051219180625634189PXVvLzpy)","type":"new_api_error","param":"","code":"conve | 0.00s |
| windhub | `mimo-v2.5-pro` | `responses` | `mamdani_rent_freeze` | 0.00 | 0/0 | no | HTTP 500: {"error":{"message":"not implemented (request id: 20260512191806371266599ZVHlD8YP)","type":"new_api_error","param":"","code":"conv | 0.00s |
| windhub | `mimo-v2.5-pro` | `responses` | `canada_recession_dual_path` | 0.00 | 0/0 | no | HTTP 500: {"error":{"message":"not implemented (request id: 20260512191806712193612fAvypwgV)","type":"new_api_error","param":"","code":"conv | 0.00s |
| windhub | `mimo-v2.5-pro` | `responses` | `gpt6_before_gta_vi` | 0.00 | 0/0 | no | HTTP 500: {"error":{"message":"not implemented (request id: 2026051219180729938784UocxigB7)","type":"new_api_error","param":"","code":"conve | 0.00s |
| windhub | `mimo-v2.5-pro` | `responses` | `esports_odd_even_kills` | 0.00 | 0/0 | no | HTTP 500: {"error":{"message":"not implemented (request id: 20260512191807357374568oob1YnLz)","type":"new_api_error","param":"","code":"conv | 0.00s |
| windhub | `mimo-v2.5-pro` | `responses` | `balance_of_power_resolution` | 0.00 | 0/0 | no | HTTP 500: {"error":{"message":"not implemented (request id: 20260512191807734901859UAhm6axE)","type":"new_api_error","param":"","code":"conv | 0.00s |
| windhub | `mimo-v2.5-pro` | `responses` | `ukraine_peace_deal_signature` | 0.00 | 0/0 | no | HTTP 500: {"error":{"message":"not implemented (request id: 20260512191808131853677COtfsJNw)","type":"new_api_error","param":"","code":"conv | 0.00s |
| windhub | `mimo-v2.5-pro` | `messages` | `ukraine_peace_deal_signature` | 0.00 | 0/0 | no | HTTP 504: {"type":"https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-504/","title":"Er | 0.00s |

## 3. 解释

- 这个实验比 endpoint-format benchmark 更严格：必须命中人工标注的真实复杂 resolution 规则。
- `pass recall` 表示某模型在多少个 case 上达到该 case 的最低语义召回阈值，同时 schema 和 grounding 合格。
- `perfect` 表示该 case 的人工 golden requirements 全部命中；这是最严格排序的第一优先级。
- 真实自动套利系统应优先选择 `perfect`、`pass recall`、`min recall` 更高的模型，而不是只看 latency。

## 4. 数据归档

- per-call NDJSON: `data/experiments/2026-05-12/llm-complex-recognition-windhub-all-strict.ndjson`
- rows: 240

---
*Snapshot: 2026-05-12T17:35:42.425027+00:00*