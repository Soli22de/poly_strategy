# Windhub / Elysiver Endpoint Format 实验报告（2026-05-12T16:52:31.348609+00:00）

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

- elysiver: `llama3.1-8b`, `longcat-flash-lite`, `gpt-oss-20b`

## 3. 自动指标对比

| provider | model | format | calls | success | schema | grounding | nonempty | clauses/market | median latency | token in/out | cost class | first error |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| elysiver | `gpt-oss-20b` | `messages` | 3 | 3 | 2 | 2 | 2 | 1.3 | 8.45s | 532/1278 | unknown_or_mid |  |
| elysiver | `llama3.1-8b` | `messages` | 3 | 3 | 3 | 2 | 3 | 2.3 | 1.80s | 476/245 | likely_low |  |
| elysiver | `longcat-flash-lite` | `messages` | 3 | 2 | 2 | 2 | 2 | 1.5 | 1.90s | 432/219 | likely_low | TimeoutError: The read operation timed out |

## 4. 推荐

没有模型同时满足成功、schema、grounding 和非空输出。

说明：`cost_class` 是按模型名的保守启发式分类，因为这两个 `/models` 返回没有暴露 pricing 字段；真实价格仍需以服务商后台为准。

## 5. 数据归档

- per-call NDJSON: `data/experiments/2026-05-12/llm-endpoint-format-elysiver-lowcost-candidates.ndjson`
- rows: 9

---
*Snapshot: 2026-05-12T16:52:31.348609+00:00*