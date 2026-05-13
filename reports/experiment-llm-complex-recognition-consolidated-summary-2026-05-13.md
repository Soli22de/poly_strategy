# LLM 复杂场景识别汇总结论（2026-05-13）

## 结论

按严格复杂场景测试结果看，三家 provider 的可用性差异很大。

## 最强候选

1. `windhub / doubao-seed-1-8-251228 / messages`
   - pass recall: `7/8`
   - perfect: `6/8`
   - avg recall: `0.95`
   - median latency: `76.47s`
   - 语义最强，但太慢，不适合高频主路径。

2. `windhub / deepseek-v3-2-251201 / messages`
   - pass recall: `8/8`
   - perfect: `3/8`
   - avg recall: `0.91`
   - median latency: `44.28s`
   - 这是更均衡的主力候选。

3. `secondary / gemini-2.5-flash-nothinking / messages`
   - pass recall: `7/8`
   - perfect: `4/8`
   - avg recall: `0.91`
   - median latency: `9.20s`
   - 速度最好，但正式链路 smoke 曾出现 `HTTP 554`，不适合作为当前默认自动备份。

4. `elysiver / longcat-flash-chat / chat`
   - pass recall: `8/8`
   - perfect: `4/8`
   - avg recall: `0.94`
   - median latency: `20.08s`
   - 在 elysiver 里最稳，兼顾速度和语义。

5. `elysiver / qwen3-max / messages`
   - pass recall: `7/8`
   - perfect: `3/8`
   - avg recall: `0.87`
   - median latency: `41.96s`
   - 语义强，但慢。

6. `secondary / gemini-3.1-pro-preview / chat_stream`
   - pass recall: `6/8`
   - perfect: `1/8`
   - avg recall: `0.81`
   - median latency: `9.71s`
   - 语义弱于 `gemini-2.5-flash-nothinking/messages`，但正式 CLI smoke 通过，适合作为当前 secondary 默认备份。

## 不推荐路径

- `gpt-5.5-web-auto/messages` 在 elysiver 上被 moderation 直接拦截。
- `gemini-2.5-pro`、`gemini-3-flash-preview`、`glm-5` 在 secondary 上大量 554/不稳定。
- `42-mini`、`42-pro` 在 elysiver 上复杂语义召回偏低。
- `deepseek-v4-flash*` 在 elysiver 上基本 504，不适合继续投入。

## 实际建议

- 主路径：`windhub/deepseek-v3-2-251201/messages`
- 高语义模式：`windhub/doubao-seed-1-8-251228/messages`
- 低延迟语义候选：`secondary/gemini-2.5-flash-nothinking/messages`
- 当前 secondary 默认备份：`secondary/gemini-3.1-pro-preview/chat`
- 第三备份：`elysiver/longcat-flash-chat/chat`

## 正式链路 smoke

- `windhub/deepseek-v3-2-251201/messages`: 通过，2-market threshold 样本发现 `1` 个 implication。
- `secondary/gemini-2.5-flash-nothinking/messages`: 未通过，返回 `HTTP 554`。
- `secondary/gemini-3.1-pro-preview/chat`: 通过，2-market threshold 样本发现 `1` 个 implication。
- `elysiver/longcat-flash-chat/chat`: 通过，2-market threshold 样本发现 `1` 个 implication。

## 说明

- 这里的排序优先看 `perfect` 和 `pass recall`，其次看 `avg recall`，最后才看延迟。
- 若实际部署要偏高频，应优先用主路径 + 备份路径组合，而不是单一追求最高 recall。
