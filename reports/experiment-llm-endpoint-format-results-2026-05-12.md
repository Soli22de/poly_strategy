# Windhub / Elysiver Endpoint Format 实验报告（2026-05-12T15:25:57.673965+00:00）

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

- windhub: `glm-5.1`
- elysiver: `glm-5.1`

## 3. 自动指标对比

| provider | model | format | calls | success | schema | grounding | nonempty | clauses/market | median latency | token in/out | cost class | first error |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| elysiver | `glm-5.1` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| elysiver | `glm-5.1` | `chat_stream` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| elysiver | `glm-5.1` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| elysiver | `glm-5.1` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 500: {"error":{"message":"Format mismatch: Request appears to be in format ['openai_responses'], but only [['openai |
| windhub | `glm-5.1` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| windhub | `glm-5.1` | `chat_stream` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| windhub | `glm-5.1` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| windhub | `glm-5.1` | `responses` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | HTTP 404: {"error":{"message":"openai_error","type":"bad_response_status_code","param":"","code":"bad_response_status_co |

## 4. 推荐

没有模型同时满足成功、schema、grounding 和非空输出。

说明：`cost_class` 是按模型名的保守启发式分类，因为这两个 `/models` 返回没有暴露 pricing 字段；真实价格仍需以服务商后台为准。

## 5. 数据归档

- per-call NDJSON: `data/experiments/2026-05-12/llm-endpoint-format-results.ndjson`
- rows: 8

---
*Snapshot: 2026-05-12T15:25:57.673965+00:00*