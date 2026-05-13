# Windhub / Elysiver Endpoint Format 实验报告（2026-05-12T16:33:47.684419+00:00）

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

- elysiver: `42-mini`, `deepseek-v4-flash`, `deepseek-v4-flash-2cc`, `gemini-2.5-flash`, `gemini-3-flash-preview`, `glm-4.5-air`, `grok-4.20-0309-non-reasoning`, `llama3.1-8b`, `longcat-flash-chat`, `longcat-flash-lite`, `longcat-flash-thinking`, `longcat-flash-thinking-2cc`, `openrouter-free`, `qwen3.5-flash`, `gemma-4-26b-a4b-it`, `gemma-4-31b-it`, `glm-4.6`, `glm-5`, `glm-5.1`, `glm-5.1-2cc`, `gpt-image-2`, `gpt-oss-120b`, `gpt-oss-20b`, `grok-4.20-fast`, `qwen3-next-80b-a3b`, `42-pro`, `claude-4.6-sonnet-real`, `deepseek-v4-pro`, `deepseek-v4-pro-2cc`, `gpt-5.5-web-auto`, `qwen3-max`, `qwen3.5-plus`, `qwen3.6-plus`, `qwen3.6-plus-thinking`

## 3. 自动指标对比

| provider | model | format | calls | success | schema | grounding | nonempty | clauses/market | median latency | token in/out | cost class | first error |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| elysiver | `42-mini` | `chat` | 1 | 1 | 1 | 1 | 1 | 4.0 | 10.46s | 440/1053 | likely_low |  |
| elysiver | `42-mini` | `messages` | 1 | 1 | 1 | 1 | 1 | 2.0 | 11.18s | 429/558 | likely_low |  |
| elysiver | `42-pro` | `chat` | 1 | 1 | 1 | 1 | 1 | 2.0 | 8.21s | 440/663 | likely_high |  |
| elysiver | `42-pro` | `messages` | 1 | 1 | 1 | 1 | 1 | 2.0 | 9.38s | 429/607 | likely_high |  |
| elysiver | `claude-4.6-sonnet-real` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_high | HTTP 500: {"error":{"message":"No cookie available","type":"no_cookie_available","param":"","code":500}} |
| elysiver | `claude-4.6-sonnet-real` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_high | HTTP 500: {"error":{"type":"500","message":"No cookie available (request id: 202605121644511668321296XQllPpD)"},"type":" |
| elysiver | `deepseek-v4-flash` | `chat` | 1 | 1 | 1 | 1 | 1 | 2.0 | 13.36s | 412/1032 | likely_low |  |
| elysiver | `deepseek-v4-flash` | `messages` | 1 | 1 | 1 | 1 | 1 | 2.0 | 9.44s | 410/849 | likely_low |  |
| elysiver | `deepseek-v4-flash-2cc` | `chat` | 1 | 1 | 1 | 1 | 1 | 2.0 | 13.13s | 410/1284 | likely_low |  |
| elysiver | `deepseek-v4-flash-2cc` | `messages` | 1 | 1 | 1 | 1 | 1 | 2.0 | 13.83s | 410/741 | likely_low |  |
| elysiver | `deepseek-v4-pro` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_high | TimeoutError: The read operation timed out |
| elysiver | `deepseek-v4-pro` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_high | TimeoutError: The read operation timed out |
| elysiver | `deepseek-v4-pro-2cc` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_high | TimeoutError: The read operation timed out |
| elysiver | `deepseek-v4-pro-2cc` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_high | TimeoutError: The read operation timed out |
| elysiver | `gemini-2.5-flash` | `chat` | 1 | 1 | 1 | 1 | 1 | 2.0 | 7.03s | 433/994 | likely_low |  |
| elysiver | `gemini-2.5-flash` | `messages` | 1 | 1 | 1 | 1 | 1 | 2.0 | 6.83s | 433/1213 | likely_low |  |
| elysiver | `gemini-3-flash-preview` | `chat` | 1 | 1 | 1 | 1 | 1 | 3.0 | 6.01s | 433/1066 | likely_low |  |
| elysiver | `gemini-3-flash-preview` | `messages` | 1 | 1 | 0 | 0 | 0 | 0.0 | 9.41s | 433/1796 | likely_low |  |
| elysiver | `gemma-4-26b-a4b-it` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| elysiver | `gemma-4-26b-a4b-it` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| elysiver | `gemma-4-31b-it` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| elysiver | `gemma-4-31b-it` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| elysiver | `glm-4.5-air` | `chat` | 1 | 1 | 1 | 1 | 1 | 2.0 | 19.36s | 462/781 | likely_low |  |
| elysiver | `glm-4.5-air` | `messages` | 1 | 1 | 1 | 1 | 1 | 2.0 | 17.37s | 403/759 | likely_low |  |
| elysiver | `glm-4.6` | `chat` | 1 | 1 | 1 | 1 | 1 | 2.0 | 11.10s | 440/211 | unknown_or_mid |  |
| elysiver | `glm-4.6` | `messages` | 1 | 1 | 1 | 1 | 1 | 2.0 | 10.94s | 429/250 | unknown_or_mid |  |
| elysiver | `glm-5` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| elysiver | `glm-5` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| elysiver | `glm-5.1` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| elysiver | `glm-5.1` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| elysiver | `glm-5.1-2cc` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| elysiver | `glm-5.1-2cc` | `messages` | 1 | 1 | 1 | 1 | 1 | 3.0 | 19.24s | 402/940 | unknown_or_mid |  |
| elysiver | `gpt-5.5-web-auto` | `chat` | 1 | 1 | 1 | 1 | 1 | 2.0 | 17.16s | 410/220 | likely_high |  |
| elysiver | `gpt-5.5-web-auto` | `messages` | 1 | 1 | 1 | 1 | 1 | 2.0 | 12.55s | 410/217 | likely_high |  |
| elysiver | `gpt-image-2` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| elysiver | `gpt-image-2` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| elysiver | `gpt-oss-120b` | `chat` | 1 | 1 | 1 | 1 | 1 | 2.0 | 4.34s | 468/415 | unknown_or_mid |  |
| elysiver | `gpt-oss-120b` | `messages` | 1 | 1 | 1 | 1 | 1 | 2.0 | 7.81s | 468/742 | unknown_or_mid |  |
| elysiver | `gpt-oss-20b` | `chat` | 1 | 1 | 1 | 1 | 1 | 2.0 | 5.37s | 468/787 | unknown_or_mid |  |
| elysiver | `gpt-oss-20b` | `messages` | 1 | 1 | 1 | 1 | 1 | 2.0 | 4.66s | 468/688 | unknown_or_mid |  |
| elysiver | `grok-4.20-0309-non-reasoning` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | JSONDecodeError: Expecting value: line 1 column 1 (char 0) |
| elysiver | `grok-4.20-0309-non-reasoning` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | JSONDecodeError: Expecting value: line 1 column 1 (char 0) |
| elysiver | `grok-4.20-fast` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | JSONDecodeError: Expecting value: line 1 column 1 (char 0) |
| elysiver | `grok-4.20-fast` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | JSONDecodeError: Expecting value: line 1 column 1 (char 0) |
| elysiver | `llama3.1-8b` | `chat` | 1 | 1 | 1 | 1 | 1 | 1.0 | 4.95s | 411/137 | likely_low |  |
| elysiver | `llama3.1-8b` | `messages` | 1 | 1 | 1 | 1 | 1 | 2.0 | 1.04s | 411/173 | likely_low |  |
| elysiver | `longcat-flash-chat` | `chat` | 1 | 1 | 1 | 1 | 1 | 2.0 | 3.28s | 410/230 | likely_low |  |
| elysiver | `longcat-flash-chat` | `messages` | 1 | 1 | 1 | 1 | 1 | 2.0 | 4.12s | 410/224 | likely_low |  |
| elysiver | `longcat-flash-lite` | `chat` | 1 | 1 | 1 | 1 | 1 | 2.0 | 1.76s | 400/216 | likely_low |  |
| elysiver | `longcat-flash-lite` | `messages` | 1 | 1 | 1 | 1 | 1 | 2.0 | 8.85s | 400/215 | likely_low |  |
| elysiver | `longcat-flash-thinking` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | HTTP 500: {"error":{"message":"服务端模型:longcat-flash-thinking-2601-platform 可用容量超过限制","type":"rate_limit_error","param":"" |
| elysiver | `longcat-flash-thinking` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| elysiver | `longcat-flash-thinking-2cc` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| elysiver | `longcat-flash-thinking-2cc` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| elysiver | `openrouter-free` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | TimeoutError: The read operation timed out |
| elysiver | `openrouter-free` | `messages` | 1 | 1 | 1 | 1 | 1 | 2.0 | 6.84s | 413/193 | likely_low |  |
| elysiver | `qwen3-max` | `chat` | 1 | 1 | 1 | 1 | 1 | 2.0 | 11.92s | 407/184 | likely_high |  |
| elysiver | `qwen3-max` | `messages` | 1 | 1 | 1 | 1 | 1 | 2.0 | 12.27s | 407/193 | likely_high |  |
| elysiver | `qwen3-next-80b-a3b` | `chat` | 1 | 1 | 0 | 0 | 0 | 0.0 | 16.50s | 393/1800 | unknown_or_mid |  |
| elysiver | `qwen3-next-80b-a3b` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | unknown_or_mid | TimeoutError: The read operation timed out |
| elysiver | `qwen3.5-flash` | `chat` | 1 | 1 | 1 | 1 | 1 | 2.0 | 7.52s | 407/191 | likely_low |  |
| elysiver | `qwen3.5-flash` | `messages` | 1 | 1 | 1 | 1 | 1 | 2.0 | 8.51s | 407/192 | likely_low |  |
| elysiver | `qwen3.5-plus` | `chat` | 1 | 1 | 1 | 1 | 1 | 3.0 | 17.67s | 407/250 | likely_high |  |
| elysiver | `qwen3.5-plus` | `messages` | 1 | 1 | 1 | 1 | 1 | 2.0 | 12.86s | 407/258 | likely_high |  |
| elysiver | `qwen3.6-plus` | `chat` | 1 | 1 | 1 | 1 | 1 | 2.0 | 14.01s | 407/239 | likely_high |  |
| elysiver | `qwen3.6-plus` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_high | TimeoutError: The read operation timed out |
| elysiver | `qwen3.6-plus-thinking` | `chat` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_high | TimeoutError: The read operation timed out |
| elysiver | `qwen3.6-plus-thinking` | `messages` | 1 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_high | TimeoutError: The read operation timed out |

## 4. 推荐

1. `elysiver` / `llama3.1-8b` / `messages`: median 1.04s, schema 1/1, grounding 1/1, cost_class=likely_low.
2. `elysiver` / `longcat-flash-lite` / `chat`: median 1.76s, schema 1/1, grounding 1/1, cost_class=likely_low.
3. `elysiver` / `longcat-flash-chat` / `chat`: median 3.28s, schema 1/1, grounding 1/1, cost_class=likely_low.
4. `elysiver` / `longcat-flash-chat` / `messages`: median 4.12s, schema 1/1, grounding 1/1, cost_class=likely_low.
5. `elysiver` / `llama3.1-8b` / `chat`: median 4.95s, schema 1/1, grounding 1/1, cost_class=likely_low.

说明：`cost_class` 是按模型名的保守启发式分类，因为这两个 `/models` 返回没有暴露 pricing 字段；真实价格仍需以服务商后台为准。

## 5. 数据归档

- per-call NDJSON: `data/experiments/2026-05-12/llm-endpoint-format-elysiver-all-smoke.ndjson`
- rows: 68

---
*Snapshot: 2026-05-12T16:33:47.684419+00:00*