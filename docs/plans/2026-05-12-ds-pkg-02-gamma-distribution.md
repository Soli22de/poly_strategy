# DS 指令包 #02：Gamma 市场分布 Reality-Check

**主方案**：[`2026-05-11-longtail-resolution-thesis.md`](./2026-05-11-longtail-resolution-thesis.md) §Q1 卡点的数据准备

**作者**：方案 author 起草，DS 执行
**目的**：给 Q1（长尾 tier 阈值）提供**真实数据**而不是拍脑袋数字。所有数字都从原始 Gamma 字段计算，不抄 Dune（Paradigm 2025-12 已报告 ~2x 双重计算问题）。
**预计代码量**：~200 行（实现 + 测试）+ 1 份分析报告
**预计 DS 单次 token 消耗**：< 40k

---

## 0. 上下文（DS 必读）

项目代码**已经**有完整 Gamma 抓取能力：
- `collectors.py:11` `GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"`
- `collectors.py:64` `collect_polymarket_gamma_pages(path, limit, pages, ...)` 已经在用，分页抓 Gamma `/markets`，输出 NDJSON
- CLI `collect-polymarket --pages N --limit L` 是入口

**所以本任务不需要重写抓取层**。需要新增的是"消费 raw NDJSON → 算分布 → 出报告"的分析层。

**字段映射**（已验证存在于 raw Gamma payload，watchlist.py 已使用）：
- `volume24hrClob` / `volume24hr` —— 24h 成交量
- `volume1wkClob` / `volume1wk` —— 周成交量
- `liquidityNum` / `liquidityClob` / `liquidity` —— 流动性
- `endDate` —— 结算时间 ISO8601
- `category` / `categorySlug` —— 分类
- `negRisk` —— 是否 neg-risk 子市场
- `enableOrderBook` / `acceptingOrders` —— 活跃标志

**字段映射（不存在或贵）**：
- ❌ `spread` —— 不在 raw Gamma 里，需要逐市场调 CLOB `/book`。12k 个市场调一遍不现实。**本 spec 不涵盖 spread 分析**，留独立 task。
- ❌ `category` 在某些旧数据里可能缺失，要 fallback 处理。

---

## 1. 任务清单

### 1.1 新模块 `poly_strategy/longtail_research.py`

**性质**：research utility，**不**纳入生产管线。不被 `scanner` / `realtime` / `paper` / `execution` 任何模块依赖。

**公开函数**：

```python
def analyze_gamma_distribution(
    raw_path: Path,
    *,
    now: Optional[datetime] = None,
    drop_inactive: bool = True,
) -> "GammaDistributionReport":
    """读取 raw Gamma NDJSON，按 volume24hr / volume1wk / liquidity /
    days_to_resolution / category 切分，返回结构化报告。

    drop_inactive=True 时，过滤 enableOrderBook=False 或 acceptingOrders=False。
    now=None 时用 datetime.utcnow()。
    """
```

```python
@dataclass(frozen=True)
class GammaDistributionReport:
    snapshot_time: str             # ISO8601, 报告生成时间
    total_market_count: int        # raw NDJSON 行数
    active_market_count: int       # 过滤后活跃数
    overall_percentiles: dict      # {field_name: {p5, p10, p25, p50, p75, p90, p95, p99}}
    by_category: dict              # {category: {market_count, percentiles}}
    days_to_resolution_buckets: dict   # {bucket_label: market_count}
    cross_tab: dict                # {(days_bucket, volume_bucket): market_count}
    candidate_tier_thresholds: dict  # 数据驱动的 tier 阈值建议（见 1.3）
    notes: list[str]               # 数据质量警告（缺失字段、异常值数量等）
```

**实现要点**：
- 字段读取必须用 fallback：`volume24hr = market.get("volume24hrClob") or market.get("volume24hr") or 0.0`（参考 `watchlist.py:221` 的现有写法）
- `days_to_resolution = (parsed(endDate) - now).days`；endDate 缺失或解析失败 → 跳过该市场，记入 `notes`
- 百分位用 numpy 或 statistics.quantiles，但**不要新增 numpy 依赖**（先看 requirements.txt，如果没有 numpy 用 statistics.quantiles 即可）
- `days_to_resolution_buckets` 用以下桶（与方案 §1.2 文献区间对齐）：
  - `<7天`, `7-14天`, `14-30天`, `30-90天`, `90-180天`, `>180天`, `已过期/未知`
- `cross_tab` 二维：`days_bucket × volume_bucket`（volume_bucket = `<$100, $100-1k, $1k-10k, $10k-100k, >$100k`）

### 1.2 CLI 子命令 `analyze-gamma-distribution`

在 `cli.py` 增加：

```bash
poly-strategy analyze-gamma-distribution \
    --raw data/gamma-raw-2026-05-12.ndjson \
    --out-md reports/gamma-distribution-2026-05-12.md \
    --out-json reports/gamma-distribution-2026-05-12.json \
    [--include-inactive]
```

参数：
- `--raw` 必填，raw Gamma NDJSON 路径
- `--out-md` 必填，markdown 报告输出路径
- `--out-json` 必填，结构化 JSON 输出路径（用于后续比较 / 加载）
- `--include-inactive` 默认关闭

### 1.3 数据驱动的 tier 阈值候选（核心产出）

报告必须包含一个**基于实际分布的 tier 阈值建议表**，让 Q1 有数据可填。规则：

- `headline` tier 阈值 = volume24hr 的 P90
- `mid` tier 下限 = volume24hr 的 P50
- `longtail` tier 下限 = volume24hr 的 P10
- `dead` tier 上限 = volume24hr 的 P10

`liquidity` 同理用 P90/P50/P10。

距 resolution：默认推荐区间 = 数据中 `14-90 天` 桶（与方案 §1.2 文献区间对齐）。

**输出格式**：

```markdown
## 数据驱动的 tier 阈值候选

按 volume24hr 分位数（活跃市场，N=X）：

| Tier | volume24hr 区间 | 实际市场数 | 占比 |
|---|---|---:|---:|
| headline | ≥ $X (P90) | N | XX% |
| mid | $X - $X (P50-P90) | N | XX% |
| longtail | $X - $X (P10-P50) | N | XX% |
| dead | < $X (<P10) | N | XX% |

按 liquidity 分位数：（同上格式）

**距 resolution**:
- 14-90 天桶：N 个市场（XX%）—— 本研究的目标区间
- 30-14 天桶（学术文献的最低效区间）：N 个市场
```

### 1.4 报告 markdown 模板

整份报告至少包含以下章节（按此顺序）：

1. **基本统计** —— total / active / 缺 endDate 数 / 缺 category 数
2. **总体分布百分位** —— volume24hr / volume1wk / liquidity 各列出 P5/P10/P25/P50/P75/P90/P95/P99
3. **按 category 切片** —— top 10 category 的 market_count 和 P50 volume24hr
4. **距 resolution 桶分布** —— 7 个桶 + 占比
5. **二维 cross-tab** —— `days_to_resolution × volume24hr` —— 用于看"长尾 + 远期 resolution"组合的真实容量
6. **§1.3 候选阈值表** —— Q1 决议直接抄
7. **数据质量警告** —— `notes` 字段内容

---

## 2. 测试要求

### 2.1 `tests/test_longtail_research.py`（新建）

```python
def test_analyze_gamma_distribution_basic(tmp_path):
    """构造 10 行合成 NDJSON（5 个 active + 5 个 inactive），
    验证 active_market_count=5，total=10。"""

def test_percentile_computation_correctness():
    """构造已知分布（如 0..99 一百个值），验证 P50≈49, P90≈89。"""

def test_days_to_resolution_bucketing():
    """构造 endDate 跨越所有 7 个桶的市场，验证每桶计数正确。"""

def test_endDate_missing_or_malformed_recorded_in_notes():
    """缺 endDate 或格式错误的市场被跳过且 notes 记录数量。"""

def test_category_fallback():
    """优先用 'category'，缺失时用 'categorySlug'，都没有时归类 'unknown'。"""

def test_candidate_tier_thresholds_match_percentiles():
    """tier 阈值精确等于报告里的 P10/P50/P90。"""

def test_cli_smoke(tmp_path, capsys):
    """跑一遍 CLI，确认 markdown + json 文件都生成、字段齐全。"""
```

### 2.2 不需要 mock 外部 API

DS 不需要真的去打 Gamma API。**直接读已有的 raw NDJSON 文件即可**（用户/方案 author 会提供）。如果没有，从一个最小 fixture 走通流程：

```json
{"market_id": "test-1", "volume24hr": 1000.5, "liquidityClob": 5000, "endDate": "2026-06-15T00:00:00Z", "category": "politics", "enableOrderBook": true, "acceptingOrders": true}
```

---

## 3. 不要做的事

- ❌ **不要**新增对 numpy / pandas / scipy 的依赖（用 statistics + 标准库够了）。如果觉得必要，先在 PR 描述里说明。
- ❌ **不要**调用任何外部 API（包括 Gamma / CLOB）。本任务纯本地分析。
- ❌ **不要**把 `longtail_research.py` 接入 `scanner` / `realtime` / `paper` / `execution`。它是 research-only 工具。
- ❌ **不要**计算 spread（raw Gamma 没有；放到独立 task #03）。
- ❌ **不要**修改 `collectors.py` / `watchlist.py` / 任何现有模块。
- ❌ **不要**自动生成可执行交易建议。报告纯粹是研究数据。

---

## 4. 完成定义（DoD）

- [ ] `pytest tests/test_longtail_research.py` 全绿
- [ ] 整套 `pytest` 0 失败、0 新 warning
- [ ] CLI smoke：在一份合成 fixture 上跑通，生成两个输出文件
- [ ] PR 描述贴出：
  - 一段合成 fixture 的样例
  - markdown 报告的"§1.3 候选阈值表"和"基本统计"两段截图（用代码块即可）
  - JSON 输出的 schema 顶层 keys 列表
- [ ] 如果 raw NDJSON 实际存在（`data/` 下），DS 也可以跑一遍真实数据并贴结果（可选，加分项）

---

## 5. PR 标题与描述模板

**标题**：`Add gamma distribution analysis utility for Q1 thresholds`

**描述**：
```
Implements DS task pack #02 (Gamma distribution reality-check) per
docs/plans/2026-05-12-ds-pkg-02-gamma-distribution.md.

Adds research-only analysis utility to compute volume/liquidity/days
distributions from raw Gamma NDJSON. Output is a markdown report +
JSON snapshot intended to inform §9 Q1 (long-tail tier thresholds).

What this is NOT:
- Not part of the production scanner / realtime / execution path
- Does not touch fees, watchlist, or existing collectors
- Does not call any external API at runtime

Test fixture: <sample line>
Sample report excerpt: <thresholds table>
```

---

## 6. 如果 DS 遇到不确定情况

- raw NDJSON 实际字段和文档描述的对不上 → grep 现有 `watchlist.py` 的字段读法照抄
- 距 resolution 的时区处理 → 默认 UTC（Polymarket endDate 用 UTC），但在 notes 里记一句"时区按 UTC 解释"
- 数据中位数计算精度问题 → 用 `statistics.quantiles(data, n=100, method='inclusive')`
- 任何 schema/接口外的疑问 → **停下来在 PR 上提问**，不要凭直觉扩大范围
