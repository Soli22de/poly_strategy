"""Shared helpers for research-only simulation scripts."""
from __future__ import annotations

import statistics
from typing import Any

DEFAULT_TICK_SIZE = 0.001
EPSILON = 1e-9


def simulate_buy_cost(asks: list[tuple[float, float]], target_units: float) -> tuple[float, float, float]:
    """Walk an ask ladder and return (units_filled, total_cost, avg_price_paid)."""
    filled = 0.0
    cost = 0.0
    for price, size in asks:
        if filled >= target_units:
            break
        take = min(float(size), target_units - filled)
        if take <= 0:
            continue
        cost += take * float(price)
        filled += take
    avg_price = cost / filled if filled > 0 else 0.0
    return filled, cost, avg_price


def fee_rate_from_book(book: dict[str, Any]) -> float:
    member = book.get("member") or {}
    return float(book.get("fee_rate", member.get("fee_rate", 0.0)) or 0.0)


def simulate_basket_fill(book_data: list[dict[str, Any]], requested_size: float) -> dict[str, Any]:
    """Simulate a mutually-exclusive YES basket at the common executable size.

    A basket only pays out for the minimum size completed across all legs. If
    one leg has 2 units of ask depth and the requested basket is 10 units, the
    executable basket is 2 units, not 10.
    """
    requested_size = float(requested_size)
    requested_fills: list[float] = []
    for book in book_data:
        filled, _, _ = simulate_buy_cost(book.get("asks") or [], requested_size)
        requested_fills.append(filled)

    effective_size = min(requested_fills) if requested_fills else 0.0
    effective_size = max(0.0, min(effective_size, requested_size))

    total_cost = 0.0
    total_fee = 0.0
    per_member: list[dict[str, Any]] = []
    if effective_size > EPSILON:
        for book in book_data:
            filled, cost, avg_px = simulate_buy_cost(book.get("asks") or [], effective_size)
            fee_rate = fee_rate_from_book(book)
            fee = fee_rate * avg_px * (1.0 - avg_px) * filled
            total_cost += cost
            total_fee += fee
            member = book.get("member") or {}
            per_member.append(
                {
                    "member": str(member.get("question") or "")[:40],
                    "filled": filled,
                    "avg_px": avg_px,
                    "cost": cost,
                    "fee": fee,
                }
            )

    edge_dollars = effective_size - total_cost - total_fee
    edge_pct = edge_dollars / effective_size if effective_size > EPSILON else 0.0
    return {
        "size": requested_size,
        "requested_size": requested_size,
        "effective_size": effective_size,
        "max_fillable_units": effective_size,
        "is_full_size_fillable": effective_size + EPSILON >= requested_size,
        "total_cost": total_cost,
        "total_fee": total_fee,
        "edge_dollars": edge_dollars if effective_size > EPSILON else 0.0,
        "edge_pct": edge_pct,
        "per_member": per_member,
    }


def maker_target_price(
    best_bid: float,
    best_ask: float,
    markup: float,
    tick_size: float = DEFAULT_TICK_SIZE,
) -> float | None:
    """Return a non-crossing maker bid target or None if the spread is too tight."""
    best_bid = float(best_bid)
    best_ask = float(best_ask)
    markup = float(markup)
    tick_size = float(tick_size)
    if best_ask <= 0 or best_bid < 0 or tick_size <= 0:
        return None
    lower = best_bid + tick_size
    upper = best_ask - tick_size
    if upper + EPSILON < lower:
        return None
    target = max(best_ask - markup, lower)
    target = min(target, upper)
    if target <= 0 or target + EPSILON >= best_ask:
        return None
    return round(target, 6)


def zero_maker_stats(n_total_days: int, reason: str) -> dict[str, Any]:
    return {
        "targets": [],
        "n_filled_days": 0,
        "n_total_days": n_total_days,
        "fill_rate": 0.0,
        "avg_edge_given_fill": 0.0,
        "median_edge_given_fill": 0.0,
        "expected_daily_edge_dollars": 0.0,
        "avg_min_leg_sell_size": 0.0,
        "avg_effective_basket_size": 0.0,
        "max_effective_basket_size": 0.0,
        "n_positive_edge_days": 0,
        "n_negative_edge_days": 0,
        "skipped_reason": reason,
    }


def capped_expected_daily_edge(
    filled_days: list[dict[str, Any]],
    n_total_days: int,
    basket_size: float,
) -> dict[str, float]:
    """Compute daily maker PnL capped by observed trade size on the thinnest leg."""
    if n_total_days <= 0 or not filled_days:
        return {
            "expected_daily_edge_dollars": 0.0,
            "avg_effective_basket_size": 0.0,
            "max_effective_basket_size": 0.0,
        }

    basket_size = float(basket_size)
    effective_sizes = [
        min(basket_size, max(0.0, float(day.get("min_leg_sell_size") or 0.0)))
        for day in filled_days
    ]
    pnl = [
        float(day.get("edge") or 0.0) * size
        for day, size in zip(filled_days, effective_sizes)
    ]
    return {
        "expected_daily_edge_dollars": sum(pnl) / n_total_days,
        "avg_effective_basket_size": statistics.mean(effective_sizes) if effective_sizes else 0.0,
        "max_effective_basket_size": max(effective_sizes) if effective_sizes else 0.0,
    }


def qualifying_trade_size(trades: list[dict[str, Any]], target_price: float) -> float:
    """Return total sell size that could have hit a resting bid at target_price."""
    target_price = float(target_price)
    total = 0.0
    for trade in trades:
        try:
            price = float(trade.get("price") or 0.0)
            size = float(trade.get("size") or 0.0)
        except (TypeError, ValueError):
            continue
        if price <= target_price and size > 0:
            total += size
    return total
