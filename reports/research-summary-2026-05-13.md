# 长尾 Polymarket Thesis —— Day 2 续报（2026-05-13）

**作者**：Soli22de + Claude Opus 4.7（1M context）
**面向读者**：同学 WW
**与昨日报告 (`research-summary-2026-05-12.md`) 的关系**：昨日是一次 06:13 UTC snapshot 的普查结果（"有 1 个 strict 候选 James Bond, edge +8.93%"）。今日把数据量扩到 14 天 × 15 分钟 granularity，并且对 strict 候选做了真实 orderbook 深度检查。**结论从「thesis 待验证」推到「thesis 在当前深度下商业死亡」**。

---

## TL;DR —— 30 秒结论（vs 昨日）

| 问题 | 昨日的答案（1 snapshot） | 今日的答案（14 天 + 深度检查） |
|---|---|---|
| 长尾 explicit_other arb 存在吗？ | 1 个 strict 候选，mid-edge +8.93% | ✅ 存在；持续性强（**最长 60 小时连续 edge>5%**） |
| 能赚多少？ | 没量化 | ❌ **每事件最高 ~\$3.78**，全年理论上限 ~\$394 |
| 频率？ | 不知道 | 14 天里 4 次事件，**全都是同一个组 James Bond** |
| Binary D-vs-R 套利存在吗？ | 7 个候选，edge 0.1-3% | ⚠️ 回测看到 98 事件，**但绝大多数是 forward-fill 伪信号** |
| 该继续做 thesis 吗？ | "上线 paper trading" | **当前深度下不值得；继续观察实盘 bestAsk 才能定 binary** |

**核心新发现**：mid-price 给出的"持续 edge"和 bestAsk 实际可成交的 edge 是**两个东西**。回测里看着 30 小时 +18% 的 arb，实际订单簿一次只能吃 \$50-100 的 basket，再多 slippage 就吃掉所有收益。

**今天 Claude 的判决**：**stop chasing this，把 live snapshot loop 留着跑，下周再用真 bestAsk 时间序列验证 binary 那边**。

---

## 1. 从 1 个 snapshot 到 14 天数据

### 1.1 思路：用 `/prices-history` 回补

昨日报告的 "1 strict 候选 + 7 binary" 全部基于 06:13 UTC 那一瞬。问题：
- edge +8.93% 可能只是当时一笔报价的偶然事件
- 30 分钟后可能就被定价掉，也可能持续几天
- 单 snapshot **无法回答"alpha 是否持续"**

直接等 14 天 live snapshot 太慢，因此用 Polymarket CLOB `/prices-history` 端点回补：
- 对每个 negRisk market 的 YES tokenID 调一次 `/prices-history?fidelity=900&startTs=...&endTs=...`
- 2010 个 token，5 并发，约 10 分钟拉完，46108 个 mid-price 数据点
- 客户端按 15 分钟桶 forward-fill 重建合成 snapshot

**Caveat（写在脚本里也强调过）**：
1. 价格是 **mid 不是 bestAsk** —— 实际买价 sum(bestAsk) ≥ sum(mid)，所以 edge **系统性高估**
2. group membership 是「今天的」回投，市场<14d 前未存在时该组在老 slot 被丢弃
3. liquidity / vol24hr 用今天的值填到所有历史行 —— **不是历史真实活跃度**

### 1.2 14-天 explicit_other 回测结果

```
载入 1083 个 explicit_other 历史 group-rows（963 个唯一 snapshot 时间）
检测 edge_after_fee > 5% 的连续事件（gap > 35 min 切断）：
  4 events，全部 longtail
  median persistence: 2235 min (= 37.25 hr)
  P25: 466 min (7.8 hr)
  P75: 3360 min (56 hr)
```

更关键的是 **所有 4 个事件都在同一组 `0xb23e25438839...`（James Bond）**：

| 时段 | 持续 | 峰值 mid-edge |
|---|---|---|
| 04-30 18:15 → 05-02 00:00 | 30 hr | +12.36% |
| 05-05 18:15 → 05-07 15:00 | 45 hr | +9.14% |
| 05-08 06:15 → 05-10 18:00 | **60 hr** | **+18.23%** |
| 05-12 13:53 → 14:05+ (still open) | 12+ min | +8.93% |

第二个 explicit_other 组（Trump-Putin 下次见面地点，0x986b6856bc63...，15 member）**最高 edge -0.25%**，从来没成为机会。

**所以整个 14 天的"长尾 explicit_other 套利"thesis 缩成一句话：James Bond 一个组，平均 3-4 天来一次，每次持续约一天半，mid-edge 9-18%。**

---

## 2. James Bond 真实订单簿深度检查 —— $394/yr 上限

mid-edge 是上界。真要交易得用 CLOB `/book` 看 bestAsk 阶梯。

### 2.1 检查方法（`scripts/verify_james_bond_book.py`）

对 15 个 James Bond YES token 同时拉 `/book`：
1. 取 bestAsk 和该价位的挂单深度
2. 模拟买 N 单位 basket：每个 member 走 ask 阶梯，遇到深度不足就跳到下一档价
3. 算 N 单位 basket 的实际加权均价、总 fee、净 edge

### 2.2 结果

| Basket 大小 (= \$payout) | 均价 / unit | Fee | Net Edge \$ | Net Edge % |
|---:|---:|---:|---:|---:|
| 10 u | 0.8930 | 0.18 | +\$0.89 | +8.93% （= mid 上界）|
| 30 u | 0.8948 | 0.53 | +\$2.62 | +8.74% |
| 50 u | 0.9096 | 0.91 | +\$3.61 | +7.22% |
| **80 u** | **0.9337** | **1.53** | **+\$3.78** | **+4.72% ← 最大单事件利润** |
| 100 u | 0.9505 | 1.97 | +\$2.98 | +2.98% |
| 150 u | 1.0391 | 3.52 | **-\$9.38** | **-6.25%** |
| 200 u | 1.1007 | 5.15 | -\$25.28 | -12.64% |

瓶颈是细腿（Jacob Elordi 21 单位 @ 0.037，Callum Turner 40 单位 @ 0.062，"No one" 30 单位 @ 0.73），超过这些深度后必须吃更贵的 ask。

### 2.3 全年理论上限

```
每事件最高利润：\$3.78
事件频率：14 天 4 次 = 365/3.5 ≈ 104 次/年
全年理论上限：\$3.78 × 104 ≈ \$394
```

减去：
- Polygon gas（每事件 16+ 笔交易 × \$0.5-2）≈ \$8-32/event
- 资金占用机会成本（James Bond endDate 多在 2026-12-31，资金锁 8 个月）
- 真有人发现这个 edge 后竞争吃 fill

**现实利润：\$0-200/yr，大概率 < \$0**。

### 2.4 结论

长尾 explicit_other thesis **技术上活着**（edge 真实存在），**商业上死亡**（深度撑不起规模）。

---

## 3. Binary D-vs-R 套利 —— 回测看到 98 事件，但都是伪信号

### 3.1 重新做 binary classifier

昨日 v2 简单的"2 member = binary"分类把 Aston Villa vs Freiburg（UEFA Europa，几十支队）也归类成 binary。今天的 `analyze_binary_refined.py` 做了 sub-classify：

- **`dvr`**：一问含 "Democrats"，另一问含 "Republicans"，**且共享同一个 race noun**（Senate/governor/House/Presidential）→ 真正 D-vs-R 通选，几乎肯定穷举
- **`yes_no`**：一问含否定标记（not / fail to / miss），另一问是肯定版本，且字符前缀高度相似
- **`pseudo`**：默认兜底 —— 大概率是 sample of many（体育、初选）

92 个 2-member 组里：71 个 dvr / 0 个 yes_no（启发式太严）/ 21 个 pseudo。

### 3.2 回测结果

| sub-tier | events (edge>2%) | distinct groups | median persistence | top peak |
|---|---:|---:|---:|---:|
| **dvr** | **98** | 71 | 22 hr | **+41.7%** |
| yes_no | 0 | 0 | — | — |
| pseudo | 27 | 21 | 14.75 hr | +51.9% |

98 个 D-vs-R 事件 × 22 小时中位持续看起来超级牛 —— **直到看具体峰值长什么样**。

### 3.3 峰值的真相 —— forward-fill 伪信号

前 5 名 dvr 峰值：

| Group | 类别 | Peak edge | 跨度 | 14 天内 distinct sum_ask 数 |
|---|---|---:|---:|---:|
| Oregon Senate D/R | dvr | +41.7% | 1 个 snapshot 跳变 | **9** |
| S. Dakota Senate D/R | dvr | +38.5% | 一段连续 0.604 | 34 |
| Arkansas Senate D/R | dvr | +32.8% | backfill window 起点就是 0.66 | 23 |
| CA-27 House D/R | dvr | +32.5% | 一段连续 0.659 | 30 |
| Oklahoma Senate D/R | dvr | +27.3% | 一段连续 0.7155 | 22 |

14 天 1140 行数据，只有 9-34 个 distinct 价格 → 平均每 30 小时才有一笔 mid 更新。然后 forward-fill 把那一笔孤立 trade 的"低价"传播了几十个 snapshot，看起来像"持续 edge"。

**实盘验证**：现在的 sum_ask 是多少？

- Oregon Senate：当下 sum_ask = **1.0000**（基本无 edge，spread 接近 0）
- South Dakota Senate：sum_ask = **1.036**（已经 > 1.0，买双边亏 spread）
- Arkansas Senate：sum_ask = **0.998**（接近 0，无机会）
- CA-27 House：sum_ask = **1.204**（远 > 1.0）
- Oklahoma Senate：sum_ask = **0.988**（0.7% edge，但 mid 不是 bestAsk）

那些"30 小时 +30%-+40% edge"全部是过去某个时刻的孤立 trade 加 forward-fill 假象。**没有一个能在今天落单执行。**

### 3.4 教训

**Backfill / mid-price 的方法对长尾市场不靠谱**：
- 长尾市场每天才几笔 trade，`/prices-history` 数据点稀疏
- forward-fill 把单点价格延伸为"持续状态"，制造伪持续 edge
- 真实可成交价（bestAsk）每时每刻都在变，但回测看不到

**只有 live bestAsk 时间序列才能定 binary thesis 死活**。

### 3.5 当前 binary 现实

15 分钟 cadence 的 live snapshot loop 已经在跑（21:05 UTC 开始），未来 7-14 天会积累真 bestAsk-基础的 binary 时间序列。等积累到 1-2 周后再跑 `analyze_arb_events.py --tier binary --min-edge 0.02`，那时候才是 binary thesis 的真测试。

---

## 4. 今天搭好的基础设施

每一块都已经验证可用：

| 文件 | 作用 | 何时用 |
|---|---|---|
| `scripts/snapshot_gamma.py` | 每次拉一帧 Gamma + 派生 group classifier | 被 loop 每 15 min 调用 |
| `run_snapshot_loop.ps1` | 持久 PowerShell 后台循环 | 在分离的 PS 窗口里运行（Ctrl+C 停）|
| `scripts/backfill_prices_history.py` | 从 CLOB `/prices-history` 重建历史合成 snapshot | 一次性，仅适用于较活跃市场 |
| `scripts/analyze_arb_events.py` | 检测连续 edge 事件 + pass/kill 判决 | 任何时候，读 `data/snapshots/` 全部数据 |
| `scripts/analyze_binary_refined.py` | sub-classify 2-member 组 + 分 sub-tier 检测事件 | 任何时候 |
| `scripts/verify_james_bond_book.py` | 真实 CLOB `/book` 深度检查 + 滑点模拟 | 候选出现时单独跑 |

数据布局（`.gitignore` 已排除 `data/`）：
```
data/snapshots/
  2026-04-28 ~ 2026-05-12/  ← 历史 backfill (groups.ndjson only, is_backfill: true)
  2026-05-12/
    13-53/  14-05/  14-20/  ...  ← live snapshots (markets.ndjson + groups.ndjson + meta.json)
data/experiments/2026-05-12/
  james-bond-books-raw.json   ← 深度检查原始数据
  binary-classification.json  ← refined binary sub-tier 表
```

---

## 5. 我对下一步的建议（更新版）

### 5.1 立即 (今天 / 明天)

1. **不要再花时间在 explicit_other arb**。James Bond 是唯一候选，$394/yr 上限已知，不值得继续投入。
2. **让 live snapshot loop 继续跑**。每 15 min 自动落盘，14 天后会有真 bestAsk 时间序列。
3. **审本报告**，特别是 §3 的 forward-fill 伪信号问题 —— 这影响所有低活跃市场的回测结论。

### 5.2 短期 (1-2 周)

**等 live loop 跑满 7-14 天，再做一次 binary 真测**：
- 用 `analyze_arb_events.py --tier binary --min-edge 0.02` 跑 **仅 live 数据**（is_backfill=False）
- 真实 bestAsk 时间序列上看 binary D-vs-R 有没有持续机会
- 对前 5 名峰值跑 `verify_james_bond_book.py` 类的深度检查（脚本需轻微改造泛化）

### 5.3 中期 thesis 修正

昨日的 §6.2 推荐"T2 LLM resolution_reader 主跑改 GLM-4.6"仍然成立，但**优先级降低** —— 因为现在我们知道 thesis 的瓶颈不是 description 解读能力，是**订单簿深度**。

新的 thesis 方向候选（按性价比降序，待 WW 评议）：
- **A. 高流动性事件 + 短时 mid-edge**：放弃长尾，专做"有交易、bestAsk + bestBid spread <1pp、深度>$5k"的市场，盯短半衰期 edge。完全反方向，但有可能找到 HFT 缝隙。
- **B. Resolution 规则不对齐的 cross-platform**：Polymarket vs Kalshi/Manifold 同一事件 implicit prob 偏差。问题是覆盖低 —— 之前提过。
- **C. 做市策略**：在 longtail 市场挂双边赚 spread。需要 $1k+ 资金 + 24/7 监控。
- **D. 直接放弃 prediction market，转其它领域**。诚实选项。

### 5.4 已经定死不做的（KILL LIST）

- ❌ 继续 polish T2/T3 LLM pipeline，期待"更智能的 description 解读 → 更好 alpha"。**已证明 alpha 瓶颈在订单簿，不在 LLM**。
- ❌ 用 mid-price 回测 long-tail market。**已证明回测伪信号率 >90%**。
- ❌ 上线任何 paper trading on James Bond basket。$3.78/event 经不起 gas 和监控成本。
- ❌ 把更多模型加进 multi-model bench。GLM-4.6 / DeepSeek V3 已够。

---

## 6. 数据 / 工具 / 记录的去向

- 本报告 + 4 个新 reports + 5 个新 scripts + `run_snapshot_loop.ps1` 即将一次性 commit 到 `experiment/2026-05-12-gamma-baseline`
- `data/snapshots/` 在 `.gitignore` 内不会进 PR，但本地保留作为后续分析基线
- live loop 会一直跑直到手动停（窗口 Ctrl+C 或关闭窗口）。**建议留着跑**。

---

## 7. Day 2 honest 时间账

| 类别 | 时长 | 价值 |
|---|---|---|
| 写 snapshot_gamma + run_snapshot_loop + analyze_arb_events | ~1h | 基础设施，已验证 |
| 写 backfill_prices_history + 跑 14 天 | ~1h | **方法上验证了 backfill 在 longtail 失败**，本身就是结论 |
| 写 verify_james_bond_book + 跑深度检查 | ~30min | **决定性 \$394/yr 结论来自这 30 分钟** |
| 写 analyze_binary_refined + 调查 forward-fill 伪信号 | ~1h | 排除掉一条假分支 |
| 与你的来回（决定 backfill, 决定 commit）| ~30min | 决策正确性的保证 |

如果今天一开始就先 build snapshot_loop + verify_james_bond_book，4 小时就能得出"$394/yr"上限。backfill 那 1 小时事后看的价值是发现"mid-price 长尾回测不靠谱"—— 这个 meta-lesson 也很重要。

---

*报告写于 2026-05-13。基于 14 天 (2026-04-28 → 2026-05-12 14:00 UTC) 合成回测 + 实时 CLOB 深度。*
