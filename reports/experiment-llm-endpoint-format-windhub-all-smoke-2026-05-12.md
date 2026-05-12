# Windhub / Elysiver Endpoint Format 实验报告（2026-05-12T16:08:16.055425+00:00）

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

- windhub: `doubao-seed-2-0-lite-260428`, `mimo-v2.5`, `mimo-v2.5-pro`, `deepseek-v3-2-251201`, `doubao-seed-1-6-251015`, `doubao-seed-1-8-251228`, `doubao-seedream-4-5-251128`, `glm-5.1`, `kimi-k2.6`, `doubao-1-5-pro-32k-250115`

## 3. 自动指标对比

| provider | model | format | calls | success | schema | grounding | nonempty | clauses/market | median latency | token in/out | cost class | first error |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| windhub | `deepseek-v3-2-251201` | `chat` | 1 | 1 | 1 | 1 | 1 | 2.0 | 8.14s | 410/186 | unknown_or_mid |  |
| windhub | `deepseek-v3-2-251201` | `chat_plain` | 1 | 1 | 1 | 1 | 1 | 2.0 | 10.43s | 410/199 | unknown_or_mid |  |
| windhub | `deepseek-v3-2-251201` | `chat_stream` | 1 | 1 | 1 | 1 | 1 | 2.0 | 6.56s | 0/0 | unknown_or_mid |  |
| windhub | `deepseek-v3-2-251201` | `chat_stream_plain` | 1 | 1 | 1 | 1 | 1 | 4.0 | 12.93s | 0/0 | unknown_or_mid |  |
| windhub | `deepseek-v3-2-251201` | `messages` | 1 | 1 | 1 | 1 | 1 | 1.0 | 7.09s | 410/165 | unknown_or_mid |  |
| windhub | `deepseek-v3-2-251201` | `responses` | 1 | 1 | 1 | 1 | 1 | 3.0 | 8.20s | 639/236 | unknown_or_mid |  |
| windhub | `doubao-1-5-pro-32k-250115` | `chat` | 1 | 1 | 1 | 1 | 1 | 2.0 | 6.22s | 446/228 | likely_high |  |
| windhub | `doubao-1-5-pro-32k-250115` | `chat_plain` | 1 | 1 | 1 | 1 | 1 | 2.0 | 7.33s | 446/230 | likely_high |  |
| windhub | `doubao-1-5-pro-32k-250115` | `chat_stream` | 1 | 1 | 1 | 1 | 1 | 2.0 | 8.48s | 0/0 | likely_high |  |
| windhub | `doubao-1-5-pro-32k-250115` | `chat_stream_plain` | 1 | 1 | 1 | 1 | 1 | 2.0 | 8.07s | 0/0 | likely_high |  |
| windhub | `doubao-1-5-pro-32k-250115` | `messages` | 1 | 1 | 1 | 1 | 1 | 2.0 | 5.46s | 446/225 | likely_high |  |
| windhub | `doubao-1-5-pro-32k-250115` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_high | HTTP 403: {"error":{"message":"The request failed because model `doubao-1-5-pro-32k-250115` does not have access to resp |
| windhub | `doubao-seed-1-6-251015` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| windhub | `doubao-seed-1-6-251015` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| windhub | `doubao-seed-1-6-251015` | `chat_stream` | 1 | 1 | 1 | 1 | 1 | 2.0 | 59.81s | 0/0 | unknown_or_mid |  |
| windhub | `doubao-seed-1-6-251015` | `chat_stream_plain` | 1 | 1 | 1 | 1 | 1 | 2.0 | 35.97s | 0/0 | unknown_or_mid |  |
| windhub | `doubao-seed-1-6-251015` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| windhub | `doubao-seed-1-6-251015` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| windhub | `doubao-seed-1-8-251228` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| windhub | `doubao-seed-1-8-251228` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| windhub | `doubao-seed-1-8-251228` | `chat_stream` | 1 | 1 | 1 | 1 | 1 | 2.0 | 52.41s | 0/0 | unknown_or_mid |  |
| windhub | `doubao-seed-1-8-251228` | `chat_stream_plain` | 1 | 1 | 1 | 1 | 1 | 2.0 | 27.72s | 0/0 | unknown_or_mid |  |
| windhub | `doubao-seed-1-8-251228` | `messages` | 1 | 1 | 1 | 1 | 1 | 2.0 | 20.88s | 470/1033 | unknown_or_mid |  |
| windhub | `doubao-seed-1-8-251228` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| windhub | `doubao-seed-2-0-lite-260428` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 400: {"error":{"message":"The parameter `response_format.type` specified in the request are not valid: `json_object |
| windhub | `doubao-seed-2-0-lite-260428` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| windhub | `doubao-seed-2-0-lite-260428` | `chat_stream` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 400: {"error":{"message":"The parameter `response_format.type` specified in the request are not valid: `json_object |
| windhub | `doubao-seed-2-0-lite-260428` | `chat_stream_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| windhub | `doubao-seed-2-0-lite-260428` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| windhub | `doubao-seed-2-0-lite-260428` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| windhub | `doubao-seedream-4-5-251128` | `chat` | 1 | 1 | 0 | 0 | 0 | 0.0 | 21.82s | 0/0 | unknown_or_mid |  |
| windhub | `doubao-seedream-4-5-251128` | `chat_plain` | 1 | 1 | 0 | 0 | 0 | 0.0 | 21.19s | 0/0 | unknown_or_mid |  |
| windhub | `doubao-seedream-4-5-251128` | `chat_stream` | 1 | 1 | 0 | 0 | 0 | 0.0 | 25.21s | 0/0 | unknown_or_mid |  |
| windhub | `doubao-seedream-4-5-251128` | `chat_stream_plain` | 1 | 1 | 0 | 0 | 0 | 0.0 | 24.64s | 0/0 | unknown_or_mid |  |
| windhub | `doubao-seedream-4-5-251128` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 500: {"error":{"type":"new_api_error","message":"not implemented (request id: 20260512162525643924333olMxOOzK)"},"t |
| windhub | `doubao-seedream-4-5-251128` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 500: {"error":{"message":"not implemented (request id: 20260512162525244316407hQxGIYwM)","type":"new_api_error","pa |
| windhub | `glm-5.1` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| windhub | `glm-5.1` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| windhub | `glm-5.1` | `chat_stream` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| windhub | `glm-5.1` | `chat_stream_plain` | 1 | 1 | 1 | 1 | 1 | 2.0 | 82.95s | 0/0 | unknown_or_mid |  |
| windhub | `glm-5.1` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| windhub | `glm-5.1` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 404: {"error":{"message":"openai_error","type":"bad_response_status_code","param":"","code":"bad_response_status_co |
| windhub | `kimi-k2.6` | `chat` | 1 | 1 | 0 | 0 | 0 | 0.0 | 20.45s | 402/1800 | unknown_or_mid |  |
| windhub | `kimi-k2.6` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| windhub | `kimi-k2.6` | `chat_stream` | 1 | 1 | 0 | 0 | 0 | 0.0 | 80.65s | 0/0 | unknown_or_mid |  |
| windhub | `kimi-k2.6` | `chat_stream_plain` | 1 | 1 | 1 | 1 | 1 | 2.0 | 75.69s | 0/0 | unknown_or_mid |  |
| windhub | `kimi-k2.6` | `messages` | 1 | 1 | 1 | 1 | 1 | 2.0 | 13.02s | 402/1407 | unknown_or_mid |  |
| windhub | `kimi-k2.6` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 404: {"error":{"message":"openai_error","type":"bad_response_status_code","param":"","code":"bad_response_status_co |
| windhub | `mimo-v2.5` | `chat` | 1 | 1 | 0 | 0 | 0 | 0.0 | 22.53s | 27/1800 | likely_low |  |
| windhub | `mimo-v2.5` | `chat_plain` | 1 | 1 | 0 | 0 | 0 | 0.0 | 25.29s | 27/1800 | likely_low |  |
| windhub | `mimo-v2.5` | `chat_stream` | 1 | 1 | 0 | 0 | 0 | 0.0 | 24.61s | 0/0 | likely_low |  |
| windhub | `mimo-v2.5` | `chat_stream_plain` | 1 | 1 | 0 | 0 | 0 | 0.0 | 22.55s | 0/0 | likely_low |  |
| windhub | `mimo-v2.5` | `messages` | 1 | 1 | 0 | 0 | 0 | 0.0 | 22.25s | 27/1800 | likely_low |  |
| windhub | `mimo-v2.5` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 500: {"error":{"message":"not implemented (request id: 20260512161239653052814CUycRuPS)","type":"new_api_error","pa |
| windhub | `mimo-v2.5-pro` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| windhub | `mimo-v2.5-pro` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| windhub | `mimo-v2.5-pro` | `chat_stream` | 1 | 1 | 0 | 0 | 0 | 0.0 | 44.39s | 0/0 | likely_low |  |
| windhub | `mimo-v2.5-pro` | `chat_stream_plain` | 1 | 1 | 0 | 0 | 0 | 0.0 | 52.87s | 0/0 | likely_low |  |
| windhub | `mimo-v2.5-pro` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| windhub | `mimo-v2.5-pro` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 500: {"error":{"message":"not implemented (request id: 20260512161539885494675qBvdxvm8)","type":"new_api_error","pa |

## 4. 推荐

1. `windhub` / `doubao-1-5-pro-32k-250115` / `messages`: median 5.46s, schema 1/1, grounding 1/1, cost_class=likely_high.
2. `windhub` / `doubao-1-5-pro-32k-250115` / `chat`: median 6.22s, schema 1/1, grounding 1/1, cost_class=likely_high.
3. `windhub` / `deepseek-v3-2-251201` / `chat_stream`: median 6.56s, schema 1/1, grounding 1/1, cost_class=unknown_or_mid.
4. `windhub` / `deepseek-v3-2-251201` / `messages`: median 7.09s, schema 1/1, grounding 1/1, cost_class=unknown_or_mid.
5. `windhub` / `doubao-1-5-pro-32k-250115` / `chat_plain`: median 7.33s, schema 1/1, grounding 1/1, cost_class=likely_high.

说明：`cost_class` 是按模型名的保守启发式分类，因为这两个 `/models` 返回没有暴露 pricing 字段；真实价格仍需以服务商后台为准。

## 5. 数据归档

- per-call NDJSON: `data/experiments/2026-05-12/llm-endpoint-format-windhub-all-smoke.ndjson`
- rows: 60

---
*Snapshot: 2026-05-12T16:08:16.055425+00:00*