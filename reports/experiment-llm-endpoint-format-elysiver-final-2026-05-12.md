# Windhub / Elysiver Endpoint Format 实验报告（2026-05-12T16:00:31.087342+00:00）

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

- elysiver: `longcat-flash-lite`, `qwen3.5-flash`, `grok-4.20-0309-non-reasoning`

## 3. 自动指标对比

| provider | model | format | calls | success | schema | grounding | nonempty | clauses/market | median latency | token in/out | cost class | first error |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| elysiver | `grok-4.20-0309-non-reasoning` | `chat` | 3 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | JSONDecodeError: Expecting value: line 1 column 1 (char 0) |
| elysiver | `grok-4.20-0309-non-reasoning` | `messages` | 3 | 0 | 0 | 0 | 0 | 0.0 | 0.00s | 0/0 | likely_low | JSONDecodeError: Expecting value: line 1 column 1 (char 0) |
| elysiver | `longcat-flash-lite` | `chat` | 3 | 2 | 2 | 2 | 2 | 1.5 | 3.02s | 432/217 | likely_low | TimeoutError: The read operation timed out |
| elysiver | `longcat-flash-lite` | `messages` | 3 | 3 | 3 | 3 | 3 | 1.7 | 1.69s | 480/296 | likely_low |  |
| elysiver | `qwen3.5-flash` | `chat` | 3 | 1 | 1 | 1 | 1 | 2.0 | 13.61s | 407/195 | likely_low | TimeoutError: The read operation timed out |
| elysiver | `qwen3.5-flash` | `messages` | 3 | 2 | 2 | 2 | 2 | 3.0 | 13.72s | 526/412 | likely_low | TimeoutError: The read operation timed out |

## 4. 推荐

1. `elysiver` / `longcat-flash-lite` / `messages`: median 1.69s, schema 3/3, grounding 3/3, cost_class=likely_low.

说明：`cost_class` 是按模型名的保守启发式分类，因为这两个 `/models` 返回没有暴露 pricing 字段；真实价格仍需以服务商后台为准。

## 5. 数据归档

- per-call NDJSON: `data/experiments/2026-05-12/llm-endpoint-format-elysiver-final.ndjson`
- rows: 18

---
*Snapshot: 2026-05-12T16:00:31.087342+00:00*