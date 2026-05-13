# 长尾 Polymarket Thesis — 一日研究纪要（2026-05-12）

**作者**：Soli22de + Claude Opus 4.7（1M context）
**面向读者**：同学 WW（项目协作者）
**目的**：用一份文档把今天 ~8 小时实验全部沉淀下来，决定明天往哪走。

---

## TL;DR — 30 秒结论

1. **今天第一次回答了"有没有钱可赚"这个根本问题。答案是「有，但要会挑」**。
2. 在 06:13 UTC snapshot 上，2000 个活跃市场分到 151 个 neg-risk 组，其中：
   - **1 个高置信 strict 候选**（James Bond next 演员，含 *No one announced* 显式 catch-all，post-fee edge **+8.93%**，长尾区域）
   - **7 个 binary 候选**（state senate / governor D-vs-R 对决，edge 0.1–3.14%，需评估第三方风险）
   - **6 个 open-set 假阳性**（Nobel / Israel PM 等，名单不穷举，**不能交易**）
3. **方案 v0.1 里几乎所有量化假设都被实验推翻**：
   - 长尾 tier 阈值偏高 100× → 实测 vol24hr P50 只有 \$40
   - `spread` 字段误判不存在 → 实际在 raw Gamma payload 里
   - T4 corpus 需 \$5–10 跑 rule_discovery → 实际 0 LLM 调用从 neg-risk 结构白嫖 10,122 mutex pairs
   - `fees.py` 是错的 → 实际已经按市场级 `feeSchedule.rate` 工作（这条是你 2026-05-11 半夜帮我抓出来的）
4. **OpenRouter 路线打通了**，预算从 \$17/run → ~\$0.87/run（且 GLM 系列经 elysiver 可以零成本）。LLM 选型基本明朗：DeepSeek V3 / GLM-4.6 抽 substance 最深，Gemini 2.0 Flash 最便宜兜底，GPT-4o-mini 会 hallucinate 落地 URL，Llama 70B 不稳定。
5. **核心 thesis 没死**：长尾 neg-risk 确实存在 mispricing；但需要严格的 exhaustiveness 判定（开放命题里 sum_ask<1 是假信号），这恰好是 T2 (resolution_reader) + T3 (same_event_detector) 要做的事。

---

## 1. 今天到底做了什么（按时间）

| # | 实验 | 产出 | 看 |
|---|---|---|---|
| 1 | Gamma 分布 + 结构关系派生 | n=2000 真实数据，171 neg-risk 组，10,122 mutex pairs | `reports/experiment-gamma-distribution-2026-05-12.md` |
| 2 | OpenRouter Gemini Flash 校准 | 5/5 schema, 5/5 grounded，\$0.000214/call 实测 | `reports/experiment-openrouter-calibration-2026-05-12.md` |
| 3 | 4 模型 head-to-head | Gemini / DeepSeek V3 / GPT-4o-mini / Llama | `reports/experiment-multi-model-extraction-2026-05-12.md` |
| 4 | GLM-4.6 单模型（elysiver 免费） | 29/29 成功，clauses/市场 3.3（最高） | `reports/experiment-multi-model-results-glm-4-6-2026-05-12.md` |
| 5 | GLM-5 单模型（elysiver 免费） | 16/30 成功（quota/timeout），抽得最深 3.9 | `reports/experiment-multi-model-results-glm-5-2026-05-12.md` |
| 6 | （跳过的）deepseek-v4-pro + gpt-5.5-web-auto 全跑 | 仅 smoke test，未完整 30 markets | 我们判断本末倒置，跳过了 |
| 7 | **长尾 neg-risk mispricing 普查（v2 refined）** | **151 组分类 + 1 strict + 7 binary 候选** | `reports/experiment-negrisk-mispricing-2026-05-12.md` |

---

## 2. 实验 7 是今天最重要的发现

### 2.1 起源

到下午 4 点为止我一直在 polish 抽取管线：测模型、改 spec、修备忘。你（用户视角）一句"研究出了什么名堂吗"把我拉回来 —— 5 小时工作 0 个 alpha 验证。然后再问"这些信息到底有没有用"指出本末倒置。

实验 7 是直接回答 *thesis 能不能赚钱* 的最小测试：

```
拿 PR #7 派生的 171 个 neg-risk 组
   ↓
对每组 sum 所有 member 的 bestAsk
   ↓
计算 fee-adjusted basket cost
   ↓
edge = 1.0 - basket_cost
   ↓
edge > 0 的组 = 潜在 basket arb
```

成本：\$0（用现有 snapshot 数据），耗时：~15 分钟。

### 2.2 v1 跑出 51% 假阳性

第一版结果说：

> Nobel Peace Prize 2026 组：20 个候选人 sum_ask = 0.459，edge_after_fee = **+51.91%**

看着像免费 \$1。但 Nobel 委员会每年 200+ 提名，**Polymarket 这 20 个绝不是穷举的**。最可能的结果是「以上都不是」→ 所有 YES 归零 → 整篮亏 100%。

我 v1 的 `likely_exhaustive` 启发式是「size ≥ 8 → exhaustive」。在 Nobel 这种"开放命题"上完全错。

### 2.3 v2 用显式 catch-all 关键词正确分级

```python
EXHAUSTIVE_MARKERS = [
    "no one", "none of", "another candidate", "another team",
    "any other", "no candidate", "neither", "someone else",
    "no one announced", ...
]
```

三档：
- `explicit_other`：组内含 *No one wins* / *Another candidate* 等显式 member → **真 exhaustive**
- `binary`：恰好 2 个 member → 多数是 D/R 对决，**可能** exhaustive，但有第三方风险
- `open_set`：3+ member 且无 catch-all → **几乎确定不穷举**，basket sum<1 是假信号

### 2.4 v2 结果

```
151 总组 → 1 explicit / 73 binary / 77 open_set
14 组 edge_after_fee > 0
  - 1 strict 候选
  - 7 binary 候选
  - 6 open-set 假阳性（被正确剔除）
```

### 2.5 唯一的 Strict 候选 —— James Bond Next

`negRiskMarketID=0xb23e25438839…`，15 个 member：

| 候选演员 | bestAsk |
|---|---|
| Aaron Taylor-Johnson | 0.016 |
| Jacob Elordi | 0.037 |
| Callum Turner | 0.060 |
| Harris Dickinson | 0.011 |
| 其余 10 个演员 | 0.002–0.012 |
| **"No one announced as next James Bond"** | **0.730** ← 显式 catch-all |

- Sum = 0.893
- Fee total ≈ 0.018（5% feeRate × p(1-p)）
- **Post-fee edge = 1.0 - 0.893 - 0.018 = +0.089 (≈ 8.9%)**
- Min liquidity = \$2,210（长尾区域）

**为什么这是真信号**：
- "No one announced" 显式覆盖了 *没人被官宣* 的所有可能 → 真 exhaustive
- 14 个具体演员 + "No one" 的 disjunction 在逻辑上 = 全集
- 任意 resolution 都有恰好一个 YES → 基本工资稳定 \$1

**为什么不一定能吃到 8.9%**：
- bestAsk 只是 snapshot 时刻一瞬的最优挂单价，**后面挂多深不知道**
- 长尾 \$2,210 min liquidity 意味着大单会立刻 slippage 几个 cent
- 实际操作要用 CLOB `/book` 端点核对深度，可能 edge 砍到 3-5%

### 2.6 Binary 候选（7 个）

主要是州级选举 D-vs-R：

| 选举 | sum_ask | post-fee edge | 备注 |
|---|---|---|---|
| West Virginia Senate 2026 | 0.964 | +3.14% | R 0.92, D 0.044，第三方风险低 |
| Tennessee Governor 2026 | 0.966 | +2.75% | R 0.894, D 0.072 |
| NY Democratic Gubernatorial Primary | 0.989 | +0.93% | Hochul 0.973 已锁定 |
| 其余 4 个 | 0.99–0.994 | 0.1–0.8% | edge 小，不一定值得 |

**Binary 的第三方风险**：理论上 D/R 总和应该 = 1.0（无独立候选人当选），但：
- 历史上美国第三方议员存在（Bernie Sanders 独立人士）
- 候选人退选、特殊情况、市场 resolution 规则细节都可能让"既不是 D 也不是 R"
- 真实概率可能只有 0.5–2%，但 binary 套利的 margin 本身就只有 1–3%

需要用 T2 (resolution_reader) 读 description 判断 resolution 规则到底是「D wins → YES_D; R wins → YES_R; 都不是 → 全 NO」还是「正负风险结构」。

### 2.7 被正确剔除的假阳性（6 个）

包括 Nobel Peace Prize、Israel Next PM、Israel strikes N countries 等。**单看 sum<1 像是 arb，但成员列表本质开放** —— 实际结果不在列表里时整篮归零。

---

## 3. 路上学到的（meta lessons）

按重要性排序：

### 3.1 起草任何"现状 X 是错的/缺 Y"前必须读代码

`fees.py` 那次：我基于网上的 Polymarket category 阶梯，断言代码"只有单一全局 fee_rate 是错的"。你 push 一个 commit 指出 `collectors.py:1382` 早就在用 `feeSchedule.rate`。**外部研究告诉我们世界状态，代码告诉我们项目状态**。今天又踩了第二次：spec PR #4 我写 "spread 字段不在 raw Gamma"，但实测 spread 是 top-level 字段。

memory 已经写入 `feedback_verify_code_before_claiming_broken.md`，但实操还是会忘。

### 3.2 自动指标 ≠ 收益价值

4-model T2 对比的自动指标：Gemini 30/30 schema、DeepSeek 30/30 schema、几乎打平。但**读每个 model 抽出的具体 clauses** 才发现 DeepSeek 在 substantive condition（"必须 transferable"、">50% 阈值"、"FA Cup 不算"）上明显胜出，Gemini 保守地只抓日期。

教训：以后不能只看 schema/grounding 通过率就判定模型水平。

### 3.3 不要把不同分布的数字写在一起

方案 v0.1 的 longtail 阈值「vol24hr ≥ \$100」「mid ≥ \$5k」「headline ≥ \$50k」纯属拍脑袋。实测分布 P10=\$0 / P50=\$40 / P90=\$18k。**初稿偏高 100×**。

教训：先看分布再写阈值，永远不要反过来。

### 3.4 自动判定 exhaustive 比看着难

实验 7 v1 用 size≥8 作 exhaustive proxy → Nobel 这种 20 人开放命题被误判。
实验 7 v2 用 explicit catch-all 关键词 → Nobel 正确分到 open_set。
**但 binary 这一档（2 member）仍是灰色** —— 大多数是 exhaustive 的 D-vs-R 但偶尔会有第三方意外。

T2 的真实工作就是让 LLM 读 description 自动判定每个 group 是哪一档。

### 3.5 "速度赛 vs 广度赛" 这个 framing 是对的

你之前讲："识别出来机会，二次复核就没了 → 我就往广度上面去扩"。今天的实验完美映射了这个直觉：
- HFT 战场（半衰期 <1 分钟）：长尾外的主流市场，套利已死
- 长尾战场（半衰期数小时-数天）：**我们看到的 8.9% edge 持续存在的可能性更高**

---

## 4. LLM 选型的当前判决（基于实测）

| 模型 | Provider | 单 call 成本 | 延迟 | Schema | Substance | 适用场景 |
|---|---|---|---|---|---|---|
| **Gemini 2.0 Flash** | OpenRouter | $0.00021 | 3.1s | 30/30 | 中（漏 thresholds） | **大批量 first-pass** |
| **DeepSeek V3** | OpenRouter | $0.00049 | 16.9s | 30/30 | **最深** | **复杂 description 二跑** |
| GPT-4o-mini | OpenRouter | $0.00025 | 5.2s | 30/30 | 中（hallucinate URL） | 不推荐 |
| Llama 3.3 70B | OpenRouter | $0.00019 | 9.8s | 28/30 | 浅（parsed 空） | 不推荐 |
| **GLM-4.6** | **elysiver (free)** | **$0** | **~13s** | **29/29** | 高（3.3 clauses/m） | **0 成本替代品** |
| GLM-5 | elysiver (free) | $0 | ~45s | 16/30 ⚠️ | 4.0/市场（最深） | 不稳定 |
| GLM-5.1 | elysiver (free) | $0 | — | 今日 quota 已用完 | 未测 | — |
| Gemini Flash | windhub | — | — | Cloudflare 墙 | — | 不能用 |

**生产 T2 推荐**：
1. **首选**：GLM-4.6 via elysiver（0 成本，clause 数最多，stability 29/29）
2. **复核**：DeepSeek V3 via OpenRouter（仅对 GLM-4.6 返回 <3 clauses 的 markets，~10% 二次跑）
3. **兜底**：Gemini 2.0 Flash via OpenRouter（如 elysiver 全断）

预算估算：
- 2000 markets × GLM-4.6 = \$0 + ~7 小时（长尾，单线程无所谓）
- ~200 复杂 markets × DeepSeek V3 = \$0.10
- **总计 ~\$0.10 跑一遍**（vs 方案 v0.1 估算 \$17）

---

## 5. GitHub 当前状态

8 个 PR 在 upstream/main 上等：

| PR | 内容 | 状态 |
|---|---|---|
| [#1](https://github.com/WW-shan/poly_strategy/pull/1) | 长尾 thesis v0.1（你 merge 了） | ✅ MERGED |
| [#2](https://github.com/WW-shan/poly_strategy/pull/2) | DS pkg #01 fee schedule spec | ⏳ 等 review |
| [#3](https://github.com/WW-shan/poly_strategy/pull/3) | §9 决议（7/8 已自答，Q4 等你） | ⏳ 等 review |
| [#4](https://github.com/WW-shan/poly_strategy/pull/4) | DS pkg #02 Gamma 分布 spec（含 spread 修正评论） | ⏳ 等 review |
| [#5](https://github.com/WW-shan/poly_strategy/pull/5) | sector-reader 模式备忘（anthropic/financial-services） | ⏳ 等 review |
| [#6](https://github.com/WW-shan/poly_strategy/pull/6) | dash-ocr 生产模式 + OpenRouter 决议 | ⏳ 等 review |
| [#7](https://github.com/WW-shan/poly_strategy/pull/7) | Gamma 真实数据 + 实验脚本 + 校准结果 | ⏳ 等 review |
| [#8](https://github.com/WW-shan/poly_strategy/pull/8) | DS pkg #03 T2 resolution reader spec | ⏳ 等 review |

并且实验 7 + 多模型实验数据**在 experiment/2026-05-12-gamma-baseline 分支**，本文档会和它们一起再发一个 PR。

---

## 6. 我建议的下一步

按优先级排序：

### 6.1 立即做（你回了再说）

**审阅本文档 + 实验 7 候选清单**。两个关键问题需要你看一眼：

1. **James Bond Strict 候选**：值得用 CLOB `/book` 端点查真实深度吗？还是说先放着，等下次 snapshot 看是不是稳定存在？
2. **Binary 候选的第三方风险**：要不要让 T2 的 description 读取直接判定每个 binary neg-risk 是否真 exhaustive？

### 6.2 短期（这周）

按本文档 §4 的 LLM 选型决议，**改 PR #3 Q2 + PR #6 + PR #8 三处**：
- T2 主模型 = GLM-4.6 via elysiver（替代之前的 Gemini Flash 主跑）
- 二号模型 = DeepSeek V3 via OpenRouter（复核复杂 markets）
- 删除 PR #8 spec 里的 "head-to-head tuning 阶段"（实测已经完成）

### 6.3 中期（下周）

- T2 真正实现（按 PR #8 spec，~400 行）
- T3 same_event_detector：核心任务是**自动判定 binary 组的真实 exhaustiveness**，让 LLM 读 description 区分 D/R/Other 的 resolution 规则
- 不要做 T4 evaluation（用 10,122 mutex pairs 当 corpus 验证 judge，得是 T3 跑通之后的事）

### 6.4 长期目标

把 thesis 从「snapshot 普查」升级到「持续监控」：
- 每小时拉一次 Gamma snapshot
- 跑实验 7 类型的分析
- 发现新 strict 候选时发警报（webhook / Telegram）
- 重点跟踪 strict 候选的 edge 在 12-48 小时内是否稳定（验证 "长尾半衰期 > HFT 范围" 假设）

如果稳定存在 → thesis 成立，开始 paper trading
如果几小时内就被定价掉 → 我们错了，长尾也是 HFT 战场

---

## 7. 不要做的事（kill list）

- ❌ **再调一个 LLM 模型**。我们已经知道 GLM-4.6 + DeepSeek 是最优组合，再花时间测 deepseek-v4-pro / gpt-5.5-web-auto 不会改变决策。
- ❌ **优化 T2 schema**。verbatim_text + deterministic_clauses 在 8 个模型上都通过了，schema 不是瓶颈。
- ❌ **跨平台 (Kalshi / Manifold) 集成**。我之前提的，但你正确指出长尾事件几乎没有跨平台覆盖，性价比低。
- ❌ **HFT / 速度优化**。本 thesis 明确不是速度战。
- ❌ **做市策略**。\$100 量级不够，且面临 $0.10/次订单簿狙击。

---

## 8. 数据保留

- 所有 raw snapshot（gamma-raw.ndjson）和实验结果（NDJSON + 报告）都在 `data/experiments/2026-05-12/`（gitignored）和 `reports/`（committed）。
- 脚本都在 `scripts/experiment_*.py`，**任何时候可以重跑**验证。
- `.env` 配置了 `OPENAI_BACKUP_API_KEY`（elysiver 的 key），用于 GLM 系列调用。**今日 GLM-5.1 quota 已耗尽，明天可重试**。

---

## 9. 时间花在哪里了（透明账单）

| 类别 | 时长 | 我现在的看法 |
|---|---|---|
| 起草 spec / 备忘 / 决议 / PR 流程 | ~3h | 后半部分价值很低，但 OpenRouter 决议 + dash-ocr 模式备忘是底层基础设施 |
| LLM 模型 benchmark + 校准 | ~2h | Gemini Flash + DeepSeek V3 + GLM-4.6 这 3 个的对比有用，其他时间在浪费 |
| **实验 7 (alpha 普查)** | **~1h** | **这是真正决定 thesis 死活的 1 小时** |
| 修 bug（Python 编码、Cloudflare、quote 嵌套等） | ~1h | 工程时间，没办法 |
| 跟你的来回讨论 + 你拉我回正轨 | ~1h | **决定性贡献来自你 2 次"本末倒置"提醒** |

如果今天 8 点就直接做实验 7，可能下午 9 点就能得出 strict=1 这个结论。但路上的实验 1（Gamma 真实数据）和 PR #7 派生的 mutex pairs 也是必要 setup。

---

*报告写于 2026-05-12 北京时间 18:30 前后，基于 06:13 UTC 的 Polymarket snapshot。*
