# 待决问题：长尾 + 规则细读方案 (v0.1)

**关联文档**：[`2026-05-11-longtail-resolution-thesis.md`](./2026-05-11-longtail-resolution-thesis.md)

本文件是该方案 §9 的独立讨论稿，供团队评论和决议。每条问题下方留 `**Decision:**` 一行；讨论收敛后填入，并同步更新主方案至 v1.0。

讨论方式：在本 PR 上对每条问题做评论。**Gate G1 通过条件**：8 条 Decision 全部填入，4 人书面确认。

---

## Q1. T1 长尾 Tier 阈值

主方案初稿：

| Tier | 24h 量 | 7d 量 | spread | 距离 resolution |
|---|---|---|---|---|
| headline | ≥ $50k | ≥ $200k | ≤ 1¢ | 任意 |
| mid | $5k-$50k | $20k-$200k | 1-3¢ | 任意 |
| longtail | $100-$5k | $1k-$20k | 3-10¢ | 14-90 天 |
| dead | < $100 | < $1k | > 10¢ | 任意 |

**问题**：
- 数字是否合理？还是应该先拉一周 Gamma 实际分布数据，看百分位数后再定？
- "距离 resolution 14-90 天" 是基于学术文献的 30-14 天最低效区间，但我们放宽到 14-90 天保留更多样本。这个范围对吗？
- 是否需要单独区分 neg-risk 子市场 tier（neg-risk 整组可能流动性好，但单个子市场长尾）？

**Decision:**

---

## Q2. T2 模型选择

主方案初稿：Haiku 4.5 主跑（提取），Sonnet 4.6 在 ambiguity 高时复核。

**问题**：
- 同意这个分层吗？
- 是否试 DeepSeek？理由：成本可能更低，且当前项目本来就是 DS 帮我们干活的语境。代价：英文金融文本理解 vs Claude 系列的对比未知。
- 是否需要在 prompt 调优阶段双跑（Haiku + DeepSeek）做 head-to-head 对比，再决定主跑？

**Decision:**

---

## Q3. T3 Embedding 模型

主方案初稿：OpenAI `text-embedding-3-small`（$0.00002/1k token，预算 ~$0.20 单次完整跑）。

**问题**：
- 用 OpenAI 还是开源 `sentence-transformers`（如 `BAAI/bge-large-en-v1.5`）？开源免费但要本地跑 + GPU/CPU 资源。
- 如果用 OpenAI，需要给项目加一个 OpenAI key 配置（当前 key 是给 rule_discovery 用的，复用即可）—— 确认这个复用没问题。
- Embedding 相似度阈值 0.85 是初稿，是否同意"用 100 对人工标注后再调"的流程？

**Decision:**

---

## Q4. T4 人工标注分工

主方案初稿：100 条规则，4 人各 25 条，至少 2 人独立标注同一条，冲突讨论。标签集：`correct / wrong / ambiguous`。

**问题**：
- 4 × 25 的分配 OK 吗？
- 100 条规则的样本怎么选？（建议：从现有 rule_discovery 输出里分层抽样 —— implication 30 + mutex 30 + equivalent 20 + exhaustive 10 + complement 10）
- 标签集是否需要加 `confidence`（high / medium / low）字段？这会增加标注时间但提供更细信息。
- 标注工具：直接编辑一个共享 NDJSON / Google Sheets / 还是搭一个最简单的 web 标注页面？

**Decision:**

---

## Q5. 代码 Review 流程

**问题**：
- 每个工作流（T1/T2/T3/T4）完工后，PR 由谁 review？建议：作者之外的至少 1 人 + 我（Claude）做最后 sanity check。
- Merge 标准：CI 通过 + 1 个 human review + Gate（G2/G3/G4）通过？
- 谁负责 merge 到 main？

**Decision:**

---

## Q6. DS 指令包拆解粒度

主方案初稿：每个 T 拆成 "实现 + 测试 + 验证" 3 个子包，共 ~10 个 DS 包。

**问题**：
- 同意这个粒度吗？还是想更细（如每个 prompt 设计单独成包）/ 更粗（一个 T 一个包）？
- 谁负责把 §11 模板填充成具体 DS 指令包并发送？
- DS 跑回的代码谁来 review？是否每个包都需要人工审一遍再 merge？

**Decision:**

---

## Q7. 节奏与同步

**问题**：
- 每周固定时间同步进度？建议：每周一晚 30 分钟站会。
- 每两周重审 kill criteria（§7）？
- 出现 Gate 失败时多久内开会决定走或留？

**Decision:**

---

## Q8. 失败 / 暂停的记录方式

**问题**：
- Kill criteria 触发或 Gate 失败时，结论写在哪？建议：直接 append 到主方案对应章节末尾，标注日期 + 决议者。
- 是否需要单独的 `decisions-log.md` 追踪所有 Gate 决议？
- 还是放进 GitHub Issues 用 label 管理？

**Decision:**

---

## 决议后处理

8 条 Decision 全部填入后：

1. 我（Claude）把决议同步到主方案 `2026-05-11-longtail-resolution-thesis.md`，版本号从 v0.1 升到 v1.0。
2. 关闭本 PR（merge or close），但**保留本文件**作为决策记录。
3. 按 §11 模板把工作流拆成 DS 指令包，逐个发出。
4. 进入实施阶段，按 §6 决策门推进。

---

*起草：2026-05-11*
*目标决议日期：待团队约定（建议 1 周内）*
