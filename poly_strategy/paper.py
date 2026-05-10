from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, List, Optional

from poly_strategy.fees import taker_fee_per_share
from poly_strategy.models import Leg, Opportunity
from poly_strategy.orderbook import insufficient_liquidity, take_levels


@dataclass(frozen=True)
class PaperTrade:
    opportunity: Opportunity
    quantity: float
    capital_used: float
    edge: float

    @property
    def roi(self) -> float:
        if self.capital_used <= 0:
            return 0.0
        return self.edge / self.capital_used


@dataclass(frozen=True)
class PaperRejection:
    opportunity: Opportunity
    reason: str
    available_quantity: float


@dataclass(frozen=True)
class PaperSelection:
    trades: List[PaperTrade]
    rejections: List[PaperRejection]

    @property
    def capital_used(self) -> float:
        return sum(trade.capital_used for trade in self.trades)

    @property
    def edge(self) -> float:
        return sum(trade.edge for trade in self.trades)


def select_paper_trades(
    opportunities: Iterable[Opportunity],
    max_capital_per_trade: Optional[float] = None,
    bankroll: Optional[float] = None,
    min_quantity: float = 1e-9,
    min_roi: Optional[float] = None,
    min_edge: Optional[float] = None,
) -> PaperSelection:
    if max_capital_per_trade is not None and max_capital_per_trade < 0:
        raise ValueError("max_capital_per_trade must be non-negative")
    if bankroll is not None and bankroll < 0:
        raise ValueError("bankroll must be non-negative")
    if min_quantity < 0:
        raise ValueError("min_quantity must be non-negative")
    if min_roi is not None and min_roi < 0:
        raise ValueError("min_roi must be non-negative")
    if min_edge is not None and min_edge < 0:
        raise ValueError("min_edge must be non-negative")

    ordered = sorted(list(opportunities), key=_selection_sort_key)
    remaining_bankroll = bankroll
    remaining_by_leg = _initial_leg_capacity(ordered)
    trades: List[PaperTrade] = []
    rejections: List[PaperRejection] = []

    for opportunity in ordered:
        if opportunity.cost_per_share <= 0:
            rejections.append(PaperRejection(opportunity, "invalid_cost", 0.0))
            continue
        quantity = _available_quantity(opportunity, remaining_by_leg)
        capital_cap = None
        if max_capital_per_trade is not None:
            capital_cap = max_capital_per_trade
        if remaining_bankroll is not None:
            capital_cap = remaining_bankroll if capital_cap is None else min(capital_cap, remaining_bankroll)
        if capital_cap is not None:
            quantity = min(quantity, _quantity_for_cap(opportunity, quantity, capital_cap))

        if quantity <= min_quantity:
            rejections.append(PaperRejection(opportunity, _rejection_reason(opportunity, remaining_by_leg, remaining_bankroll), quantity))
            continue

        selected_opportunity = _opportunity_at_quantity(opportunity, quantity)
        if min_roi is not None and _opportunity_roi(selected_opportunity) < min_roi:
            rejections.append(PaperRejection(selected_opportunity, "below_min_roi", quantity))
            continue
        if min_edge is not None and selected_opportunity.total_edge < min_edge:
            rejections.append(PaperRejection(selected_opportunity, "below_min_edge", quantity))
            continue
        trade = PaperTrade(
            opportunity=selected_opportunity,
            quantity=quantity,
            capital_used=quantity * selected_opportunity.cost_per_share,
            edge=quantity * selected_opportunity.net_edge_per_share,
        )
        trades.append(trade)
        for leg in opportunity.legs:
            remaining_by_leg[_leg_key(leg)] -= quantity
        if remaining_bankroll is not None:
            remaining_bankroll -= trade.capital_used

    return PaperSelection(trades=trades, rejections=rejections)


def opportunity_key(opportunity: Opportunity) -> str:
    legs = "|".join(sorted(f"{leg.venue}:{leg.market_id}:{leg.token}:{leg.side}" for leg in opportunity.legs))
    return f"{opportunity.kind}:{legs}"


def opportunity_to_row(opportunity: Opportunity) -> dict:
    return {
        "kind": opportunity.kind,
        "ts": opportunity.ts,
        "quantity": opportunity.quantity,
        "cost_per_share": opportunity.cost_per_share,
        "net_edge_per_share": opportunity.net_edge_per_share,
        "total_edge": opportunity.total_edge,
        "quality": opportunity_quality(opportunity),
        "key": opportunity_key(opportunity),
        "legs": [_leg_to_row(leg) for leg in opportunity.legs],
    }


def trade_to_row(trade: PaperTrade) -> dict:
    row = opportunity_to_row(trade.opportunity)
    row.update(
        {
            "paper_quantity": trade.quantity,
            "paper_capital_used": trade.capital_used,
            "paper_edge": trade.edge,
            "paper_roi": trade.roi,
        }
    )
    return row


def rejection_to_row(rejection: PaperRejection) -> dict:
    row = opportunity_to_row(rejection.opportunity)
    row.update({"reason": rejection.reason, "available_quantity": rejection.available_quantity})
    return row


def _selection_sort_key(opportunity: Opportunity) -> tuple:
    roi = _opportunity_roi(opportunity)
    return (-roi, -opportunity.net_edge_per_share, -opportunity.total_edge, opportunity_key(opportunity))


def opportunity_quality(opportunity: Opportunity) -> dict:
    return {
        "roi": _opportunity_roi(opportunity),
        "leg_count": len(opportunity.legs),
        "market_count": len({leg.market_id for leg in opportunity.legs}),
        "min_leg_quantity": min((leg.quantity for leg in opportunity.legs), default=0.0),
        "min_top_level_size": min((leg.levels[0].size for leg in opportunity.legs if leg.levels), default=0.0),
        "uses_multiple_price_levels": any(
            leg.worst_price is not None and abs(leg.worst_price - leg.average_price) > 1e-12
            for leg in opportunity.legs
        ),
        "max_worst_price": max((leg.worst_price for leg in opportunity.legs if leg.worst_price is not None), default=0.0),
    }


def _opportunity_roi(opportunity: Opportunity) -> float:
    if opportunity.cost_per_share <= 0:
        return 0.0
    return opportunity.net_edge_per_share / opportunity.cost_per_share


def _quantity_for_cap(opportunity: Opportunity, max_quantity: float, capital_cap: float) -> float:
    if capital_cap <= 0 or max_quantity <= 0:
        return 0.0
    if not _can_reprice(opportunity):
        return min(max_quantity, capital_cap / opportunity.cost_per_share)
    if _opportunity_notional(opportunity, max_quantity) <= capital_cap:
        return max_quantity

    low = 0.0
    high = max_quantity
    for _ in range(50):
        midpoint = (low + high) / 2
        if midpoint <= 0:
            break
        if _opportunity_notional(opportunity, midpoint) <= capital_cap:
            low = midpoint
        else:
            high = midpoint
    return low


def _opportunity_at_quantity(opportunity: Opportunity, quantity: float) -> Opportunity:
    if not _can_reprice(opportunity):
        return opportunity

    payout_per_share = opportunity.cost_per_share + opportunity.net_edge_per_share
    cost_per_share = _opportunity_notional(opportunity, quantity) / quantity
    return Opportunity(
        kind=opportunity.kind,
        quantity=quantity,
        cost_per_share=cost_per_share,
        net_edge_per_share=payout_per_share - cost_per_share,
        legs=[_leg_at_quantity(leg, quantity) for leg in opportunity.legs],
        ts=opportunity.ts,
    )


def _can_reprice(opportunity: Opportunity) -> bool:
    if not opportunity.legs:
        return False
    return all(leg.levels and not insufficient_liquidity(leg.levels, min(opportunity.quantity, leg.quantity)) for leg in opportunity.legs)


def _opportunity_notional(opportunity: Opportunity, quantity: float) -> float:
    if quantity <= 0:
        return 0.0
    return sum(_leg_notional(leg, quantity) for leg in opportunity.legs)


def _leg_notional(leg: Leg, quantity: float) -> float:
    total = 0.0
    remaining = quantity
    for level in leg.levels or []:
        if remaining <= 0:
            break
        used = min(remaining, level.size)
        total += used * (level.price + taker_fee_per_share(leg.venue, level.price, leg.fee_rate))
        remaining -= used
    return total


def _leg_at_quantity(leg: Leg, quantity: float) -> Leg:
    if not leg.levels:
        return leg
    fill = take_levels(leg.levels, quantity)
    return Leg(
        venue=leg.venue,
        market_id=leg.market_id,
        token=leg.token,
        side=leg.side,
        average_price=fill.average_price,
        quantity=quantity,
        token_id=leg.token_id,
        worst_price=fill.worst_price,
        fee_rate=leg.fee_rate,
        levels=leg.levels,
    )


def _initial_leg_capacity(opportunities: List[Opportunity]) -> dict:
    capacity = defaultdict(float)
    for opportunity in opportunities:
        for leg in opportunity.legs:
            key = _leg_key(leg)
            capacity[key] = max(capacity[key], opportunity.quantity)
    return capacity


def _available_quantity(opportunity: Opportunity, remaining_by_leg: dict) -> float:
    if not opportunity.legs:
        return 0.0
    return min([opportunity.quantity] + [remaining_by_leg[_leg_key(leg)] for leg in opportunity.legs])


def _rejection_reason(opportunity: Opportunity, remaining_by_leg: dict, remaining_bankroll: Optional[float]) -> str:
    if remaining_bankroll is not None and remaining_bankroll <= 0:
        return "bankroll_exhausted"
    if _available_quantity(opportunity, remaining_by_leg) <= 0:
        return "overlapping_liquidity_reserved"
    return "below_min_quantity"


def _leg_key(leg: Leg) -> tuple:
    return (leg.venue, leg.market_id, leg.token, leg.side)


def _leg_to_row(leg: Leg) -> dict:
    return {
        "venue": leg.venue,
        "market_id": leg.market_id,
        "token": leg.token,
        "token_id": leg.token_id,
        "side": leg.side,
        "average_price": leg.average_price,
        "worst_price": leg.worst_price,
        "quantity": leg.quantity,
    }
