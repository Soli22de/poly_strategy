# 长尾 Polymarket Thesis —— Day 2 续报（2026-05-13）

**作者**：Soli22de + Claude Opus 4.7（1M context）
**面向读者**：同学 WW
**与昨日报告 (`research-summary-2026-05-12.md`) 的关系**：昨日是一次 06:13 UTC snapshot 的普查结果（"有 1 个 strict 候选 James Bond, edge +8.93%"）。今日把数据量扩到 14 天 × 15 分钟 granularity，并且对 strict 候选做了真实 orderbook 深度检查。**结论从「thesis 待验证」推到「thesis 在当前深度下商业死亡」**。

> **Post-review correction（2026-05-13）**：§3.9 的 maker v2 dollar 结论是旧 simulator 产物；旧公式按目标 basket size 计收益，没有按每条腿真实 at-or-below-target SELL-Yes 成交量封顶，也没有强制 maker quote 严格低于 bestAsk。代码已修正，下面涉及 `$918/yr`、`$200-500/yr`、`$2-5k/yr` 的数字只能视为 stale upper bound，必须重跑 `scripts/simulate_maker_basket_v2.py` 后再决策。

---

## TL;DR —— 30 秒结论（vs 昨日）

| 问题 | 昨日的答案（1 snapshot） | 今日的答案（14 天 + 深度检查） |
|---|---|---|
| 长尾 explicit_other arb 存在吗？ | 1 个 strict 候选，mid-edge +8.93% | ✅ 存在；持续性强（**最长 60 小时连续 edge>5%**） |
| 能赚多少？ | 没量化 | ❌ **每事件最高 ~\$3.78**，全年理论上限 ~\$394 |
| 频率？ | 不知道 | 14 天里 4 次事件，**全都是同一个组 James Bond** |
| Binary D-vs-R 套利存在吗？ | 7 个候选，edge 0.1-3% | ⚠️ 回测看到 98 事件，**但绝大多数是 forward-fill 伪信号** |
| 该继续做 thesis 吗？ | "上线 paper trading" | **TAKER 死，MAKER 活但很小**（详见 §3.9）|

**核心发现链（按时间顺序）**：
1. mid-price 给出的"持续 edge"和 bestAsk 实际可成交 edge 是两个东西（§3.4）
2. TAKER 一次性吃光 bestAsk 在 2 个测试组（James Bond + SC Gov）下死亡（§2 + §3.7）
3. 我据此说"thesis 死了" —— 用户当场质疑（§3.9）
4. 补做 MAKER 模拟：v1 mid-touch 给 $15k/yr 假象，v2 trade tape 旧公式给 $918/yr 上界
5. Post-review 修正：maker v2 需要按真实成交量封顶后重跑；**旧 `$200-500/yr @ $100 basket` 不再作为最终结论**

**Post-review 后的判决**：**Taker 基本死；Maker 不能再按旧数字下结论，必须用成交量封顶版本重跑。最严重的教训是 §3.9：我用 1 个角度的测试做了全局结论，错了；但旧 maker v2 又犯了 size 上限错误。**

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

### 3.6 Day 3 实测结果（不用等 1-2 周了）

第二天醒来跑了一次 `analyze_binary_refined.py --live-only`（新加的 flag），用过去 14 小时纯 live bestAsk 数据：

| | 14 天回测（mid） | 纯 14 小时 live（bestAsk） |
|---|---:|---:|
| dvr 事件数 (edge>2%) | 98 | **7** |
| 中位持续时间 | 22 小时 | **15 分钟（1 个 snapshot）** |
| 最高峰 | +41.7% | +19.8% |

确认 22 小时持续是 forward-fill 假象。**真实 bestAsk 看到的"persistent edge floor"**：

- **WV Senate D/R**：14:35-17:35 sustained +4-5%（3 小时 +4-5% 边际 edge）
- **TN Governor D/R**：14:35-15:50 sustained +9-10%，然后崩到负
- **SC Governor D/R**：**14 小时连续 +2.5-3.0%**，min_liq \$4,377（看起来最稳）
- **OK Senate D/R**：peak +3.55% 后 settled +0.5%
- **AR Senate D/R**：徘徊 ±0.15%，噪音

这 5 个里 SC Governor 看起来最像真 alpha：持续小 edge，深度看起来还行。所以**深度检查走起**。

### 3.7 SC Governor D/R 深度检查 —— 同样死亡

```
scripts/verify_group_book.py --group-id 0xa8574c0caacc --basket-sizes "50,200,500,1000,2000,5000"
```

| Basket size | Avg cost/u | Total fee | Edge $ | Edge % |
|---:|---:|---:|---:|---:|
| 1u marginal | 0.969 | 0.005 | +\$0.026 | +2.55% |
| 50u | 0.9846 | 0.25 | **+\$0.52** | +1.04% |
| 200u | 0.9934 | 1.01 | +\$0.31 | +0.15% ← 接近 breakeven |
| 500u | 1.0371 | 2.88 | -\$21 | -4.29% |
| 1000u | 1.0644 | 5.75 | -\$70 | -7.01% |

**Killer**：Republican 侧 bestAsk=0.91，**该价位深度只有 3.9 单位**（\$3.5 fillable）。一笔 \$4 的 trade 就把 edge 干掉。

### 3.8 两条 TAKER thesis 分支的统一结论

| Thesis 分支（**TAKER 视角**） | 每事件最高利润 | Verdict |
|---|---:|---|
| explicit_other (James Bond) | \$3.78 | **当前深度下死亡** |
| binary D-vs-R (SC Gov 等 71 组) | \$0.52 | **当前深度下死亡** |

**两条 TAKER 分支都被同一个结构性事实杀死**：Polymarket 长尾市场 bestAsk 处深度只有 \$5-80。我们看到的 "edge" 都是真的存在，但它们的存在恰恰因为**没人来 \$5 的资金把它吃掉**。

也就是说，整个 thesis 的逻辑链是反的：**我们以为"长尾持续 edge = 别人没注意"，实际上"长尾持续 edge = 别人不愿意为了 \$3 折腾这一套订单流"**。市场是有效率的，只是有效率的定价区间只对应"值得做"的回报。

### 3.9 我之前判错了 —— MAKER thesis 是活的（小规模）

写完 §3.8 之后用户当面质疑："你的实验方法确认准确？真正的技术在哪里？"

**我之前只测了 TAKER 一条腿，就宣布 thesis 死了。这是过度推论**。Maker 视角（挂限价单等被填）是完全不同的策略，需要独立测试。

#### v1 (mid-touch) 模拟

`scripts/simulate_maker_basket.py`：3,153,188 个 mid-price tick 点跨 14 天 × 157 token。对每个 (group, day, markup) 三元组，检查每条腿的 mid 是否在那天某时刻 touch 到 `bestAsk - markup`。若 ALL legs filled，计算 basket cost + fee + edge。

结果（**乐观上限**）：
- 总日预期 $42.59，年化 **$15,546**
- 49/72 个 dvr 组有正期望
- Best: Kansas Governor D/R，$4.87/day @ $100 basket，spread 9%

**警告写在脚本里：mid-touch 不等于 trade-at-target。真实 fill 率会低很多**。

#### v2 (trade tape) 旧公式结果（post-review 后需重跑）

`scripts/simulate_maker_basket_v2.py`：从 `data-api.polymarket.com/trades` 拉了真实成交记录。48,030 raw trades → 1,602 个 SELL Yes 在窗口内（只有 **3.3%** 的成交是 SELL-Yes，即"会触发我们 maker bid 的那种"）。

Post-review 发现旧公式仍把每次 fill 乘以目标 basket size，没有按最薄腿真实 at-or-below-target 成交量封顶；因此本节数字只能作为旧版上界。

| Metric | v1 (mid-touch) | v2 (trade tape, pre-fix upper bound) |
|---|---:|---:|
| 总日 $ | $42.59 | **$2.51** |
| 年化 | $15,546 | **$918（旧上界）** |
| 正期望组 | 49/72 | **17/72** |
| 平均 fill rate | 23-69% | **5-6%** |

**v1 过估 17x**。

#### 现实折扣（v2 之上还要往下打）

| 折扣项 | 影响 |
|---|---:|
| Queue priority（我们不一定是第一） | ×0.6 |
| D/R 相关动（联合 fill 比独立 fill 难） | ×0.7 |
| Partial fill 风险（一腿成 一腿没成 → 持仓不对冲） | -10% |
| Polygon gas / 多笔交易成本 | -20% |
| **旧现实估计** | **无效，需按成交量封顶后重跑** |

旧版 "$1000 basket → ~$2-5k/yr" 线性外推同样无效，因为真实成交量通常远低于目标 basket size。

#### 修正后的两层 verdict

| 策略 | 现实预期 \$/yr | 备注 |
|---|---:|---|
| Taker basket arb | \$0-200 | 被深度杀死，verified |
| Maker basket arb（mid-sim 错估） | \$15k 假象 | 方法错 |
| **Maker basket arb（trade tape）** | **需重跑** | 代码已改成成交量封顶 + 非 crossing maker quote |

#### 我学到的最严肃的教训

我前两天说 "thesis 已死" 是**过度推论**。我只测了 1 个视角（TAKER 一次性吃光 bestAsk），用 2 个组的单次 snapshot 就下了"整条 thesis 死亡"的判决。**用户当面质疑后补做的 trade tape v2 提示 maker 方向仍值得验证，但 post-review 后必须用成交量封顶版本重跑，不能再把旧收益数当结论**。

更广义的教训：**"测一个角度 → 推全局"** 是科研里最廉价的错误之一。Robust 测试需要至少：
- 多种策略视角（taker / maker / hold-to-resolution）
- 多个时刻的 snapshot（不只单点）
- Realistic 模拟模型（trade tape > mid-touch）
- 多种规模（depth 在不同 size 下表现不同）

Day 1 我没做 §3.9 的工作就敢宣布"alpha 不存在"。Day 3 在用户推动下补做，才得到诚实答案。

**用户的"我不信邪"是这份报告唯一存活的原因**。

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
| `scripts/verify_james_bond_book.py` | 真实 CLOB `/book` 深度检查 + 滑点模拟（James Bond 专用） | 已退役 |
| `scripts/verify_group_book.py` | 上面的泛化版 —— 接 `--group-id` arg 对任意 negRisk 组做深度检查 | 候选出现时单独跑 |
| `scripts/simulate_maker_basket.py` | v1 maker 策略模拟（mid-touch 代理）—— **乐观偏差** | 第一次试，已知方法偏粗 |
| `scripts/simulate_maker_basket_v2.py` | v2 maker 策略模拟（trade tape）—— **methodologically defensible** | 现在的 canonical maker 模拟 |

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

## 5. 我对下一步的建议（Day 3 更新版）

### 5.1 立即

1. **停 live snapshot loop**。两条 thesis 分支都已死，继续 14 天积累已无意义。已积累的数据保留在 `data/snapshots/` 作 baseline。
2. **审本报告**，特别是 §3.6-3.8 的 SC Gov 深度检查结果 —— 这是 binary thesis 的"棺材板"。
3. **跟 WW 在 PR #9 上对齐新方向**。

### 5.2 候选新 thesis（按 cost-to-falsify 升序）

| 方向 | 假设 | 第一步测试 | 落实成本 |
|---|---|---|---|
| **A. 直接放弃** | "prediction market 在我们的资金/精力水平上不值得" | 已经做完 —— 本报告就是 falsification | \$0 |
| **B. 做市策略** | "longtail 市场 sum(bestAsk) 经常 > 1 → 双边挂单赚 spread > $1.5/day/市场" | 用现有 live 数据回测每市场每日 spread × hypothetical 50u fill 频次 | ~2hr |
| **C. 高流动性 HFT 缝隙** | "headline 市场（vol24hr P90+）有 sub-minute mid-edge" | 抓 5 个 vol24hr > \$10k 市场的 1-second tick 数据 30 分钟，看是否存在 >0.5% 持续>10s edge | ~3hr |
| **D. Cross-platform** | "Polymarket vs Kalshi 同一事件价格不一致" | 拉两边 active events，模糊匹配，比较 implicit prob | ~4hr |

**Claude 的偏好**：跑 **B（做市）**，因为：
- 数据已经有（不用重新拉）
- 假设是 `2.55%` 这种 edge 是**人家不愿来挑的服务费**，不是 alpha；如果是服务费，反方向是**我们挂上去赚**它
- 可证伪：算一下 14 天里 sum(bestBid) - sum(bestAsk) 的累积分布即可

### 5.3 已经定死不做的（KILL LIST，Day 3 扩展）

- ❌ 继续 polish T2/T3 LLM pipeline，期待"更智能的 description 解读 → 更好 alpha"。**已证明 alpha 瓶颈在订单簿，不在 LLM**。
- ❌ 用 mid-price 回测 long-tail market。**已证明回测伪信号率 >90%**。
- ❌ 上线任何 paper trading on James Bond basket。$3.78/event 经不起 gas。
- ❌ 上线任何 paper trading on D/R 通选 basket。$0.52/event，更糟。
- ❌ 把更多模型加进 multi-model bench。GLM-4.6 / DeepSeek V3 已够（且当前 thesis 不需要 LLM）。
- ❌ **再跑 14 天 backfill on long-tail markets**。已证明对低活跃市场不靠谱。

---

## 6. 数据 / 工具 / 记录的去向

- 本报告 + 5 个新 reports + 6 个新 scripts + `run_snapshot_loop.ps1` commit 到 `experiment/2026-05-12-gamma-baseline`
- `data/snapshots/` 在 `.gitignore` 内不会进 PR，但本地保留作为后续分析基线（约 1.3GB）
- live loop **Day 3 下午停**：thesis 已死，不再积累。停止时机记在 §7 时间账里。

---

## 7. Day 2 + Day 3 honest 时间账

| 类别 | 时长 | 价值 |
|---|---|---|
| 写 snapshot_gamma + run_snapshot_loop + analyze_arb_events | ~1h | 基础设施，已验证 |
| 写 backfill_prices_history + 跑 14 天 | ~1h | **方法上验证了 backfill 在 longtail 失败** |
| 写 verify_james_bond_book + 跑深度检查 | ~30min | **决定性 \$394/yr 结论来自这 30 分钟** |
| 写 analyze_binary_refined + 调查 forward-fill 伪信号 | ~1h | 排除掉一条假分支 |
| Day 3 早晨：跑 live-only binary 分析 | ~15min | 看到 22h persistence 全是 forward-fill 假象 |
| Day 3 早晨：泛化 verify_book + 跑 SC Gov | ~30min | **第二条 thesis 分支死亡的决定性 15 分钟** |
| 与你的来回 + commit + PR | ~1h | 决策正确性 + WW 可视 |

**总耗时（Day 2 + 3）约 5 小时**，得出两个完整 thesis 分支的死亡判决。**如果只为了 verdict**，理论最短路径：build snapshot_loop + verify_group_book + 跑 2 个组（James Bond + SC Gov）= 1.5 小时。剩下 3.5 小时的"沉没成本"价值：
- 方法论 meta-lesson：mid-price 回测对 longtail 不可信（写在 §3.4）
- 基础设施可用于任何 future thesis（snapshot_loop + analyze_arb_events + verify_group_book 都是泛化的）
- backfill 1.3GB 数据保留作 baseline，未来如果回头研究 D/R 价格动力学还能用

---

## 8. 给 WW 的明确请求

请审阅这份报告 + PR #9，在 PR 评论里回答：

1. **同意停 live loop 吗？**（我已经停了，但可以重启）
2. **§5.2 四个候选 thesis 你想优先做哪个？** Claude 推 B（做市），但可能我看漏了。
3. **是否要把今天得到的 verdict 写一篇正式的"thesis post-mortem"** 文档放进 repo，作为后续协作的明确 baseline（不被未来的人重复探索）？

---

*报告写于 2026-05-13。基于 14 天 (2026-04-28 → 2026-05-12 14:00 UTC) 合成回测 + 实时 CLOB 深度 + Day 3 (~14h) live bestAsk 时间序列。*
