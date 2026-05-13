# 长尾 Neg-Risk Mispricing 普查实验 7 (refined)（2026-05-12T10:19:18.834485+00:00）

**v2 改进**：原版 `likely_exhaustive` 把 size≥8 当作 exhaustive 是错的（Nobel 奖那种 20 人候选其实根本不穷举）。
本版分级：
- `explicit_other` —— 组内含 'No one / None / Another' 等显式 catch-all member（高置信度真 exhaustive）
- `binary` —— 正好 2 个 member（多数是 D/R 政治对决，**可能**穷举，但有第三方风险）
- `open_set` —— 3+ member 且无 catch-all（**几乎确定不穷举**，basket arb 是假信号）

---

## 1. 重新分级后的基本计数

- 总 neg-risk 组（已过滤 ask 退化）：**151**
  - `explicit_other`（**高置信度 exhaustive**）：**1** (1%)
  - `binary` (2 member)：**73** (48%)
  - `open_set` (假阳性源)：**77** (51%)
- 含至少 1 个长尾成员（vol24hr < $40）：**99** (66%)

## 2. Sum(YES_ask) < 1.0 + edge>0 三分类

- **Strict 候选**（confidently exhaustive + edge_after_fee > 0）：**1**
- **Binary 候选**（2 member + edge > 0，需验证第三方风险）：**7**
- **Open-set 假阳性**（看似 edge > 0 但 basket 不穷举，**不能交易**）：**6**

## 3. Strict 候选（真正值得 follow-up）

| Group | size | sum_ask | fee_total | edge_after_fee | longtail? | tier | min_liq |
|---|---:|---:|---:|---:|:---:|:---:|---:|
| `0xb23e25438839…` | 15 | 0.8930 | 0.01772 | +0.0893 | ✓ | explicit | $2,210 |

### Strict #1: edge = +0.0893, longtail = True

| Member | bestAsk | bestBid | vol24hr | liquidity | fee_rate |
|---|---:|---:|---:|---:|---:|
| Aaron Taylor-Johnson announced as next James Bond? | 0.016 | 0.005 | $113 | $2,210 | 0.0500 |
| James Norton announced as next James Bond? | 0.004 | 0.002 | $512 | $3,210 | 0.0500 |
| Paul Mescal announced as next James Bond? | 0.002 | 0.001 | $30 | $4,803 | 0.0500 |
| Jacob Elordi announced as next James Bond? | 0.037 | 0.035 | $72 | $3,349 | 0.0500 |
| Harris Dickinson announced as next James Bond? | 0.011 | 0.002 | $289 | $3,985 | 0.0500 |
| Tom Hardy announced as next James Bond? | 0.009 | 0.001 | $30 | $2,582 | 0.0500 |
| Pierce Brosnan announced as next James Bond? | 0.002 | 0.001 | $113 | $5,743 | 0.0500 |
| Tom Holland announced as next James Bond? | 0.012 | 0.007 | $30 | $3,173 | 0.0500 |
| Henry Cavill announced as next James Bond? | 0.002 | 0.001 | $62 | $5,696 | 0.0500 |
| Callum Turner announced as next James Bond? | 0.060 | 0.032 | $746 | $3,526 | 0.0500 |
| Jack Lowdon announced as next James Bond? | 0.002 | 0.001 | $30 | $5,933 | 0.0500 |
| Theo James announced as next James Bond? | 0.002 | 0.001 | $530 | $3,336 | 0.0500 |
| James Collier announced as next James Bond? | 0.002 | 0.001 | $114 | $5,332 | 0.0500 |
|  Josh O'Connor announced as next James Bond? | 0.002 | 0.001 | $30 | $3,390 | 0.0500 |
| No one announced as next James Bond? 🅾️ | 0.730 | 0.7 | $62 | $2,527 | 0.0500 |

## 4. Binary 候选（edge > 0，第三方风险待评估）

| Group | sum_ask | edge_after_fee | longtail? | min_liq |
|---|---:|---:|:---:|---:|
| `0x5f4893a285ad…` | 0.9640 | +0.0314 | ✓ | $2,634 |
| `0xb17c29a2fb22…` | 0.9660 | +0.0275 |  | $2,722 |
| `0xafccb4ac9586…` | 0.9890 | +0.0093 | ✓ | $13,622 |
| `0xe0ff15139f33…` | 0.9880 | +0.0079 | ✓ | $10,987 |
| `0xa8574c0caacc…` | 0.9900 | +0.0051 | ✓ | $4,009 |
| `0x9bb9ed087667…` | 0.9930 | +0.0035 | ✓ | $2,527 |
| `0x67d0d210eee8…` | 0.9940 | +0.0010 | ✓ | $3,375 |

Binary 组样本（前 3 个完整 member 表）：

#### Binary #1: edge = +0.0314
| Member | bestAsk | bestBid | vol24hr | liquidity | fee_rate |
|---|---:|---:|---:|---:|---:|
| Will the Democrats win the West Virginia Senate race in 2026 | 0.044 | 0.029 | $0 | $2,634 | 0.0400 |
| Will the Republicans win the West Virginia Senate race in 20 | 0.920 | 0.9 | $5 | $3,864 | 0.0400 |

#### Binary #2: edge = +0.0275
| Member | bestAsk | bestBid | vol24hr | liquidity | fee_rate |
|---|---:|---:|---:|---:|---:|
| Will the Democrats win the Tennessee governor race in 2026? | 0.072 | 0.051 | $110 | $6,776 | 0.0400 |
| Will the Republicans win the Tennessee governor race in 2026 | 0.894 | 0.89 | $100 | $2,722 | 0.0400 |

#### Binary #3: edge = +0.0093
| Member | bestAsk | bestBid | vol24hr | liquidity | fee_rate |
|---|---:|---:|---:|---:|---:|
| Will Kathy Hochul win the 2026 New York Democratic Gubernato | 0.973 | 0.971 | $71 | $16,225 | 0.0400 |
| Will Antonio Delgado win the 2026 New York Democratic Gubern | 0.016 | 0.008 | $0 | $13,622 | 0.0400 |

## 5. Open-set 假阳性（**不是机会**，列出避免误导）

这些组 sum < 1 看似有 arb edge，但成员列表**不穷举** —— 实际胜者不在列表里时整篮归零。**不要根据这些数据交易。**

| Group | size | sum_ask | edge_after_fee | sample question |
|---|---:|---:|---:|---|
| `0x09139fb03e82…` | 20 | 0.4590 | +0.5191 | Will Donald Trump win the Nobel Peace Prize in 202… |
| `0x03c9c6d9f7b2…` | 17 | 0.9380 | +0.0620 | Will Benjamin Netanyahu be the next Prime Minister… |
| `0x92fa5dc99566…` | 12 | 0.9610 | +0.0390 | Will Israel strike 4 countries in 2026?… |
| `0x4d76347d4d1e…` | 7 | 0.9810 | +0.0073 | Will NVIDIA be the largest company in the world by… |
| `0x80ee92187ee5…` | 14 | 0.9930 | +0.0026 | Will Kim Dong-yeon win the 2026 Gyeonggi Province … |
| `0x0f630f2d9401…` | 3 | 0.9800 | +0.0011 | Will the Democrats win the Michigan governor race … |

## 6. 重要警告（读结果前必看）

- **bestAsk 是 snapshot 时刻的最优挂单价**，不是任意可成交数量的均价。Long-tail 市场上 bestAsk 后面可能只挂 $5 的深度。
- **fee_rate** 取每市场自带的 `feeSchedule.rate`；feesEnabled=False 的市场记 0。
- **strict 也只是 'confidently exhaustive' 的启发式判定**，不是结构保证。生产时需要看 Polymarket Neg Risk Adapter 合约的实际配置。
- **slippage 可能吃掉所有 edge** —— 实际交易前需要用 CLOB `/book` 端点核对深度。

## 7. 真正要回答的问题

- 今天 snapshot 下，**confidently exhaustive 且 edge > 0 after fees 的组数 = 1**。
  - 长尾子集 = 1
- 进入下一步的条件：用 CLOB orderbook 复核这 1 个候选的真实可成交深度，剔除 slippage 吃掉 edge 的，剩多少是真 alpha。

---
*Snapshot: 2026-05-12T10:19:18.834485+00:00*