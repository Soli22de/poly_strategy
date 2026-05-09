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
                _daily_risk_used(state, now) + notional <= max_daily_loss,
                _daily_risk_used(state, now) + notional,
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


def update_risk_state_from_execution_result(
    plan_row: dict,
    responses: list,
    state_path: Path,
    reconciliation: Optional[dict] = None,
    realized_loss: float = 0.0,
    now: Optional[datetime] = None,
) -> dict:
    if realized_loss < 0:
        raise ValueError("realized_loss must be non-negative")
    now = now or datetime.now(timezone.utc)
    state = _read_risk_state(state_path)
    state = _reset_daily_state_if_needed(state, now)
    reconciliation = reconciliation or {}
    orders = plan_row.get("orders") or []
    dry_run = bool(plan_row.get("dry_run", True))
    submitted_count = 0 if dry_run else int(reconciliation.get("submitted_order_count") or 0)
    attempted_count = 0 if dry_run else len(orders)
    notional = 0.0 if dry_run else _plan_notional(orders)
    needs_reconciliation = (not dry_run) and bool(reconciliation.get("needs_reconciliation", True))

    state["orders"] = int(state.get("orders") or 0) + submitted_count
    state["attempted_orders"] = int(state.get("attempted_orders") or 0) + attempted_count
    state["realized_loss"] = float(state.get("realized_loss") or 0.0) + realized_loss
    state["reserved_notional"] = float(state.get("reserved_notional") or 0.0) + notional
    state["pending_reconciliation"] = bool(state.get("pending_reconciliation")) or needs_reconciliation
    state["last_execution"] = {
        "ts": _utc_iso(now),
        "dry_run": dry_run,
        "opportunity_key": plan_row.get("opportunity_key"),
        "planned_notional": _plan_notional(orders),
        "submitted_order_count": submitted_count,
        "attempted_order_count": attempted_count,
        "response_count": len(responses or []),
        "reconciliation_status": reconciliation.get("status"),
        "needs_reconciliation": needs_reconciliation,
    }
    _write_risk_state(state_path, state)
    return dict(state)


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


def _daily_risk_used(state: dict, now: datetime) -> float:
    if state.get("date") != now.date().isoformat():
        return 0.0
    return float(state.get("realized_loss") or 0.0) + float(state.get("reserved_notional") or 0.0)


def _reset_daily_state_if_needed(state: dict, now: datetime) -> dict:
    date = now.date().isoformat()
    if state.get("date") == date:
        state.setdefault("orders", 0)
        state.setdefault("attempted_orders", 0)
        state.setdefault("realized_loss", 0.0)
        state.setdefault("reserved_notional", 0.0)
        return dict(state)
    return {
        "type": "risk_state",
        "date": date,
        "orders": 0,
        "attempted_orders": 0,
        "realized_loss": 0.0,
        "reserved_notional": 0.0,
        "pending_reconciliation": False,
    }


def _write_risk_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _check(name: str, passed: bool, value, limit=None) -> dict:
    row = {"name": name, "passed": bool(passed), "value": value}
    if limit is not None:
        row["limit"] = limit
    return row
