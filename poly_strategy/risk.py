import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def risk_check_execution_plan(
    plan_row: dict,
    state_path: Optional[Path] = None,
    kill_switch_path: Optional[Path] = None,
    max_trade_notional: Optional[float] = None,
    max_daily_loss: Optional[float] = None,
    max_daily_orders: Optional[int] = None,
    max_order_count: Optional[int] = None,
    live: bool = False,
    require_live_env: bool = True,
    now: Optional[datetime] = None,
) -> dict:
    if max_trade_notional is not None and max_trade_notional < 0:
        raise ValueError("max_trade_notional must be non-negative")
    if max_daily_loss is not None and max_daily_loss < 0:
        raise ValueError("max_daily_loss must be non-negative")
    if max_daily_orders is not None and max_daily_orders < 0:
        raise ValueError("max_daily_orders must be non-negative")
    if max_order_count is not None and max_order_count < 0:
        raise ValueError("max_order_count must be non-negative")

    now = now or datetime.now(timezone.utc)
    state = _read_risk_state(state_path)
    orders = plan_row.get("orders") or []
    notional = _plan_notional(orders)
    checks = [
        _check("kill_switch_absent", not _kill_switch_active(kill_switch_path), str(kill_switch_path) if kill_switch_path else None),
        _check("not_paused", not _is_paused(state, now), state.get("pause_until")),
        _check("order_count_positive", len(orders) > 0, len(orders)),
    ]
    if max_order_count is not None:
        checks.append(_check("max_order_count", len(orders) <= max_order_count, len(orders), max_order_count))
    if max_trade_notional is not None:
        checks.append(_check("max_trade_notional", notional <= max_trade_notional, notional, max_trade_notional))
    if max_daily_orders is not None:
        checks.append(
            _check(
                "max_daily_orders",
                _daily_orders(state, now) + len(orders) <= max_daily_orders,
                _daily_orders(state, now) + len(orders),
                max_daily_orders,
            )
        )
    if max_daily_loss is not None:
        checks.append(
            _check(
                "max_daily_worst_case_loss",
                _daily_realized_loss(state, now) + notional <= max_daily_loss,
                _daily_realized_loss(state, now) + notional,
                max_daily_loss,
            )
        )
    if live and require_live_env:
        checks.append(_check("live_env_enabled", os.environ.get("POLY_STRATEGY_ALLOW_LIVE") == "1", os.environ.get("POLY_STRATEGY_ALLOW_LIVE")))
        checks.append(_check("private_key_present", bool(os.environ.get("POLYMARKET_PRIVATE_KEY")), None))
    else:
        checks.append(_check("live_disabled_or_not_requested", True, live))

    passed = all(check["passed"] for check in checks)
    return {
        "status": "pass" if passed else "fail",
        "passed": passed,
        "dry_run_only_recommended": True,
        "planned_notional": notional,
        "planned_order_count": len(orders),
        "partial_fill_policy": "block_or_reconcile_before_next_plan",
        "reconciliation_required_before_live": bool(live),
        "checks": checks,
    }


def _plan_notional(orders: list) -> float:
    total = 0.0
    for order in orders:
        try:
            total += float(order.get("price") or 0.0) * float(order.get("size") or 0.0)
        except (TypeError, ValueError):
            continue
    return total


def _read_risk_state(path: Optional[Path]) -> dict:
    if not path or not path.exists():
        return {}
    try:
        row = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return row if isinstance(row, dict) else {}


def _kill_switch_active(path: Optional[Path]) -> bool:
    return bool(path and path.exists())


def _is_paused(state: dict, now: datetime) -> bool:
    pause_until = state.get("pause_until")
    if not pause_until:
        return False
    try:
        paused_until = datetime.fromisoformat(str(pause_until).replace("Z", "+00:00"))
    except ValueError:
        return False
    return now < paused_until


def _daily_orders(state: dict, now: datetime) -> int:
    if state.get("date") != now.date().isoformat():
        return 0
    return int(state.get("orders") or 0)


def _daily_realized_loss(state: dict, now: datetime) -> float:
    if state.get("date") != now.date().isoformat():
        return 0.0
    return float(state.get("realized_loss") or 0.0)


def _check(name: str, passed: bool, value, limit=None) -> dict:
    row = {"name": name, "passed": bool(passed), "value": value}
    if limit is not None:
        row["limit"] = limit
    return row
