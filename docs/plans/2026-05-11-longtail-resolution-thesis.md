# 2026-05-11 长尾 + 规则细读 研究方案

本文件是下一阶段研究工作的规格说明（spec）。在与团队对齐 *待决问题* 一节之前，**不要把任意一节拆给 DS / 其他 agent 执行**。所有 I/O 契约、阈值、验收标准必须先定下来。

---

## 0. 一行话定位

> 在 Polymarket **长尾市场**上，用 LLM **深读 resolution criteria** 与 **市场关系网**，寻找 *公开主流市场上已经消失的、但在低流动性段尚未被定价的* 等价 / 蕴含 / 互斥 mispricing。

这是一个**研究**项目，不是一个交易项目。成功的标志是 *能复盘地证明 alpha 存在或不存在*，而不是赚到钱。$100 资金量在所有情况下都是研究工具，不是收益来源。

---

## 1. 这个方向为什么值得做（基于已有研究的证据）

下列事实**在方案中是常量**，不再讨论。研究素材来源在 §10。

### 1.1 主流套利已死

- **Anatomy of Polymarket** (arxiv 2603.03136)：YES+NO 套利半衰期从 2024 年初的数小时，到 2024 年 10 月已压到 **<1 分钟**。Kyle's λ 下降一个数量级。
- **NegRisk 主流组的 sum-of-YES <$1 套利**：已被专业团队提取 ~$39.6M（2024-04 至 2025-04），半衰期 <1 分钟。
- **JeremyWhittaker 的开源套利项目**：作者已公开放弃，理由是流动性。
- **结论**：盯 top markets 跑 taker arb 是已知亏钱行为。我们要避开。

### 1.2 长尾的客观事实

- ~12,000+ 活跃市场（2026-04）；63% 的短期市场过去 24h **零成交量**。
- 成交量集中：~63% 来自 0.23% 的钱包；Sports 39% + Politics 34% + Crypto 18% = ~90% 总量。
- 公开的"最低效区间"：**距离 resolution 30-14 天**（方向已知但概率未精确定价）。
- 长尾流动性差，但同时也是 *做市商不覆盖、HFT 不竞争* 的区域。

### 1.3 费用结构已变（必须更新代码）

Polymarket 2026 年起按 category 收 taker fee，公式 `rate × price × (1-price) × size`：

| Category | Taker rate |
|---|---|
| Crypto | 1.80% |
| Mentions | 1.56% |
| Economics | 1.50% |
| Culture | 1.25% |
| Weather | 1.25% |
| Finance / Politics / Tech | 1.00% |
| Sports | 0.75% |
| Geopolitics | 0% |

Maker 0%，且 maker 拿 100% rebate（pro-rata）。**当前代码 `fees.py` 只有单一 `fee_rate`，是错的。**

### 1.4 我们要做的事的反例：Théo

2024 年大选赚 $85M 的"法国鲸"的 edge 来自**定制 YouGov "neighbor effect" 民调**，不是 LLM 读文本。**任何 LLM-only 文本路线必须正面回答：我们为什么不需要定制数据？** 这个项目的回答是："我们不打主流市场，主流市场的 alpha 在数据；我们打长尾，长尾的 alpha 在覆盖与文本理解。"

### 1.5 LLM-readable edge 会衰减

Lopez-Lira（SSRN 4412788）：GPT 头条策略 Sharpe 在 3 年内从 6.54 → 1.22。任何文本 alpha 都不是常量；本方案必须有 **kill criteria**（§7）。

### 1.6 当前代码库已经有的（不要重做）

- `rule_discovery.py` + `openai_rules.py`：LLM 已经在批量发现 implication / mutex / equivalent / exhaustive / complement，输出 JSON。
- `watchlist.py`：已经支持 `min_liquidity` / `min_volume_24h` 硬阈值过滤，但**没有 tier 概念**。
- `cross_platform.py`：Polymarket↔Kalshi 匹配，**站内"同事件多市场"未做**。
- `description` 字段已经传给 LLM 作为 prompt 输入，但**没有结构化解析**。
- `backtest.py`：snapshot 级别 replay，**没有 train/test split**。
- `near_miss.py`：诊断报告齐全，含 "fee blocked" 分类。

---

## 2. 范围

### 2.1 In scope（做）

- T1: 长尾市场 tier 化筛选
- T2: Resolution Criteria Reader（结构化文本解析）
- T3: 站内"同事件多市场"检测
- T4: Rule discovery 评估管线（LLM-as-judge）
- 横切：fee 模型 category-aware 升级
- 横切：所有产出走 dry-run，不接 live execution

### 2.2 Out of scope（不做，理由见 §1）

- ❌ 时序套利 / A→B 滞后反应（速度战的弱化版，主流市场半衰期 <1 分钟，长尾事件少）
- ❌ 做市策略（$100 不够，且面临已知的 $0.10/次订单簿狙击攻击）
- ❌ Polymarket↔Kalshi 跨平台执行（Kalshi 美国居民限制，中国用户不可执行；但匹配数据可以保留作为研究信号）
- ❌ HFT / WebSocket 微秒级延迟优化
- ❌ Live execution（保持 dry-run）

### 2.3 Stretch（如果 T1-T4 提前完成才考虑）

- T5: 用 T2 + T3 的输出回流喂给 `rule_discovery`，看是否能提高发现率
- T6: 把发现的 mispricing 写成静态报告（D 数据产品化的最小验证版本）

---

## 3. 架构：新模块怎么嵌入现有管线

```
                  ┌──────────────────────┐
                  │  Gamma raw markets   │
                  └──────────┬───────────┘
                             ▼
              ┌──────────────────────────────┐
              │  T1: longtail tier filter    │  → watchlist-longtail.json
              │  (extends watchlist.py)      │
              └──────────┬───────────────────┘
                         ▼
              ┌──────────────────────────────┐
              │  T2: resolution_reader       │  → resolution-clauses.ndjson
              │  (new module)                │     (per market: {market_id,
              │                              │       deterministic_clauses,
              │                              │       date_anchors, sources,
              │                              │       ambiguity_score})
              └──────────┬───────────────────┘
                         ▼
              ┌──────────────────────────────┐
              │  T3: same_event_detector     │  → internal-equivalence.json
              │  (new, complements           │     (per pair/group:
              │   cross_platform.py)         │       {market_ids, relation_type,
              │                              │        evidence, confidence})
              └──────────┬───────────────────┘
                         ▼
              ┌──────────────────────────────┐
              │  rule_discovery.py           │  ← 现有，T2/T3 输出作为
              │  (extended context)          │     额外 context
              └──────────┬───────────────────┘
                         ▼
              ┌──────────────────────────────┐
              │  T4: rule_eval harness       │  → rule-eval-report.json
              │  (new, LLM-as-judge +        │     (per rule: balanced_acc,
              │   人工 ground truth)         │      youden_j, self_consist)
              └──────────────────────────────┘
                         │
                         ▼
                    （现有 backtest / paper / near_miss 不变）
```

新增的代码文件预计：
- `poly_strategy/longtail.py`（T1）
- `poly_strategy/resolution_reader.py`（T2）
- `poly_strategy/same_event_detector.py`（T3）
- `poly_strategy/rule_eval.py`（T4）
- `poly_strategy/fees.py`（修改，category-aware）
- `tests/test_longtail.py`、`tests/test_resolution_reader.py`、`tests/test_same_event_detector.py`、`tests/test_rule_eval.py`

---

## 4. 工作流详细规格

每个工作流必须包含：输入、输出 schema、关键决策、验收标准、依赖、人工标注负担。

### T1. 长尾市场 Tier 化筛选

**目标**：把当前"硬阈值过滤"升级成"分 tier"。让下游知道一个市场是"主流-中间-长尾"中的哪一档。

**输入**：
- Gamma raw NDJSON（已有）
- 当前 watchlist 配置

**输出**：`data/watchlist-longtail.json`
```json
{
  "version": 1,
  "generated_at": "ISO8601",
  "tiers": {
    "headline": {"market_ids": [...], "criteria": {...}},
    "mid": {"market_ids": [...], "criteria": {...}},
    "longtail": {"market_ids": [...], "criteria": {...}},
    "dead": {"market_ids": [...], "criteria": {...}}
  },
  "stats": {
    "headline_count": N1, "mid_count": N2,
    "longtail_count": N3, "dead_count": N4
  }
}
```

**Tier 定义（待团队讨论确认，初稿）**：

| Tier | 24h 量 | 7d 量 | spread | 距离 resolution |
|---|---|---|---|---|
| headline | ≥ $50k | ≥ $200k | ≤ 1¢ | 任意 |
| mid | $5k-$50k | $20k-$200k | 1-3¢ | 任意 |
| **longtail** | $100-$5k | $1k-$20k | 3-10¢ | **14-90 天**（我们的研究区间） |
| dead | < $100 | < $1k | > 10¢ 或无 quote | 任意 |

**关键决策**：
- 阈值不能从 Dune 抄（Paradigm 2025-12 报告了 ~2x 双重计算问题）。必须从原始 Gamma `volume`/`volume24hr` 字段直接计算。
- "距离 resolution"是 longtail 定义的关键 —— 30-14 天是已知效率最低区间。
- `dead` tier 不进入下游研究，但保留 ID 供日后回看。

**实现要点**：
- 复用 `watchlist.py` 的 priority_score 思路，但输出是 tier 而非排序。
- 不修改 `watchlist.py` 主流程；新建 `longtail.py` 调用 watchlist 的工具函数。

**验收标准**：
- [ ] 在一个固定日期的 Gamma 快照上跑出四档划分。
- [ ] 四档计数符合预期数量级（longtail 应 ≥ 1000 个市场，dead 应 ≥ 7000 个）。
- [ ] 单元测试覆盖每个阈值边界。
- [ ] 输出可被 `build-watchlist` CLI 命令读取，作为新的 `--tier longtail` 选项。

**人工成本**：阈值校准（半天讨论）+ 实现（1 天）+ 测试（半天）。

---

### T2. Resolution Criteria Reader

**目标**：把 `description` 字段从"非结构化字符串塞进 prompt"升级成"结构化解析"。这是当前系统**最大的盲区**。

**输入**：
- 一个 market_id 的 Gamma 完整记录（`question` + `description` + `endDate` + `outcomes`）

**输出**：`data/resolution-clauses.ndjson`（每行一条）
```json
{
  "market_id": "...",
  "version": 1,
  "extracted_at": "ISO8601",
  "model": "claude-haiku-4-5-20251001",
  "deterministic_clauses": [
    {
      "type": "deadline | source | tiebreaker | exclusion | numeric_threshold",
      "text": "原文引用",
      "parsed": {
        "deadline": "ISO8601 | null",
        "source_url": "...",
        "source_authority": "official | self_reported | media",
        "trigger": "..."
      },
      "confidence": 0.0-1.0
    }
  ],
  "date_anchors": [{"text": "...", "iso": "...", "tz_explicit": true/false}],
  "sources": [{"text": "...", "url": "..."}],
  "ambiguity_flags": ["tz_unspecified", "subjective_term", "multiple_sources", "soft_language"],
  "ambiguity_score": 0.0-1.0,
  "soft_language_terms": ["officially", "publicly", "by [date]", ...]
}
```

**关键决策**：

1. **模型选择**：Haiku 4.5 用作主要提取器（成本低、文本任务足够），Sonnet 4.6 用作 ambiguity 高时的二次复核。**不要用 Opus**，单价不合算。
2. **prompt 设计**：单次提取必须包含 examples。先用 5 个手标的 markets 做 few-shot。
3. **缓存**：以 `(market_id, description_hash)` 为 key 缓存到 SQLite 或 NDJSON。description 一旦变化就重新提取。
4. **ambiguity_score 怎么算**：含 "officially"/"publicly"/"by [date]"/"announced" 等 soft language → +0.2 each；含未明确时区的日期 → +0.3；多个 source URL → +0.2；clip 到 [0,1]。
5. **不假设有 `resolution_criteria` 字段**：Polymarket 没有独立字段，规则文本就在 `description` 里。

**关键风险**：

- **UMA 治理风险（arxiv 2603.03136 已记录的 Ukraine $7M 案）**：被一个 ~25% 投票权的鲸鱼翻盘。**ambiguity_score 高的市场，要在交易层独立打 risk flag**，提示 "UMA outcome 可能与文本理解相反"。
- **LLM 提取本身有误**：必须有人工抽检（见 T4）。

**验收标准**：
- [ ] 在 100 个手选的 longtail markets 上提取 deterministic_clauses，人工标注 20 个作 ground truth。
- [ ] Precision ≥ 0.85, Recall ≥ 0.70（balanced，不是 F1）。
- [ ] 单条提取 cost ≤ $0.005。
- [ ] 提取时间 < 5 秒/市场（单线程）。
- [ ] 缓存命中率 ≥ 90%（同一 description 不重复调用）。

**人工成本**：
- prompt 设计 + few-shot 例子：1 天
- 实现 + 缓存：1.5 天
- 标注 20 个 ground truth：半天
- 测试 + 调优：1 天

---

### T3. 站内"同事件多市场"检测

**目标**：发现 Polymarket 站内被切成多个市场的同一事件，找出 equivalence / implication / partition 关系。这是 `cross_platform.py` 的站内版。

**输入**：
- T1 输出的 longtail + mid tier 市场列表
- T2 输出的 resolution-clauses
- Gamma raw 数据

**输出**：`data/internal-equivalence.json`
```json
{
  "version": 1,
  "generated_at": "ISO8601",
  "pairs": [
    {
      "market_ids": ["a", "b"],
      "relation": "equivalent | implies_ab | implies_ba | mutex | partition",
      "evidence": {
        "shared_event_id": "...",
        "shared_date_anchor": "...",
        "shared_source": "...",
        "neg_risk_group_id": "..."
      },
      "embedding_similarity": 0.0-1.0,
      "llm_confidence": 0.0-1.0,
      "deterministic": true/false
    }
  ],
  "groups": [
    {
      "market_ids": ["a", "b", "c"],
      "relation": "partition_of_event",
      "event_id": "...",
      "yes_sum_expected": 1.0
    }
  ]
}
```

**算法（三层）**：

1. **Deterministic layer（最便宜，最先跑）**：
   - 同 `neg_risk_market_id` → partition_of_event（确定）
   - 同 `event_id` 且 `outcomes` 互斥 → mutex（确定）
   - `question` 文本完全相同且 `end_date` 相同 → equivalent（确定）

2. **Embedding layer（候选生成）**：
   - 对 `question + description` 提 embedding（OpenAI `text-embedding-3-small`，便宜）
   - cosine similarity ≥ 0.85 的进入候选池
   - **这步替代了 `cross_platform.py` 的 Jaccard**，是 §B1 路径的核心改进

3. **LLM 验证层（最贵，最后跑）**：
   - 对候选 pair 用 LLM 做语义验证
   - prompt 必须包含 T2 提取的 deterministic_clauses（让 LLM 看到结构化规则而非裸文本）
   - 输出 relation type + confidence + 简短理由

**关键决策**：
- Embedding 阈值 0.85 是初稿，必须在 100 对人工标注上调优。
- LLM 验证只跑 deterministic 没覆盖的对，节省成本。
- 输出必须能被现有 `rule_discovery` 当作额外 context 消费（schema 兼容 `DiscoveryResult`）。

**验收标准**：
- [ ] 在 longtail tier 上跑出至少 200 个候选 pairs。
- [ ] 人工抽检 50 对，precision ≥ 0.80。
- [ ] 跑一次完整长尾的总成本 ≤ $5（embedding + LLM）。
- [ ] 输出与 `rule_discovery.write_discovered_rules` 的 schema 兼容（或提供适配器）。

**人工成本**：
- 实现 deterministic 层：半天
- 实现 embedding 层 + 缓存：1 天
- 实现 LLM 验证层：1 天
- 标注 50 对 ground truth：1 天
- 测试 + 调优：1 天

---

### T4. Rule Discovery 评估管线（LLM-as-judge）

**目标**：当前 rule_discovery 没有 evaluation harness。我们需要一个独立的评估管线来回答："这个 rule_set 的 precision/recall 到底是多少？"

**输入**：
- 现有 `rules/*.json`（rule_discovery 的输出）
- T2 的 resolution-clauses
- 人工标注的 ground truth subset

**输出**：`data/rule-eval-report.json`
```json
{
  "version": 1,
  "evaluated_at": "ISO8601",
  "ruleset_path": "...",
  "ground_truth_size": N,
  "metrics": {
    "precision": 0.0-1.0,
    "recall": 0.0-1.0,
    "balanced_accuracy": 0.0-1.0,
    "youden_j": -1.0 to 1.0,
    "self_consistency": 0.0-1.0
  },
  "per_relation_type": {
    "implication": {...},
    "mutex": {...},
    "equivalent": {...}
  },
  "judge_ensemble": {
    "models": ["claude-haiku-4-5", "claude-sonnet-4-6", "gpt-4o-mini"],
    "agreement_rate": 0.0-1.0
  },
  "failures": [{"rule_id": "...", "judge_said": "...", "truth": "...", "why": "..."}]
}
```

**关键方法论决策（基于研究素材 §10.5）**：

1. **不报 F1**：F1 受 prevalence 影响，对二分类不可靠。报 **balanced accuracy** 和 **Youden's J**（arxiv 2512.08121）。
2. **判官集成**：单 LLM judge 不可信（arxiv 2512.16041 的 Intra-Pair Instability 数据）。**集成至少 3 个模型** —— Haiku、Sonnet、加一个外部供应商如 gpt-4o-mini —— 取多数票。
3. **Self-consistency**：每条规则被 judge 3 次（temperature 0.3），看一致率。一致率 <0.8 的规则标 "unstable"。
4. **Ground truth 怎么来**：
   - 100 条规则人工标注（团队 4 人，每人 25 条，1-2 天）
   - 标注协议：每条 rule = (market_a, market_b, relation_type)，标 `correct / wrong / ambiguous`
   - 至少有 2 人独立标注同一条；冲突时讨论
5. **避免污染**：评估时 judge 看不到 rule_discovery 的原 prompt（防止判官重复同样的错）。

**验收标准**：
- [ ] 在 100 条 ground truth 上跑完评估。
- [ ] 报告含 balanced accuracy、Youden's J、judge ensemble 一致率。
- [ ] 失败样本能逐条追溯 to (market_a, market_b, judge_reasoning)。
- [ ] 报告能在 CLI `poly-strategy rule-eval --rules rules.json` 上一行命令重跑。

**人工成本**：
- 标注协议设计：半天
- 人工标注 100 条：2 天（4 人 × 半天）
- 实现 + judge ensemble：2 天
- 测试 + 报告：1 天

---

### 横切 1: Fee 模型 Category-Aware 升级

**为什么必须做**：Polymarket 2026 起 fee 是 category 阶梯（§1.3）。当前 `fees.py` 只有单一 `fee_rate`，意味着我们的 backtest **系统性高估了 Geopolitics 边缘、低估了 Crypto 边缘**。

**改动范围**：
- `poly_strategy/fees.py`：增加 `category_taker_rate(category: str) -> float`，硬编码当前阶梯。
- `taker_fee_per_share` 签名增加可选 `category` 参数。
- `scanner.py` 调用处补传 category。
- `models.py` 的 `BinaryMarketSnapshot` 增加 `category` 字段。
- 数据收集 (`collectors.py`) 从 Gamma 抽出 category 字段写入快照。

**注意**：
- Maker 0% + 100% rebate。**maker.py 也需要更新**（如果未来用 maker 路径）。
- 阶梯有可能再变（参考 2026-04 的回退事件）。把阶梯写在 **一个常量字典里**，留 TODO 注释指向文档 URL。

**验收**：
- [ ] 单元测试覆盖每个 category 的 fee 计算。
- [ ] 现有 backtest 数据重跑，对比新旧 fee 模型下的 opportunity 数量差异，写入 release notes。

**人工成本**：1 天。

---

### 横切 2: 资源预算

**API 成本估算**（一次完整跑）：

| 项目 | 单价 | 数量 | 小计 |
|---|---|---|---|
| T2 resolution_reader (Haiku) | ~$0.003/市场 | 2000 | $6 |
| T2 ambiguity 复核 (Sonnet) | ~$0.02/市场 | 200 | $4 |
| T3 embedding (text-embedding-3-small) | $0.00002/1k token | ~10M token | $0.20 |
| T3 LLM 验证 (Haiku) | ~$0.004/对 | 500 | $2 |
| T4 judge ensemble | ~$0.015/规则 × 3 | 100 × 3 | $4.50 |
| **合计单次完整跑** | | | **~$17** |

每月跑 4 次 ≈ **$70**。可控。

**人工时间预算**（4 人团队，假设每人每周可投入 10 小时）：

| 任务 | 工时 | 分配 |
|---|---|---|
| 阈值/协议讨论 | 4h | 全员 |
| T1 longtail | 16h | 1 人 |
| T2 resolution_reader | 32h | 1 人 |
| T3 same_event_detector | 32h | 1 人 |
| T4 rule_eval | 28h | 1 人 |
| 横切 fees | 8h | 1 人（兼） |
| 人工标注 | 16h | 全员 |
| **小计** | **~136h** | **约 3-4 周** |

---

## 5. 验证 / Dry-run 协议

1. **每个工作流必须有独立测试**，不依赖其他工作流即可跑通（用 fixture）。
2. **集成验证**：T1 → T2 → T3 → rule_discovery → T4 在一份固定 Gamma 快照上端到端跑通。
3. **回测对比**：用新的 rule_set + 新的 fee 模型，在过去 30 天的 snapshot NDJSON 上重跑 `backtest`，对比旧 baseline 的 opportunity 数 / fee_blocked 数。
4. **Live 上线条件**：**不上线**。所有产出走 `paper.py` 和 near_miss 报告，不接 `execution.py` 的 live 路径。

---

## 6. 决策门（Decision Gates）

| Gate | 何时 | 通过条件 | 不通过则 |
|---|---|---|---|
| G1: 阈值确认 | 启动前 | T1 tier 阈值 4 人达成一致 | 重新讨论或推迟 |
| G2: T2 ground truth | T2 完工时 | 在 20 条标注上 precision ≥ 0.85 | 调 prompt 重做，最多 2 轮 |
| G3: T3 ground truth | T3 完工时 | 在 50 对标注上 precision ≥ 0.80 | 调 embedding 阈值 + LLM prompt |
| G4: T4 报告 | T4 完工时 | 跑通 100 条评估，judge ensemble 一致率 ≥ 0.70 | 增加 judge 数量或换模型 |
| G5: 集成 | 所有完工后 | 端到端在固定快照上跑通，无 crash | 修 bug |
| G6: 回测对比 | G5 后 | 新管线找到的"high-confidence longtail mispricing"数 > 0 | 见 §7 kill criteria |

---

## 7. Kill Criteria（什么时候放弃）

基于 Lopez-Lira 的衰减证据，必须明确何时承认无 alpha。

**杀死整个 thesis 的条件**：
- G6 在长尾上找到 **0 个** high-confidence mispricing（balanced accuracy ≥ 0.85 的 rule，且 net edge > fee + 2σ slippage）。
- 或者：找到了 mispricing，但放进 30 天历史 snapshot replay 时，**0 笔** paper trade 能赚钱。

**降级条件（不杀死，转方向）**：
- T2 precision <0.85 但 >0.70 → 降级为辅助信号，不作为主要 rule 来源。
- T3 在长尾上候选 <50 对 → 长尾"同事件多市场"假设不成立，关闭这个子项目。
- T4 judge ensemble 一致率 <0.50 → LLM-as-judge 不可用，必须人工标注更多，研究规模收缩。

**杀死后的归宿**：项目转 D 路径（数据产品化 / 学术输出），保留代码作为研究框架。

---

## 8. 风险清单

| # | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| R1 | UMA 治理 attack（如 Ukraine $7M 案）：文本理解正确但被鲸鱼翻盘 | 低-中 | 高 | T2 输出的 ambiguity_score 高的市场，下游强制打 "uma_risk" flag，不进入 paper trade |
| R2 | LLM 提取错误，rule_discovery 喂了脏数据 | 中 | 中 | T4 ensemble judge + 人工抽检 |
| R3 | Polymarket 改 fee 阶梯，代码常量过期 | 中 | 低 | 常量集中放在一个 dict，TODO 注释定期复查 |
| R4 | LLM 提取成本超预算 | 低 | 低 | 缓存 + 阶梯（Haiku 主跑、Sonnet 复核） |
| R5 | 长尾市场 quote 太陈旧，回测不可信 | 中 | 中 | 在 backtest 加 "quote_age < 5 min" 过滤；记录 quote 时效分布 |
| R6 | 人工标注疲劳，质量下降 | 中 | 高 | 4 人分担，至少 2 人独立标，冲突讨论 |
| R7 | 我们的 alpha 衰减（Lopez-Lira 模式） | 高 | 高 | §7 kill criteria；T4 每 2 周重评 |
| R8 | 项目变成"沉没成本无底洞" | 中 | 高 | 决策门 + kill criteria 是硬性的 |
| R9 | Polymarket 中国 IP / KYC 政策变化 | 低 | 中 | dry-run 不受影响，研究价值不变 |

---

## 9. 待决问题（讨论后填入）

启动前必须 4 人达成一致：

1. **T1 阈值**：上表初稿的数字（$50k/$5k/$100、1¢/3¢/10¢、14-90 天）是否合理？是否需要先看 1 周 Gamma 实际分布再定？
2. **T2 模型选择**：Haiku 主跑 + Sonnet 复核，是否同意？还是想试 DeepSeek？
3. **T3 embedding 模型**：`text-embedding-3-small` 还是开源 sentence-transformers（免费但要本地跑）？
4. **T4 人工标注分工**：100 条规则 4 人分，每人 25 条？标注协议（correct / wrong / ambiguous）够不够细？是否要加 "confidence" 字段？
5. **代码 review 流程**：每个工作流完工后，PR review by 谁？merge 标准？
6. **DS 拆解方式**：每个 T 是一个 DS 指令包？还是更细？（建议：T1 一个包，T2/T3/T4 各拆成"实现 + 测试 + 验证"3 个子包，共 10 个 DS 包）
7. **Cadence**：每周固定时间同步进度？每两周重审 kill criteria？
8. **失败/暂停的标志写在哪**：放在 issue tracker 还是这个文档里 append？

---

## 10. 研究素材引用（决策依据）

本方案的关键事实出自以下来源。每条决策的依据必须可追溯。

### 学术
- **Anatomy of Polymarket: 2024 Presidential Election** — arxiv 2603.03136
  - YES+NO 套利半衰期 <1 分钟（§1.1, §2.2）
- **The Microstructure of Wealth Transfer in Prediction Markets** — Becker
  - 长尾 takers 系统性输给 makers ~57%（§1.2）
- **Unravelling the Probabilistic Forest** — arxiv 2508.03474
  - NegRisk 结构性套利已被职业捕获（§1.1）
- **PolySwarm: Multi-Agent LLM Framework** — arxiv 2604.03888
  - 最接近的 LLM 驱动预测市场前作（§3 架构参考）
- **Lead-Lag Trading with LLM** — arxiv 2602.07048
  - LLM 贡献主要在损失管理而非信号（影响 §7 kill criteria）
- **Can ChatGPT Forecast Stock Price Movements** — SSRN 4412788
  - LLM 头条策略 3 年 Sharpe 6.54→1.22（§1.5）
- **Survey on LLM-as-a-Judge** — arxiv 2411.15594
- **Balanced Accuracy for LLM Judges** — arxiv 2512.08121（§T4 metric 选择）
- **Are We on the Right Way to Assessing LLM-as-a-Judge** — arxiv 2512.16041

### 行业 / Polymarket 官方
- **Polymarket fee schedule** — help.polymarket.com/articles/13364478（§1.3）
- **Polymarket API docs** — docs.polymarket.com（§3 接入）
- **NegRisk CTF Adapter** — github.com/Polymarket/neg-risk-ctf-adapter
- **Paradigm: Polymarket Volume Double-Counted (Dec 2025)** — paradigm.xyz/2025/12（§T1 阈值警告）

### 长尾流动性
- **PANews 290k market analysis** — 63% 短期市场零成交（§1.2）
- **tradetheoutcome 2026** — Sports 39% + Politics 34% + Crypto 18%（§1.2）

### 反例
- **The French Whale / Théo** — thefp.com（§1.4）
- **JeremyWhittaker/Polymarket_arbitrage** — github 开源套利项目，作者因流动性放弃（§1.1）
- **Ukraine $7M mineral deal UMA 案** — 2025-03-25 治理 attack（§8 R1）

### 公开 dashboards（用于验证 §T1 阈值）
- dune.com/rchen8/polymarket
- dune.com/filarm/polymarket-activity
- predictions.paradigm.xyz

---

## 11. 给 DS 的指令包格式（执行阶段才用）

**Gate G1 通过后**，把每个工作流拆成 DS 指令包。模板：

```
任务：T2.1 实现 resolution_reader（提取层）

读取以下文件：
- docs/plans/2026-05-11-longtail-resolution-thesis.md §4 T2
- poly_strategy/rule_discovery.py（参考现有 LLM 调用方式）
- poly_strategy/models.py（schema 风格）

实现：
- 新建 poly_strategy/resolution_reader.py
- 公开函数：extract_clauses(market: MarketText, model: str = "claude-haiku-4-5-20251001") -> ResolutionClauses
- 输出 schema 严格按 §4 T2 中的 JSON 定义
- 缓存以 (market_id, sha256(description)) 为 key，写入 data/.cache/resolution-clauses/<hash>.json

不要：
- 不要修改 watchlist.py
- 不要修改 rule_discovery.py
- 不要接入 live execution
- 不要自己设计输出 schema（必须严格匹配文档）

测试：
- 新建 tests/test_resolution_reader.py
- mock LLM 响应，验证 schema 解析
- 至少 5 个测试 case：deadline / source / tiebreaker / soft_language / pure_question

完成定义：
- pytest 通过
- mypy 通过
- 在 5 个真实长尾 market description 上手工调用并贴 5 个示例输出到 PR 描述
```

每个包都必须：(a) 显式指向本文档某一节，(b) 列出"不要做"清单，(c) 完成定义（DoD）必须可机器验证。

---

## 12. 文档维护

- 本文档是 **planning 文档**，不是 changelog。完工的 T 标记 `[Done]` 但保留章节。
- 决策门（§6）和 kill criteria（§7）触发时，append 日期 + 结论到对应章节末尾。
- 启动后两周如果仍未确认 §9 待决问题，**自动触发 G1 失败**，回到讨论。

---

*起草日期：2026-05-11*
*下一次必须更新：§9 全部决定后，作为 v1.0 正式生效。*
