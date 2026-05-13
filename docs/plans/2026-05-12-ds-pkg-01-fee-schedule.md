# DS 指令包 #01：Fee Schedule 元数据升级

**主方案**：[`2026-05-11-longtail-resolution-thesis.md`](./2026-05-11-longtail-resolution-thesis.md) §横切 1

**作者**：方案 author 起草，DS 执行
**review 链路**：DS → 方案 author → 同学（PR）
**预计代码量**：~150 行（实现 + 测试）
**预计 DS 单次 token 消耗**：< 30k

---

## 0. 上下文（DS 必读）

Polymarket 当前 fee 公式：

```text
fees = feeRate * shares * price * (1 - price)
```

**重要事实**（不要重新发明）：
- 项目代码**已经**在 `collectors.py:1382` 的 `market_fee_rate(market)` 里从 Gamma `feeSchedule.rate` 拿到每个市场自己的费率，写入 `BinaryMarketSnapshot.fee_rate`。**不要硬编码 category 阶梯，也不要假装代码当前只有一个全局常量。**
- 真正的缺口：Gamma `feeSchedule` 还有 `rebateRate`、`takerOnly`、`feeType` 等字段，**目前没保存进 snapshot**。这导致：
  - maker rebate 没法在诊断里展示真实值
  - 未来 fee 政策变化（如调整 rebateRate）无法在历史 snapshot 上回放
- 本任务的范围是**补齐元数据**，不改变现有 fee 计算逻辑。

---

## 1. 任务清单

### 1.1 `poly_strategy/models.py`

修改 `BinaryMarketSnapshot` dataclass，**保持 frozen + 向后兼容**：

```python
@dataclass(frozen=True)
class BinaryMarketSnapshot:
    market_id: str
    venue: str
    yes: OrderBook
    no: OrderBook
    fee_rate: float                      # 保留，等同 fee_schedule_rate
    ts: Optional[str] = None
    fee_schedule_rate: Optional[float] = None    # 新增
    fee_rebate_rate: Optional[float] = None      # 新增
    fee_taker_only: Optional[bool] = None        # 新增
    fee_type: Optional[str] = None               # 新增
```

**约束**：
- 4 个新字段必须全部 Optional + 默认 None，否则旧 NDJSON 加载会破。
- `fee_rate` 字段保留语义不变（taker 费率），等同 `fee_schedule_rate`。代码内部以 `fee_schedule_rate` 为权威；外部已有调用方继续读 `fee_rate` 不破坏。

### 1.2 `poly_strategy/collectors.py`

**新增函数**（紧贴现有 `market_fee_rate` 之后）：

```python
def market_fee_schedule(market: dict) -> dict:
    """从 Gamma market payload 读完整 feeSchedule 元数据。

    返回 dict 包含：
      - rate: float (taker 费率，feesEnabled=False 时 0.0)
      - rebate_rate: Optional[float]
      - taker_only: Optional[bool]
      - fee_type: Optional[str]

    所有字段缺失时为 None（而非 0/False/""），让下游能区分"未提供"和"已声明为 0"。
    """
```

**修改 snapshot 写入处**（搜 `market_fee_rate(market)` 的调用点）：
- 当前在 ~line 1033 写 `"fee_rate": market_fee_rate(market)`。
- 改为同时写：
  ```python
  schedule = market_fee_schedule(market)
  ...
  "fee_rate": schedule["rate"],
  "fee_schedule_rate": schedule["rate"],
  "fee_rebate_rate": schedule.get("rebate_rate"),
  "fee_taker_only": schedule.get("taker_only"),
  "fee_type": schedule.get("fee_type"),
  ```
- Kalshi 路径（~line 758）**不变**，新字段写 None（Kalshi 不暴露 Polymarket-style feeSchedule）。

**约束**：
- 不要修改 `market_fee_rate` 的签名或行为；它是其他模块的稳定 API。
- 不要给所有调用方都强制升级；按需补字段即可。

### 1.3 `poly_strategy/backtest.py`

修改 NDJSON 加载处（line 386 附近，构造 `BinaryMarketSnapshot` 的地方）：
- 读 `fee_rate` 保持不变。
- 增读：
  ```python
  fee_schedule_rate=row.get("fee_schedule_rate"),
  fee_rebate_rate=row.get("fee_rebate_rate"),
  fee_taker_only=row.get("fee_taker_only"),
  fee_type=row.get("fee_type"),
  ```
- 旧 NDJSON 缺失这些字段时，全部为 None，不影响现有 replay。

### 1.4 `poly_strategy/maker.py`

修改 maker diagnostics 输出（搜 `fee_rate_assumption`，~line 1625 和 1665）：
- 当前写 `"fee_rate_assumption": snapshot.fee_rate`。
- 增加：
  ```python
  "rebate_rate": snapshot.fee_rebate_rate,
  "taker_only": snapshot.fee_taker_only,
  ```
- **关键约束**：rebate 只作为诊断信息呈现，**不要**把 rebate 当成"确定收入"加到 maker 路径的 net edge 计算里。Maker fill 概率本身没建模，rebate 是条件期望，不是已实现收益。任何 fee net 计算保持现状。

### 1.5 `poly_strategy/fees.py`

**主公式不变**。如果需要新增 category fallback：
- 单独的 helper `polymarket_category_fallback_rate(category: str) -> Optional[float]`
- **不默认启用**；只在显式 opt-in 时使用（参数名 `allow_category_fallback: bool = False`）
- fallback 表硬编码在文件顶部 dict，附 TODO 注释：源 URL（`docs.polymarket.com/trading/fees`）+ 复核日期（YYYY-MM-DD）
- **本 PR 不要求实现这个 helper**——如果加，也只暴露函数，不接入主路径。

---

## 2. 测试要求

在 `tests/test_collectors.py`、`tests/test_backtest.py`、`tests/test_maker.py` 增加测试。如果对应文件不存在，新建。

### 2.1 `tests/test_collectors.py`（新增或扩展）

```python
def test_market_fee_schedule_full():
    market = {
        "feesEnabled": True,
        "feeSchedule": {
            "rate": 0.02,
            "rebateRate": 0.01,
            "takerOnly": True,
            "feeType": "linear_price_squared",
        },
    }
    result = market_fee_schedule(market)
    assert result["rate"] == 0.02
    assert result["rebate_rate"] == 0.01
    assert result["taker_only"] is True
    assert result["fee_type"] == "linear_price_squared"

def test_market_fee_schedule_disabled():
    market = {"feesEnabled": False, "feeSchedule": {"rate": 0.02}}
    result = market_fee_schedule(market)
    assert result["rate"] == 0.0
    # 其他字段未启用时返回 None
    assert result["rebate_rate"] is None

def test_market_fee_schedule_partial():
    # 只有 rate 字段时，其他字段 None
    market = {"feesEnabled": True, "feeSchedule": {"rate": 0.015}}
    result = market_fee_schedule(market)
    assert result["rate"] == 0.015
    assert result["rebate_rate"] is None
    assert result["taker_only"] is None
    assert result["fee_type"] is None
```

### 2.2 `tests/test_backtest.py`（扩展）

```python
def test_replay_handles_legacy_snapshot_without_fee_schedule_fields(tmp_path):
    """旧 NDJSON 只有 fee_rate，没有新字段，应该正常 replay。"""
    # 构造一行只含 fee_rate 的 snapshot, 验证 replay 不抛错

def test_replay_preserves_new_fee_schedule_fields(tmp_path):
    """新 NDJSON 带全套字段，replay 后 snapshot 上字段可访问。"""
```

### 2.3 `tests/test_maker.py`（扩展）

```python
def test_maker_diagnostics_include_rebate_when_present():
    """snapshot 带 fee_rebate_rate 时，diagnostics 中应该包含 rebate_rate 字段。"""

def test_maker_diagnostics_rebate_missing_when_absent():
    """snapshot 不带 fee_rebate_rate 时，diagnostics 中 rebate_rate 为 None（或不影响净 edge）。"""

def test_maker_net_edge_does_not_credit_rebate():
    """关键：maker 路径的 net edge 计算不能因为 rebate 存在而提高。"""
```

---

## 3. 不要做的事

明确**out of scope**：

- ❌ 不要改 `BinaryMarketSnapshot.fee_rate` 的语义或类型
- ❌ 不要把 category 阶梯写进 `fees.py` 的主路径
- ❌ 不要在 `fee_adjusted_buy_cost` / scanner 的 net edge 计算里加入 rebate
- ❌ 不要修改 Kalshi 路径的 fee 处理
- ❌ 不要"顺便"修 `fee_adjusted_buy_cost` 永远走 polymarket fee 的潜在问题（独立任务）
- ❌ 不要重命名现有字段
- ❌ 不要触碰 watchlist / scanner / 任何 longtail/T1-T4 相关模块

---

## 4. 完成定义（DoD）

- [ ] `pytest tests/test_collectors.py tests/test_backtest.py tests/test_maker.py` 全绿
- [ ] `pytest` 整套 0 失败、0 新 warning
- [ ] `mypy poly_strategy/models.py poly_strategy/collectors.py poly_strategy/backtest.py poly_strategy/maker.py` 通过（如果项目用 mypy）
- [ ] 旧 NDJSON 样本（`data/` 下任意现存 snapshot 文件）能被 `replay_ndjson` 加载不抛错
- [ ] 在 PR 描述里贴出：
  - 一段真实 Gamma market payload 中 `feeSchedule` 字段的实际形状（从一个最近的 raw market dump 里 copy）
  - 一份新生成 snapshot NDJSON 的样例行（含新字段）
  - `pytest -q` 的最后 3 行输出

---

## 5. PR 标题与描述模板

**标题**：`Save full feeSchedule metadata in binary snapshots`

**描述**：
```
Implements §横切 1 of the longtail thesis plan (post-review version).

What changes:
- BinaryMarketSnapshot gains 4 optional fee_schedule_* fields.
- collectors.market_fee_schedule() reads them from Gamma payload.
- backtest replay reads them with backward-compat defaults.
- maker diagnostics surface rebate_rate (as info, not as credited income).

What does NOT change:
- Existing fee_rate field semantics.
- fees.py main formula.
- Kalshi path.
- Any net-edge / scanner / watchlist logic.

Tests: <pytest output snippet>

Verified backward compat: <how>
```

---

## 6. 如果 DS 遇到不确定情况

- 找不到指定行号 → grep 关键函数名，code shape 可能因小重构有偏移，按语义对齐即可
- 测试样例数据缺失 → 在 `tests/fixtures/` 下新建最小 JSON fixture
- 任何 schema/接口外的疑问 → **停下来在 PR 上提问**，不要凭直觉扩大范围
