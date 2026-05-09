from typing import Optional

from poly_strategy.paper import PaperTrade, opportunity_quality


def pretrade_check_row(
    trade: PaperTrade,
    run=None,
    max_leg_count: Optional[int] = None,
    max_worst_price: Optional[float] = None,
    require_single_level: bool = False,
) -> dict:
    quality = opportunity_quality(trade.opportunity)
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
    if run is not None:
        checks.append(_check("run_observations", run.observation_count > 0, run.observation_count))
        checks.append(_check("run_duration_seconds", run.duration_seconds >= 0, run.duration_seconds))

    passed = all(check["passed"] for check in checks)
    return {
        "status": "pass" if passed else "fail",
        "passed": passed,
        "quality": quality,
        "run": _run_row(run),
        "checks": checks,
    }


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
