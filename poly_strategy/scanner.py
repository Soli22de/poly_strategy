from collections import defaultdict
from typing import List, Optional, Tuple

from poly_strategy.fees import taker_fee_per_share
from poly_strategy.models import (
    BinaryMarketSnapshot,
    CollectivelyExhaustiveRule,
    ComplementRule,
    EquivalenceRule,
    ExhaustiveGroupRule,
    ImplicationRule,
    Leg,
    MutualExclusionRule,
    NegRiskGroupRule,
    Opportunity,
    VenueBinarySnapshot,
)
from poly_strategy.orderbook import Level, insufficient_liquidity, take_levels


def _buy_cost_per_share(venue: str, price: float, fee_rate: float) -> float:
    return price + taker_fee_per_share(venue, price, fee_rate)


def find_yes_no_bundle_arbs(
    snapshot: BinaryMarketSnapshot,
    min_net_edge: float = 0.0,
) -> List[Opportunity]:
    opportunity = _bundle_candidate(
        "yes_no_bundle",
        [
            (snapshot, "YES", snapshot.yes.asks),
            (snapshot, "NO", snapshot.no.asks),
        ],
        payout_per_share=1.0,
        min_net_edge=min_net_edge,
        ts=snapshot.ts,
    )
    if opportunity is None:
        return []
    return [opportunity]


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


def find_mutual_exclusion_basket_arbs(
    snapshots: List[BinaryMarketSnapshot],
    rules: List[MutualExclusionRule],
    min_net_edge: float = 0.0,
) -> List[Opportunity]:
    by_market_id = {snapshot.market_id: snapshot for snapshot in snapshots}
    adjacency = defaultdict(set)
    for rule in rules:
        if rule.first_market_id in by_market_id and rule.second_market_id in by_market_id:
            adjacency[rule.first_market_id].add(rule.second_market_id)
            adjacency[rule.second_market_id].add(rule.first_market_id)

    opportunities = []
    for clique in _maximal_cliques(adjacency):
        if len(clique) < 3:
            continue
        opportunity = _mutual_exclusion_basket_candidate(clique, by_market_id, min_net_edge)
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


def find_exhaustive_group_arbs(
    snapshots: List[BinaryMarketSnapshot],
    rules: List[ExhaustiveGroupRule],
    min_net_edge: float = 0.0,
) -> List[Opportunity]:
    by_market_id = {snapshot.market_id: snapshot for snapshot in snapshots}
    opportunities = []
    for rule in rules:
        opportunity = _exhaustive_group_candidate(rule.market_ids, by_market_id, min_net_edge)
        if opportunity is not None:
            opportunities.append(opportunity)
    return opportunities


def find_neg_risk_group_arbs(
    snapshots: List[BinaryMarketSnapshot],
    rules: List[NegRiskGroupRule],
    min_net_edge: float = 0.0,
) -> List[Opportunity]:
    by_market_id = {snapshot.market_id: snapshot for snapshot in snapshots}
    opportunities = []
    for rule in rules:
        market_ids = _unique_market_ids(rule.market_ids)
        if len(market_ids) < 2:
            continue
        group_snapshots = [by_market_id.get(market_id) for market_id in market_ids]
        if any(snapshot is None for snapshot in group_snapshots):
            continue

        no_opportunity = _bundle_candidate(
            kind="neg_risk_group_no_basket",
            leg_specs=[(snapshot, "NO", snapshot.no.asks) for snapshot in group_snapshots],
            payout_per_share=len(group_snapshots) - 1,
            min_net_edge=min_net_edge,
            ts=group_snapshots[0].ts,
        )
        if no_opportunity is not None:
            opportunities.append(no_opportunity)
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
) -> Optional[Opportunity]:
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
) -> Optional[Opportunity]:
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


def _mutual_exclusion_basket_candidate(
    market_ids: List[str],
    by_market_id: dict,
    min_net_edge: float,
) -> Optional[Opportunity]:
    snapshots = [by_market_id[market_id] for market_id in market_ids if market_id in by_market_id]
    if len(snapshots) != len(market_ids):
        return None

    return _bundle_candidate(
        kind="mutual_exclusion_basket",
        leg_specs=[(snapshot, "NO", snapshot.no.asks) for snapshot in snapshots],
        payout_per_share=len(snapshots) - 1,
        min_net_edge=min_net_edge,
        ts=snapshots[0].ts,
    )


def _exhaustive_group_candidate(
    market_ids: List[str],
    by_market_id: dict,
    min_net_edge: float,
) -> Optional[Opportunity]:
    market_ids = [str(market_id) for market_id in market_ids if market_id]
    if len(market_ids) < 2 or len(set(market_ids)) != len(market_ids):
        return None

    snapshots = [by_market_id[market_id] for market_id in market_ids if market_id in by_market_id]
    if len(snapshots) != len(market_ids):
        return None

    return _bundle_candidate(
        kind="exhaustive_group_yes_basket",
        leg_specs=[(snapshot, "YES", snapshot.yes.asks) for snapshot in snapshots],
        payout_per_share=1.0,
        min_net_edge=min_net_edge,
        ts=snapshots[0].ts,
    )


def _unique_market_ids(market_ids: List[str]) -> List[str]:
    unique = []
    seen = set()
    for market_id in market_ids:
        if not market_id:
            continue
        normalized = str(market_id)
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique


def _two_leg_candidate(
    kind: str,
    first: BinaryMarketSnapshot,
    first_token: str,
    first_levels: List[Level],
    second: BinaryMarketSnapshot,
    second_token: str,
    second_levels: List[Level],
    min_net_edge: float,
) -> Optional[Opportunity]:
    return _bundle_candidate(
        kind=kind,
        leg_specs=[
            (first, first_token, first_levels),
            (second, second_token, second_levels),
        ],
        payout_per_share=1.0,
        min_net_edge=min_net_edge,
        ts=first.ts or second.ts,
    )


def _bundle_candidate(
    kind: str,
    leg_specs: List[Tuple[BinaryMarketSnapshot, str, List[Level]]],
    payout_per_share: float,
    min_net_edge: float,
    ts: Optional[str],
) -> Optional[Opportunity]:
    quantity = _max_profitable_quantity(leg_specs, payout_per_share, min_net_edge)
    if quantity is None:
        return None

    fills = [take_levels(levels, quantity) for _, _, levels in leg_specs]
    cost_per_share = _bundle_cost_per_share(leg_specs, quantity)
    net_edge = payout_per_share - cost_per_share
    if net_edge <= min_net_edge:
        return None

    return Opportunity(
        kind=kind,
        quantity=quantity,
        cost_per_share=cost_per_share,
        net_edge_per_share=net_edge,
        ts=ts,
        legs=[
            Leg(
                snapshot.venue,
                snapshot.market_id,
                token,
                "buy",
                fill.average_price,
                quantity,
                _token_id_for(snapshot, token),
                fill.worst_price,
                snapshot.fee_rate,
                list(levels),
            )
            for (snapshot, token, levels), fill in zip(leg_specs, fills)
        ],
    )


def _max_profitable_quantity(
    leg_specs: List[Tuple[BinaryMarketSnapshot, str, List[Level]]],
    payout_per_share: float,
    min_net_edge: float,
) -> Optional[float]:
    if not leg_specs:
        return None
    if any(not levels for _, _, levels in leg_specs):
        return None

    target_cost = payout_per_share - min_net_edge
    best_cost = sum(_buy_cost_per_share(snapshot.venue, levels[0].price, snapshot.fee_rate) for snapshot, _, levels in leg_specs)
    if best_cost >= target_cost:
        return None

    max_quantity = min(sum(level.size for level in levels) for _, _, levels in leg_specs)
    if max_quantity <= 0:
        return None
    if _bundle_cost_per_share(leg_specs, max_quantity) < target_cost:
        return max_quantity

    low = 0.0
    high = max_quantity
    for _ in range(50):
        midpoint = (low + high) / 2
        if midpoint <= 0:
            break
        if _bundle_cost_per_share(leg_specs, midpoint) < target_cost:
            low = midpoint
        else:
            high = midpoint

    if low <= 1e-9:
        return None
    return low


def _bundle_cost_per_share(leg_specs: List[Tuple[BinaryMarketSnapshot, str, List[Level]]], quantity: float) -> float:
    total = 0.0
    for snapshot, _, levels in leg_specs:
        total += _fee_adjusted_notional(levels, quantity, snapshot.venue, snapshot.fee_rate) / quantity
    return total


def _fee_adjusted_notional(levels: List[Level], quantity: float, venue: str, fee_rate: float) -> float:
    if insufficient_liquidity(levels, quantity):
        raise ValueError("insufficient liquidity")
    remaining = quantity
    notional = 0.0
    for level in levels:
        if remaining <= 0:
            break
        used = min(remaining, level.size)
        notional += used * _buy_cost_per_share(venue, level.price, fee_rate)
        remaining -= used
    return notional


def _maximal_cliques(adjacency) -> List[List[str]]:
    def bronk(r, p, x, cliques):
        if not p and not x:
            cliques.append(sorted(r))
            return

        union = p | x
        pivot = max(union, key=lambda node: len(adjacency.get(node, set())), default=None)
        pivot_neighbors = adjacency.get(pivot, set()) if pivot is not None else set()
        candidates = set(p) - pivot_neighbors
        for vertex in list(candidates):
            bronk(
                r | {vertex},
                p & adjacency.get(vertex, set()),
                x & adjacency.get(vertex, set()),
                cliques,
            )
            p.remove(vertex)
            x.add(vertex)

    cliques: List[List[str]] = []
    bronk(set(), set(adjacency), set(), cliques)
    return cliques


def _cross_candidate(
    first: VenueBinarySnapshot,
    first_token: str,
    first_levels: List[Level],
    second: VenueBinarySnapshot,
    second_token: str,
    second_levels: List[Level],
    min_net_edge: float,
) -> Optional[Opportunity]:
    return _bundle_candidate(
        kind="cross_venue_same_binary",
        leg_specs=[
            (first, first_token, first_levels),
            (second, second_token, second_levels),
        ],
        payout_per_share=1.0,
        min_net_edge=min_net_edge,
        ts=first.ts or second.ts,
    )


def _token_id_for(snapshot: BinaryMarketSnapshot, token: str):
    if token == "YES":
        return snapshot.yes.token_id
    if token == "NO":
        return snapshot.no.token_id
    return None
