# Windhub / Elysiver Endpoint Format 实验报告（2026-05-12T15:48:39.910481+00:00）

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

- windhub: `deepseek-v3-2-251201`, `doubao-seed-2-0-lite-260428`, `glm-5.1`, `mimo-v2.5`

## 3. 自动指标对比

| provider | model | format | calls | success | schema | grounding | nonempty | clauses/market | median latency | token in/out | cost class | first error |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| windhub | `deepseek-v3-2-251201` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| windhub | `deepseek-v3-2-251201` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| windhub | `deepseek-v3-2-251201` | `chat_stream` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| windhub | `deepseek-v3-2-251201` | `chat_stream_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| windhub | `deepseek-v3-2-251201` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| windhub | `deepseek-v3-2-251201` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| windhub | `doubao-seed-2-0-lite-260428` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 400: {"error":{"message":"The parameter `response_format.type` specified in the request are not valid: `json_object |
| windhub | `doubao-seed-2-0-lite-260428` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| windhub | `doubao-seed-2-0-lite-260428` | `chat_stream` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| windhub | `doubao-seed-2-0-lite-260428` | `chat_stream_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| windhub | `doubao-seed-2-0-lite-260428` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| windhub | `doubao-seed-2-0-lite-260428` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| windhub | `glm-5.1` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| windhub | `glm-5.1` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| windhub | `glm-5.1` | `chat_stream` | 1 | 1 | 1 | 1 | 1 | 2.0 | 76.77s | 0/0 | unknown_or_mid |  |
| windhub | `glm-5.1` | `chat_stream_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| windhub | `glm-5.1` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| windhub | `glm-5.1` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 404: {"error":{"message":"openai_error","type":"bad_response_status_code","param":"","code":"bad_response_status_co |
| windhub | `mimo-v2.5` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| windhub | `mimo-v2.5` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| windhub | `mimo-v2.5` | `chat_stream` | 1 | 1 | 1 | 1 | 1 | 2.0 | 19.72s | 0/0 | likely_low |  |
| windhub | `mimo-v2.5` | `chat_stream_plain` | 1 | 1 | 0 | 0 | 0 | 0.0 | 26.30s | 0/0 | likely_low |  |
| windhub | `mimo-v2.5` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| windhub | `mimo-v2.5` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 500: {"error":{"message":"not implemented (request id: 20260512155514364146144zHvCdTdE)","type":"new_api_error","pa |

## 4. 推荐

1. `windhub` / `mimo-v2.5` / `chat_stream`: median 19.72s, schema 1/1, grounding 1/1, cost_class=likely_low.

说明：`cost_class` 是按模型名的保守启发式分类，因为这两个 `/models` 返回没有暴露 pricing 字段；真实价格仍需以服务商后台为准。

## 5. 数据归档

- per-call NDJSON: `data/experiments/2026-05-12/llm-endpoint-format-windhub-smoke.ndjson`
- rows: 24

---
*Snapshot: 2026-05-12T15:48:39.910481+00:00*