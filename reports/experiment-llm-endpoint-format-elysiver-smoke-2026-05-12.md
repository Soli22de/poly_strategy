# Windhub / Elysiver Endpoint Format 实验报告（2026-05-12T15:48:41.096356+00:00）

## 1. 模型枚举

### elysiver
- `42-mini` (likely_low) owned_by=custom
- `42-pro` (likely_high) owned_by=custom
- `claude-4.6-sonnet-real` (likely_high) owned_by=custom
- `deepseek-v4-flash` (likely_low) owned_by=custom
- `deepseek-v4-flash-2cc` (likely_low) owned_by=custom
- `deepseek-v4-pro` (likely_high) owned_by=custom
- `deepseek-v4-pro-2cc` (likely_high) owned_by=custom
- `gemini-2.5-flash` (likely_low) owned_by=custom
- `gemini-3-flash-preview` (likely_low) owned_by=custom
- `gemma-4-26b-a4b-it` (unknown_or_mid) owned_by=custom
- `gemma-4-31b-it` (unknown_or_mid) owned_by=custom
- `glm-4.5-air` (likely_low) owned_by=custom
- `glm-4.6` (unknown_or_mid) owned_by=zhipu_4v
- `glm-4.7` (unknown_or_mid) owned_by=custom
- `glm-5` (unknown_or_mid) owned_by=custom
- `glm-5.1` (unknown_or_mid) owned_by=custom
- `glm-5.1-2cc` (unknown_or_mid) owned_by=custom
- `gpt-5.5-web-auto` (likely_high) owned_by=custom
- `gpt-image-2` (unknown_or_mid) owned_by=custom
- `gpt-oss-120b` (unknown_or_mid) owned_by=custom
- `gpt-oss-20b` (unknown_or_mid) owned_by=custom
- `grok-4.20-0309-non-reasoning` (likely_low) owned_by=custom
- `grok-4.20-fast` (unknown_or_mid) owned_by=custom
- `llama3.1-8b` (likely_low) owned_by=custom
- `longcat-flash-chat` (likely_low) owned_by=custom
- `longcat-flash-lite` (likely_low) owned_by=custom
- `longcat-flash-thinking` (likely_low) owned_by=custom
- `longcat-flash-thinking-2cc` (likely_low) owned_by=custom
- `openrouter-free` (likely_low) owned_by=custom
- `qwen3-max` (likely_high) owned_by=custom
- `qwen3-next-80b-a3b` (unknown_or_mid) owned_by=custom
- `qwen3.5-flash` (likely_low) owned_by=custom
- `qwen3.5-plus` (likely_high) owned_by=custom
- `qwen3.6-plus` (likely_high) owned_by=custom
- `qwen3.6-plus-thinking` (likely_high) owned_by=custom

## 2. 实测模型范围

- elysiver: `deepseek-v4-flash`, `gemini-2.5-flash`, `longcat-flash-lite`, `qwen3.5-flash`, `42-mini`, `glm-5.1`, `grok-4.20-0309-non-reasoning`

## 3. 自动指标对比

| provider | model | format | calls | success | schema | grounding | nonempty | clauses/market | median latency | token in/out | cost class | first error |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| elysiver | `42-mini` | `chat` | 1 | 1 | 1 | 1 | 1 | 3.0 | 8.69s | 440/764 | likely_low |  |
| elysiver | `42-mini` | `chat_plain` | 1 | 1 | 1 | 1 | 1 | 4.0 | 7.88s | 440/720 | likely_low |  |
| elysiver | `42-mini` | `chat_stream` | 1 | 1 | 1 | 1 | 1 | 3.0 | 8.20s | 0/0 | likely_low |  |
| elysiver | `42-mini` | `chat_stream_plain` | 1 | 1 | 1 | 0 | 1 | 4.0 | 8.16s | 0/0 | likely_low |  |
| elysiver | `42-mini` | `messages` | 1 | 1 | 1 | 1 | 1 | 4.0 | 7.99s | 429/837 | likely_low |  |
| elysiver | `42-mini` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 500: {"error":{"message":"Format mismatch: Request appears to be in format ['openai_responses'], but only [['openai |
| elysiver | `deepseek-v4-flash` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| elysiver | `deepseek-v4-flash` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| elysiver | `deepseek-v4-flash` | `chat_stream` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| elysiver | `deepseek-v4-flash` | `chat_stream_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| elysiver | `deepseek-v4-flash` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| elysiver | `deepseek-v4-flash` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 500: {"error":{"message":"Format mismatch: Request appears to be in format ['openai_responses'], but only [['openai |
| elysiver | `gemini-2.5-flash` | `chat` | 1 | 1 | 1 | 1 | 1 | 2.0 | 6.74s | 433/849 | likely_low |  |
| elysiver | `gemini-2.5-flash` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| elysiver | `gemini-2.5-flash` | `chat_stream` | 1 | 1 | 1 | 1 | 1 | 2.0 | 12.09s | 0/0 | likely_low |  |
| elysiver | `gemini-2.5-flash` | `chat_stream_plain` | 1 | 1 | 1 | 1 | 1 | 2.0 | 12.58s | 0/0 | likely_low |  |
| elysiver | `gemini-2.5-flash` | `messages` | 1 | 1 | 1 | 1 | 1 | 2.0 | 9.10s | 433/1213 | likely_low |  |
| elysiver | `gemini-2.5-flash` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 500: {"error":{"message":"not implemented (request id: 20260512155045427857879zz2nRVSQ)","type":"new_api_error","pa |
| elysiver | `glm-5.1` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| elysiver | `glm-5.1` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| elysiver | `glm-5.1` | `chat_stream` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| elysiver | `glm-5.1` | `chat_stream_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| elysiver | `glm-5.1` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| elysiver | `glm-5.1` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 500: {"error":{"message":"Format mismatch: Request appears to be in format ['openai_responses'], but only [['openai |
| elysiver | `grok-4.20-0309-non-reasoning` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | JSONDecodeError: Expecting value: line 1 column 1 (char 0) |
| elysiver | `grok-4.20-0309-non-reasoning` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | JSONDecodeError: Expecting value: line 1 column 1 (char 0) |
| elysiver | `grok-4.20-0309-non-reasoning` | `chat_stream` | 1 | 1 | 1 | 1 | 1 | 2.0 | 8.00s | 0/0 | likely_low |  |
| elysiver | `grok-4.20-0309-non-reasoning` | `chat_stream_plain` | 1 | 1 | 1 | 1 | 1 | 2.0 | 7.07s | 0/0 | likely_low |  |
| elysiver | `grok-4.20-0309-non-reasoning` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | JSONDecodeError: Expecting value: line 1 column 1 (char 0) |
| elysiver | `grok-4.20-0309-non-reasoning` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| elysiver | `longcat-flash-lite` | `chat` | 1 | 1 | 1 | 1 | 1 | 2.0 | 3.33s | 400/215 | likely_low |  |
| elysiver | `longcat-flash-lite` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| elysiver | `longcat-flash-lite` | `chat_stream` | 1 | 1 | 0 | 0 | 0 | 0.0 | 4.29s | 0/0 | likely_low |  |
| elysiver | `longcat-flash-lite` | `chat_stream_plain` | 1 | 1 | 0 | 0 | 0 | 0.0 | 2.95s | 0/0 | likely_low |  |
| elysiver | `longcat-flash-lite` | `messages` | 1 | 1 | 1 | 1 | 1 | 2.0 | 6.45s | 400/212 | likely_low |  |
| elysiver | `longcat-flash-lite` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 500: {"error":{"message":"Format mismatch: Request appears to be in format ['openai_responses'], but only [['openai |
| elysiver | `qwen3.5-flash` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| elysiver | `qwen3.5-flash` | `chat_plain` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| elysiver | `qwen3.5-flash` | `chat_stream` | 1 | 1 | 1 | 1 | 1 | 2.0 | 10.03s | 0/0 | likely_low |  |
| elysiver | `qwen3.5-flash` | `chat_stream_plain` | 1 | 1 | 1 | 1 | 1 | 2.0 | 11.08s | 0/0 | likely_low |  |
| elysiver | `qwen3.5-flash` | `messages` | 1 | 1 | 1 | 1 | 1 | 2.0 | 11.29s | 407/192 | likely_low |  |
| elysiver | `qwen3.5-flash` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 500: {"error":{"message":"openai_error","type":"bad_response_status_code","param":"","code":"bad_response_status_co |

## 4. 推荐

1. `elysiver` / `longcat-flash-lite` / `chat`: median 3.33s, schema 1/1, grounding 1/1, cost_class=likely_low.
2. `elysiver` / `longcat-flash-lite` / `messages`: median 6.45s, schema 1/1, grounding 1/1, cost_class=likely_low.
3. `elysiver` / `gemini-2.5-flash` / `chat`: median 6.74s, schema 1/1, grounding 1/1, cost_class=likely_low.
4. `elysiver` / `grok-4.20-0309-non-reasoning` / `chat_stream_plain`: median 7.07s, schema 1/1, grounding 1/1, cost_class=likely_low.
5. `elysiver` / `42-mini` / `chat_plain`: median 7.88s, schema 1/1, grounding 1/1, cost_class=likely_low.

说明：`cost_class` 是按模型名的保守启发式分类，因为这两个 `/models` 返回没有暴露 pricing 字段；真实价格仍需以服务商后台为准。

## 5. 数据归档

- per-call NDJSON: `data/experiments/2026-05-12/llm-endpoint-format-elysiver-smoke.ndjson`
- rows: 42

---
*Snapshot: 2026-05-12T15:48:41.096356+00:00*