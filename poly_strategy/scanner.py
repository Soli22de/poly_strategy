from typing import List

from poly_strategy.fees import polymarket_taker_fee_per_share
from poly_strategy.models import (
    BinaryMarketSnapshot,
    CollectivelyExhaustiveRule,
    ComplementRule,
    EquivalenceRule,
    ImplicationRule,
    Leg,
    MutualExclusionRule,
    Opportunity,
    VenueBinarySnapshot,
)
from poly_strategy.orderbook import Level, insufficient_liquidity, take_levels


def _depth_quantity(first: List[Level], second: List[Level]) -> float:
    return min(sum(level.size for level in first), sum(level.size for level in second))


def _buy_cost_per_share(price: float, fee_rate: float) -> float:
    return price + polymarket_taker_fee_per_share(price, fee_rate)


def find_yes_no_bundle_arbs(
    snapshot: BinaryMarketSnapshot,
    min_net_edge: float = 0.0,
) -> List[Opportunity]:
    quantity = _depth_quantity(snapshot.yes.asks, snapshot.no.asks)
    if quantity <= 0:
        return []
    if insufficient_liquidity(snapshot.yes.asks, quantity) or insufficient_liquidity(snapshot.no.asks, quantity):
        return []

    yes_fill = take_levels(snapshot.yes.asks, quantity)
    no_fill = take_levels(snapshot.no.asks, quantity)
    cost_per_share = _buy_cost_per_share(yes_fill.average_price, snapshot.fee_rate) + _buy_cost_per_share(
        no_fill.average_price,
        snapshot.fee_rate,
    )
    net_edge = 1.0 - cost_per_share

    if net_edge <= min_net_edge:
        return []

    return [
        Opportunity(
            kind="yes_no_bundle",
            quantity=quantity,
            cost_per_share=cost_per_share,
            net_edge_per_share=net_edge,
            ts=snapshot.ts,
            legs=[
                Leg(snapshot.venue, snapshot.market_id, "YES", "buy", yes_fill.average_price, quantity),
                Leg(snapshot.venue, snapshot.market_id, "NO", "buy", no_fill.average_price, quantity),
            ],
        )
    ]


def find_cross_venue_same_binary(
    first: VenueBinarySnapshot,
    second: VenueBinarySnapshot,
    min_net_edge: float = 0.0,
) -> List[Opportunity]:
    candidates = [
        _cross_candidate(first, "YES", first.yes.asks, second, "NO", second.no.asks, min_net_edge),
        _cross_candidate(second, "YES", second.yes.asks, first, "NO", first.no.asks, min_net_edge),
    ]
    return [candidate for candidate in candidates if candidate is not None]


def find_implication_arbs(
    snapshots: List[BinaryMarketSnapshot],
    rules: List[ImplicationRule],
    min_net_edge: float = 0.0,
) -> List[Opportunity]:
    by_market_id = {snapshot.market_id: snapshot for snapshot in snapshots}
    opportunities = []
    for rule in rules:
        antecedent = by_market_id.get(rule.antecedent_market_id)
        consequent = by_market_id.get(rule.consequent_market_id)
        if antecedent is None or consequent is None:
            continue
        opportunity = _implication_candidate(antecedent, consequent, min_net_edge)
        if opportunity is not None:
            opportunities.append(opportunity)
    return opportunities


def find_mutually_exclusive_arbs(
    snapshots: List[BinaryMarketSnapshot],
    rules: List[MutualExclusionRule],
    min_net_edge: float = 0.0,
) -> List[Opportunity]:
    by_market_id = {snapshot.market_id: snapshot for snapshot in snapshots}
    opportunities = []
    for rule in rules:
        first = by_market_id.get(rule.first_market_id)
        second = by_market_id.get(rule.second_market_id)
        if first is None or second is None:
            continue
        opportunity = _mutually_exclusive_candidate(first, second, min_net_edge)
        if opportunity is not None:
            opportunities.append(opportunity)
    return opportunities


def find_equivalent_arbs(
    snapshots: List[BinaryMarketSnapshot],
    rules: List[EquivalenceRule],
    min_net_edge: float = 0.0,
) -> List[Opportunity]:
    by_market_id = {snapshot.market_id: snapshot for snapshot in snapshots}
    opportunities = []
    for rule in rules:
        first = by_market_id.get(rule.first_market_id)
        second = by_market_id.get(rule.second_market_id)
        if first is None or second is None:
            continue
        opportunities.extend(
            candidate
            for candidate in [
                _two_leg_candidate("equivalent", first, "YES", first.yes.asks, second, "NO", second.no.asks, min_net_edge),
                _two_leg_candidate("equivalent", second, "YES", second.yes.asks, first, "NO", first.no.asks, min_net_edge),
            ]
            if candidate is not None
        )
    return opportunities


def find_collectively_exhaustive_arbs(
    snapshots: List[BinaryMarketSnapshot],
    rules: List[CollectivelyExhaustiveRule],
    min_net_edge: float = 0.0,
) -> List[Opportunity]:
    by_market_id = {snapshot.market_id: snapshot for snapshot in snapshots}
    opportunities = []
    for rule in rules:
        first = by_market_id.get(rule.first_market_id)
        second = by_market_id.get(rule.second_market_id)
        if first is None or second is None:
            continue
        opportunity = _two_leg_candidate(
            "collectively_exhaustive",
            first,
            "YES",
            first.yes.asks,
            second,
            "YES",
            second.yes.asks,
            min_net_edge,
        )
        if opportunity is not None:
            opportunities.append(opportunity)
    return opportunities


def find_complement_arbs(
    snapshots: List[BinaryMarketSnapshot],
    rules: List[ComplementRule],
    min_net_edge: float = 0.0,
) -> List[Opportunity]:
    by_market_id = {snapshot.market_id: snapshot for snapshot in snapshots}
    opportunities = []
    for rule in rules:
        first = by_market_id.get(rule.first_market_id)
        second = by_market_id.get(rule.second_market_id)
        if first is None or second is None:
            continue
        opportunities.extend(
            candidate
            for candidate in [
                _two_leg_candidate(
                    "complement_yes_bundle",
                    first,
                    "YES",
                    first.yes.asks,
                    second,
                    "YES",
                    second.yes.asks,
                    min_net_edge,
                ),
                _two_leg_candidate(
                    "complement_no_bundle",
                    first,
                    "NO",
                    first.no.asks,
                    second,
                    "NO",
                    second.no.asks,
                    min_net_edge,
                ),
            ]
            if candidate is not None
        )
    return opportunities


def _implication_candidate(
    antecedent: BinaryMarketSnapshot,
    consequent: BinaryMarketSnapshot,
    min_net_edge: float,
) -> Opportunity:
    return _two_leg_candidate(
        "implication",
        consequent,
        "YES",
        consequent.yes.asks,
        antecedent,
        "NO",
        antecedent.no.asks,
        min_net_edge,
    )


def _mutually_exclusive_candidate(
    first: BinaryMarketSnapshot,
    second: BinaryMarketSnapshot,
    min_net_edge: float,
) -> Opportunity:
    return _two_leg_candidate(
        "mutually_exclusive",
        first,
        "NO",
        first.no.asks,
        second,
        "NO",
        second.no.asks,
        min_net_edge,
    )


def _two_leg_candidate(
    kind: str,
    first: BinaryMarketSnapshot,
    first_token: str,
    first_levels: List[Level],
    second: BinaryMarketSnapshot,
    second_token: str,
    second_levels: List[Level],
    min_net_edge: float,
) -> Opportunity:
    quantity = _depth_quantity(first_levels, second_levels)
    if quantity <= 0:
        return None

    first_fill = take_levels(first_levels, quantity)
    second_fill = take_levels(second_levels, quantity)
    cost_per_share = _buy_cost_per_share(first_fill.average_price, first.fee_rate) + _buy_cost_per_share(
        second_fill.average_price,
        second.fee_rate,
    )
    net_edge = 1.0 - cost_per_share
    if net_edge <= min_net_edge:
        return None

    return Opportunity(
        kind=kind,
        quantity=quantity,
        cost_per_share=cost_per_share,
        net_edge_per_share=net_edge,
        ts=first.ts or second.ts,
        legs=[
            Leg(first.venue, first.market_id, first_token, "buy", first_fill.average_price, quantity),
            Leg(second.venue, second.market_id, second_token, "buy", second_fill.average_price, quantity),
        ],
    )


def _cross_candidate(
    first: VenueBinarySnapshot,
    first_token: str,
    first_levels: List[Level],
    second: VenueBinarySnapshot,
    second_token: str,
    second_levels: List[Level],
    min_net_edge: float,
) -> Opportunity:
    quantity = _depth_quantity(first_levels, second_levels)
    if quantity <= 0:
        return None

    first_fill = take_levels(first_levels, quantity)
    second_fill = take_levels(second_levels, quantity)
    cost_per_share = _buy_cost_per_share(first_fill.average_price, first.fee_rate) + _buy_cost_per_share(
        second_fill.average_price,
        second.fee_rate,
    )
    net_edge = 1.0 - cost_per_share
    if net_edge <= min_net_edge:
        return None

    return Opportunity(
        kind="cross_venue_same_binary",
        quantity=quantity,
        cost_per_share=cost_per_share,
        net_edge_per_share=net_edge,
        ts=first.ts or second.ts,
        legs=[
            Leg(first.venue, first.market_id, first_token, "buy", first_fill.average_price, quantity),
            Leg(second.venue, second.market_id, second_token, "buy", second_fill.average_price, quantity),
        ],
    )
