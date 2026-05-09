from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, List, Optional

from poly_strategy.models import Leg, Opportunity


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
) -> PaperSelection:
    if max_capital_per_trade is not None and max_capital_per_trade < 0:
        raise ValueError("max_capital_per_trade must be non-negative")
    if bankroll is not None and bankroll < 0:
        raise ValueError("bankroll must be non-negative")
    if min_quantity < 0:
        raise ValueError("min_quantity must be non-negative")

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
        if max_capital_per_trade is not None:
            quantity = min(quantity, max_capital_per_trade / opportunity.cost_per_share)
        if remaining_bankroll is not None:
            quantity = min(quantity, remaining_bankroll / opportunity.cost_per_share)

        if quantity <= min_quantity:
            rejections.append(PaperRejection(opportunity, _rejection_reason(opportunity, remaining_by_leg, remaining_bankroll), quantity))
            continue

        trade = PaperTrade(
            opportunity=opportunity,
            quantity=quantity,
            capital_used=quantity * opportunity.cost_per_share,
            edge=quantity * opportunity.net_edge_per_share,
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
    roi = opportunity.net_edge_per_share / opportunity.cost_per_share if opportunity.cost_per_share > 0 else 0.0
    return (-roi, -opportunity.net_edge_per_share, -opportunity.total_edge, opportunity_key(opportunity))


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
