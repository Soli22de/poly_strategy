from typing import Optional

from poly_strategy.paper import PaperTrade, opportunity_quality


def pretrade_check_row(
    trade: PaperTrade,
    run=None,
    max_leg_count: Optional[int] = None,
    max_worst_price: Optional[float] = None,
    require_single_level: bool = False,
    plan=None,
    min_limit_edge_per_share: Optional[float] = None,
    min_limit_roi: Optional[float] = None,
) -> dict:
    if min_limit_edge_per_share is not None and min_limit_edge_per_share < 0:
        raise ValueError("min_limit_edge_per_share must be non-negative")
    if min_limit_roi is not None and min_limit_roi < 0:
        raise ValueError("min_limit_roi must be non-negative")

    quality = opportunity_quality(trade.opportunity)
    limit_summary = _limit_price_summary(trade, plan)
    checks = [
        _check("positive_edge", trade.edge > 0, trade.edge),
        _check("positive_roi", trade.roi > 0, trade.roi),
        _check("all_buy_legs", all(leg.side.lower() == "buy" for leg in trade.opportunity.legs), None),
        _check("all_token_ids_present", all(bool(leg.token_id) for leg in trade.opportunity.legs), None),
    ]
    if max_leg_count is not None:
        checks.append(_check("max_leg_count", len(trade.opportunity.legs) <= max_leg_count, len(trade.opportunity.legs), max_leg_count))
    if max_worst_price is not None:
        checks.append(_check("max_worst_price", quality["max_worst_price"] <= max_worst_price, quality["max_worst_price"], max_worst_price))
    if require_single_level:
        checks.append(_check("single_level_fill", not quality["uses_multiple_price_levels"], quality["uses_multiple_price_levels"], False))
    if min_limit_edge_per_share is not None:
        checks.append(
            _check(
                "min_limit_edge_per_share",
                limit_summary is not None and limit_summary["edge_per_share"] >= min_limit_edge_per_share,
                None if limit_summary is None else limit_summary["edge_per_share"],
                min_limit_edge_per_share,
            )
        )
    if min_limit_roi is not None:
        checks.append(
            _check(
                "min_limit_roi",
                limit_summary is not None and limit_summary["roi"] >= min_limit_roi,
                None if limit_summary is None else limit_summary["roi"],
                min_limit_roi,
            )
        )
    if run is not None:
        checks.append(_check("run_observations", run.observation_count > 0, run.observation_count))
        checks.append(_check("run_duration_seconds", run.duration_seconds >= 0, run.duration_seconds))

    passed = all(check["passed"] for check in checks)
    return {
        "status": "pass" if passed else "fail",
        "passed": passed,
        "quality": quality,
        "limit_price_summary": limit_summary,
        "run": _run_row(run),
        "checks": checks,
    }


def _limit_price_summary(trade: PaperTrade, plan) -> Optional[dict]:
    if plan is None:
        return None
    orders = _plan_orders(plan)
    if not orders:
        return None
    limit_cost = 0.0
    for order in orders:
        price = _order_value(order, "price")
        if price is None:
            return None
        limit_cost += price
    payout_per_share = trade.opportunity.cost_per_share + trade.opportunity.net_edge_per_share
    edge_per_share = payout_per_share - limit_cost
    return {
        "payout_per_share": payout_per_share,
        "limit_cost_per_share": limit_cost,
        "edge_per_share": edge_per_share,
        "roi": edge_per_share / limit_cost if limit_cost > 0 else 0.0,
    }


def _plan_orders(plan) -> list:
    if isinstance(plan, dict):
        return list(plan.get("orders") or [])
    return list(getattr(plan, "orders", []) or [])


def _order_value(order, key: str) -> Optional[float]:
    if isinstance(order, dict):
        value = order.get(key)
    else:
        value = getattr(order, key, None)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _check(name: str, passed: bool, value, limit=None) -> dict:
    row = {"name": name, "passed": bool(passed), "value": value}
    if limit is not None:
        row["limit"] = limit
    return row


def _run_row(run) -> Optional[dict]:
    if run is None:
        return None
    return {
        "key": run.key,
        "observation_count": run.observation_count,
        "duration_seconds": run.duration_seconds,
        "max_edge_per_share": run.max_edge_per_share,
        "start_ts": run.start_ts,
        "end_ts": run.end_ts,
    }
