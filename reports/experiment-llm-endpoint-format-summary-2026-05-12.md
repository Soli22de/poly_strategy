# LLM Endpoint / Model Format 总结报告（2026-05-12）

## 1. 实验目标

按同一个 Polymarket T2 resolution-clause 抽取任务，测试用户提供的两个 Chat-compatible endpoint：

- `windhub`: 主站点
- `elysiver`: 备用站点

优先级：

1. 稳定完美识别：请求成功、JSON 可解析、schema 合格、`source_substring` 能在 `verbatim_text` 中 grounded、输出非空 clauses。
2. 速度：在满足 1 的前提下再比较 median latency。
3. 成本：因为两个 `/models` 响应没有返回 pricing 字段，本报告只能用模型名做启发式低/中/高成本判断，真实价格仍以站点后台计费为准。

## 2. 已测试范围

### Windhub

- 模型：`/models` 返回的 10 个模型全部测试。
- 第一阶段：每个模型跑 1 个真实 Gamma market，覆盖 `chat`、`chat_stream`、`chat_plain`、`chat_stream_plain`、`responses`、`messages` 六种格式。
- 第二阶段：对候选 `deepseek-v3-2-251201` 和 `doubao-1-5-pro-32k-250115` 跑 3 个真实 market 的复测。

核心文件：

- `reports/experiment-llm-endpoint-format-windhub-all-smoke-2026-05-12.md`
- `reports/experiment-llm-endpoint-format-windhub-candidates-2026-05-12.md`

### Elysiver

- 模型：`/models` 返回的 34 个模型全部至少测试 `chat` / `messages`。
- 额外测试：部分候选和已知格式跑过 `chat_stream`、`chat_stream_plain`、`responses`。
- 第二阶段：对低价快模型 `llama3.1-8b`、`longcat-flash-lite`、`gpt-oss-20b` 跑 3 个真实 market 的复测。

核心文件：

- `reports/experiment-llm-endpoint-format-elysiver-all-smoke-2026-05-12.md`
- `reports/experiment-llm-endpoint-format-elysiver-lowcost-candidates-2026-05-12.md`

## 3. Windhub 结论

### 最佳候选：`doubao-1-5-pro-32k-250115`

3-market 复测结果：

| format | calls | success | schema | grounding | nonempty | median latency |
|---|---:|---:|---:|---:|---:|---:|
| `messages` | 3 | 3 | 3 | 3 | 3 | 6.40s |
| `chat` | 3 | 3 | 3 | 3 | 3 | 6.47s |

判断：

- 当前 windhub 上最适合做生产主路由。
- `messages` 略快，`chat` 也几乎同速且更接近现有 OpenAI-compatible 代码路径。
- 缺点：`responses` 返回 403，不适合作 responses API 路由。
- 成本启发式：`likely_high`，因为是 pro/32k 模型；真实价格要看 windhub 后台。

### 备用候选：`deepseek-v3-2-251201`

3-market 复测结果：

| format | calls | success | schema | grounding | nonempty | median latency |
|---|---:|---:|---:|---:|---:|---:|
| `chat` | 3 | 3 | 3 | 3 | 3 | 12.80s |
| `messages` | 3 | 3 | 3 | 3 | 3 | 12.81s |

单样本全格式测试中，`deepseek-v3-2-251201` 是 windhub 上唯一同时通过 `chat`、`chat_stream`、`chat_plain`、`chat_stream_plain`、`responses`、`messages` 的模型。

判断：

- 作为 windhub 的通用兼容 fallback 很好。
- 如果必须走 `responses`，目前优先用它。
- 缺点：速度大约是 `doubao-1-5-pro-32k-250115` 的 2 倍慢。

### 不建议作为主路由的 windhub 模型

- `doubao-seed-2-0-lite-260428`: `json_object` 400，plain/messages 多次超时。
- `mimo-v2.5` / `mimo-v2.5-pro`: 能返回但经常 schema 不合格。
- `glm-5.1`: 大多超时，偶尔 stream plain 合格但 80s 级，不适合自动化扫描。
- `kimi-k2.6`: 部分格式可用，但慢且不稳定。
- `doubao-seed-1-6/1-8`: 可用格式很慢，20-60s 级。
- `doubao-seedream-4-5`: 返回内容非目标 schema，不适合文本抽取。

## 4. Elysiver 结论

单样本全模型 `chat/messages` 里最快的合格项包括：

| model / format | single-sample latency | 备注 |
|---|---:|---|
| `llama3.1-8b/messages` | 1.04s | 3-market 复测有 1 条 grounding 不合格 |
| `longcat-flash-lite/chat` | 1.76s | 多样本遇到长文本超时 |
| `longcat-flash-chat/chat` | 3.28s | 只做过单样本，需继续复测 |
| `gpt-oss-120b/chat` | 4.34s | 只做过单样本，需继续复测 |
| `gpt-oss-20b/messages` | 4.66s | 3-market 复测有 1 条 schema 不合格 |

低成本候选 3-market 复测：

| model / format | calls | success | schema | grounding | nonempty | median latency |
|---|---:|---:|---:|---:|---:|---:|
| `llama3.1-8b/messages` | 3 | 3 | 3 | 2 | 3 | 1.80s |
| `longcat-flash-lite/messages` | 3 | 2 | 2 | 2 | 2 | 2.21s |
| `gpt-oss-20b/messages` | 3 | 3 | 2 | 2 | 2 | 8.45s |

判断：

- elysiver 的低价快模型适合做 cheap pre-screen，但暂时不适合做最终交易规则确认。
- `responses` 在 elysiver 基本不可用，常见错误是只允许 `openai_chat` 或 not implemented。
- `messages` 格式有时比 `chat` 更快，但不是每个模型都稳。

## 5. 推荐路由

### 生产规则抽取 / 最终确认

1. `windhub` + `doubao-1-5-pro-32k-250115` + `messages`
2. 若 production client 暂不支持 `messages`，先用 `windhub` + `doubao-1-5-pro-32k-250115` + `chat`
3. 备用：`windhub` + `deepseek-v3-2-251201` + `chat`
4. Responses fallback：`windhub` + `deepseek-v3-2-251201` + `responses`

### 低成本预筛

暂不建议直接用于实盘确认。可进一步复测：

- `elysiver` + `longcat-flash-chat` + `chat`
- `elysiver` + `gpt-oss-120b` + `chat`
- `elysiver` + `llama3.1-8b` + `messages`

但它们目前没有达到 windhub 两个候选的多样本完美识别水平。

## 6. 对系统实现的影响

当前主生产客户端主要支持 OpenAI `chat` / `responses`。本实验发现最好的 windhub 路由是 `messages`，因此下一步应做：

1. 给 production LLM adapter 增加 `messages` mode。
2. 将主路由设为 `windhub doubao-1-5-pro-32k-250115 messages`。
3. 将 chat fallback 设为 `windhub doubao-1-5-pro-32k-250115 chat`。
4. 将兼容 fallback 设为 `windhub deepseek-v3-2-251201 chat`。
5. 将 responses fallback 只绑定 `windhub deepseek-v3-2-251201 responses`，不要继续把 responses 发给 elysiver。

