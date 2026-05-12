# §9 快速决议稿（2026-05-12）

**关联文档**：[`2026-05-11-longtail-thesis-open-questions.md`](./2026-05-11-longtail-thesis-open-questions.md)

**目的**：长尾 thesis Gate G1 要 8 个 Decision 全部填入才能开干。除 Q1 外，其余 7 个问题用"默认建议 + 一个替代"形式，方便同学快速回复 yes / swap to alt / 提新方案。

**前提调整**：原方案 §G1 写"4 人书面确认"。实际**团队只有 2 人**，G1 改为"两人都点头"。本稿里凡涉及人数的问题都按 2 人重新算过。

---

## Q1. T1 长尾 tier 阈值

**建议**：**等数据**。先用 DS pkg #02 拉一周 Gamma 实际分布，看百分位再定。本稿初稿数字（$50k/$5k/$100、1¢/3¢/10¢、14-90 天）只作为 placeholder，DS pkg #02 跑完后基于实际分布调整。

**替代**：现在直接拍板初稿数字，后续如果数据严重不符再改。

**Decision**: ⏳ 等数据

---

## Q2. T2 模型选择（Resolution Reader）

**建议**：Claude **Haiku 4.5 主跑** + **Sonnet 4.6** 在 ambiguity_score 高时复核。**不引入 DeepSeek 做 T2 文本提取**——T2 输出必须严格 JSON schema，Claude 家族在 schema 遵循上更稳。DeepSeek 仍然是"DS 写代码"的执行者，但不充当 T2 的提取器。

**替代**：在 T2 prompt 调优阶段（前 50 个市场）跑 head-to-head Haiku vs DeepSeek，再决定主跑模型。代价：多花 ~$3 + 半天。

**Decision**: ___

---

## Q3. T3 Embedding 模型

**建议**：OpenAI **`text-embedding-3-small`**。复用项目现有 OpenAI key（已经在 rule_discovery 用）。相似度阈值 0.85 作为初稿，**等 50 对人工标注完成后再调**（这步在 T3 实施阶段做，不阻塞 G1）。

**替代**：本地跑开源 `BAAI/bge-large-en-v1.5`（免费但要 GPU/CPU 资源和封装时间）。

**Decision**: ___

---

## Q4. T4 人工标注分工（团队 2 人，必须重算）

**建议**：每条规则需要 2 人独立标注，所以总标注份数 = 规则数 × 2。**2 人团队 × 每人 50 份 = 100 份 = 覆盖 50 条规则双标**。

把 T4 样本量从 100 条降到 **50 条**。分层：implication 15 + mutex 15 + equivalent 10 + exhaustive 5 + complement 5。标签集保留 `correct / wrong / ambiguous`，**不加 confidence 字段**（增加成本不增加可靠性，因为只有 2 人时 confidence 校准困难）。标注工具：**shared NDJSON 文件**，本地用 CLI helper 写入；不搭 web 工具，太重。

**替代**：保留 100 条规则样本，分两阶段标 —— 先 50 条（每人 50 份）跑通流程，再做后 50 条。代价：拖 1-2 天，但能拿到更高样本量。

**Decision**: ___

---

## Q5. 代码 review 流程（2 人团队）

**建议**：每个 PR 由**另一人 review + Claude 做 sanity check**。Merge 标准：CI 通过 + 对方 approve + Gate（如适用）通过。**24 小时内对方没响应**则作者可以自合并，但要在 PR 描述里标注。任一人都可 merge。

**替代**：所有 PR 必须双 approve，没人 approve 就不 merge。代价：节奏被任一人的可用时间卡住。

**Decision**: ___

---

## Q6. DS 指令包拆解粒度

**建议**：**一个工作流（T1/T2/T3/T4）一个 DS 包**。如果某包代码量超过 300 行，再拆"实现 + 测试"两子包。横切任务（如 fee schedule #01）独立成包。**总包数估计 5-7 个**。spec 作者负责拆解和分发，DS 跑回的代码由两人都 review。

**替代**：每 T 都拆成"实现 + 测试 + 验证"三子包，共 ~12 个包。代价：协调成本变高，但每个 PR 更小更好 review。

**Decision**: ___

---

## Q7. 节奏与同步

**建议**：**每周一晚 30 分钟同步**（讨论上周进度 + 本周计划）。**每两周复审 kill criteria（§7）**。**Gate 失败**触发 48 小时内开会决定走或留。其他时间纯异步（PR + 微信）。

**替代**：完全异步，没固定会议；只在 Gate 触发时开会。代价：节奏放松，可能拖。

**Decision**: ___

---

## Q8. 失败 / 暂停的记录方式

**建议**：**直接 append 到主方案对应章节末尾**，格式 `> 2026-XX-XX 决议: ...（决议者）`。**不**单独建 `decisions-log.md`（一个事实一处记，避免分散）。**不**用 GitHub Issues（太噪）。

**替代**：建独立的 `decisions-log.md`，所有 Gate 决议集中。代价：多一个文件维护，但搜起来方便。

**Decision**: ___

---

## 决议后处理

7 个 Decision 填入 + Q1 等数据这件事达成共识 → 视为 **Gate G1 通过的预备态**。Q1 数据到位后追加该 Decision，G1 正式通过，进入 T1-T4 实施。

我（Claude）负责：
- 收到决议后把答案同步回主方案（升 v1.0）
- 把 §G1 中的"4 人确认"改为"两人确认"
- 按 Q6 决议的粒度起草后续 DS 指令包

---

*起草：2026-05-12*
*目标：本周内（2026-05-17 前）拿到 7 个 Decision*
