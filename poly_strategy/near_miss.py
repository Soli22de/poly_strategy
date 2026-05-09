from collections import defaultdict
from pathlib import Path
from typing import List, Optional, Tuple

from poly_strategy.backtest import RuleSet, load_rule_set, snapshots_from_ndjson_lines
from poly_strategy.fees import polymarket_taker_fee_per_share
from poly_strategy.models import BinaryMarketSnapshot
from poly_strategy.orderbook import Level


def near_miss_report(
    snapshots_path: Path,
    rules_path: Optional[Path] = None,
    top_n: int = 10,
    min_net_edge: float = 0.0,
) -> dict:
    if top_n < 0:
        raise ValueError("top_n must be non-negative")

    snapshots = _latest_snapshot_batch(snapshots_path)
    rule_set = load_rule_set(rules_path) if rules_path else RuleSet()
    candidates = near_miss_candidates(snapshots, rule_set, min_net_edge=min_net_edge)
    candidates.sort(key=lambda row: (row["net_edge_per_share"], row["gross_edge_per_share"]), reverse=True)
    by_kind = _summary_by_kind(candidates, min_net_edge)
    fee_blocked = [
        row
        for row in candidates
        if row["gross_edge_per_share"] > min_net_edge and row["net_edge_per_share"] <= min_net_edge
    ]
    return {
        "type": "near_miss_report",
        "snapshots_path": str(snapshots_path),
        "rules_path": str(rules_path) if rules_path else None,
        "latest_snapshot_ts": snapshots[-1].ts if snapshots else None,
        "latest_snapshot_count": len(snapshots),
        "candidate_count": len(candidates),
        "min_net_edge": min_net_edge,
        "top": candidates[:top_n],
        "fee_blocked_top": fee_blocked[:top_n],
        "by_kind": by_kind,
    }


def near_miss_candidates(
    snapshots: List[BinaryMarketSnapshot],
    rule_set: RuleSet,
    min_net_edge: float = 0.0,
) -> List[dict]:
    by_market_id = {snapshot.market_id: snapshot for snapshot in snapshots}
    candidates = []

    for snapshot in snapshots:
        candidates.append(
            _candidate_row(
                "yes_no_bundle",
                [(snapshot, "YES", snapshot.yes.asks), (snapshot, "NO", snapshot.no.asks)],
                payout_per_share=1.0,
                min_net_edge=min_net_edge,
            )
        )

    for rule in rule_set.implications:
        antecedent = by_market_id.get(rule.antecedent_market_id)
        consequent = by_market_id.get(rule.consequent_market_id)
        if antecedent and consequent:
            candidates.append(
                _candidate_row(
                    "implication",
                    [(consequent, "YES", consequent.yes.asks), (antecedent, "NO", antecedent.no.asks)],
                    payout_per_share=1.0,
                    min_net_edge=min_net_edge,
                )
            )

    mutual_exclusion_adjacency = defaultdict(set)
    for rule in rule_set.mutual_exclusions:
        first = by_market_id.get(rule.first_market_id)
        second = by_market_id.get(rule.second_market_id)
        if not first or not second:
            continue
        candidates.append(
            _candidate_row(
                "mutually_exclusive",
                [(first, "NO", first.no.asks), (second, "NO", second.no.asks)],
                payout_per_share=1.0,
                min_net_edge=min_net_edge,
            )
        )
        mutual_exclusion_adjacency[first.market_id].add(second.market_id)
        mutual_exclusion_adjacency[second.market_id].add(first.market_id)

    for clique in _maximal_cliques(mutual_exclusion_adjacency):
        if len(clique) < 3:
            continue
        clique_snapshots = [by_market_id[market_id] for market_id in clique]
        candidates.append(
            _candidate_row(
                "mutual_exclusion_basket",
                [(snapshot, "NO", snapshot.no.asks) for snapshot in clique_snapshots],
                payout_per_share=len(clique_snapshots) - 1,
                min_net_edge=min_net_edge,
            )
        )
        row = _candidate_row(
            "potential_exhaustive_yes_basket",
            [(snapshot, "YES", snapshot.yes.asks) for snapshot in clique_snapshots],
            payout_per_share=1.0,
            min_net_edge=min_net_edge,
        )
        if row is not None:
            row["diagnostic_only"] = True
            row["risk_note"] = "requires the clique to be a complete collectively exhaustive outcome set"
            candidates.append(row)

    for rule in rule_set.equivalences:
        first = by_market_id.get(rule.first_market_id)
        second = by_market_id.get(rule.second_market_id)
        if first and second:
            candidates.append(
                _candidate_row(
                    "equivalent",
                    [(first, "YES", first.yes.asks), (second, "NO", second.no.asks)],
                    payout_per_share=1.0,
                    min_net_edge=min_net_edge,
                )
            )
            candidates.append(
                _candidate_row(
                    "equivalent",
                    [(second, "YES", second.yes.asks), (first, "NO", first.no.asks)],
                    payout_per_share=1.0,
                    min_net_edge=min_net_edge,
                )
            )

    for rule in rule_set.collectively_exhaustive:
        first = by_market_id.get(rule.first_market_id)
        second = by_market_id.get(rule.second_market_id)
        if first and second:
            candidates.append(
                _candidate_row(
                    "collectively_exhaustive",
                    [(first, "YES", first.yes.asks), (second, "YES", second.yes.asks)],
                    payout_per_share=1.0,
                    min_net_edge=min_net_edge,
                )
            )

    for rule in rule_set.exhaustive_groups:
        if len(rule.market_ids) < 2 or len(set(rule.market_ids)) != len(rule.market_ids):
            continue
        group_snapshots = [by_market_id[market_id] for market_id in rule.market_ids if market_id in by_market_id]
        if len(group_snapshots) != len(rule.market_ids):
            continue
        candidates.append(
            _candidate_row(
                "exhaustive_group_yes_basket",
                [(snapshot, "YES", snapshot.yes.asks) for snapshot in group_snapshots],
                payout_per_share=1.0,
                min_net_edge=min_net_edge,
            )
        )

    for rule in rule_set.complements:
        first = by_market_id.get(rule.first_market_id)
        second = by_market_id.get(rule.second_market_id)
        if first and second:
            candidates.append(
                _candidate_row(
                    "complement_yes_bundle",
                    [(first, "YES", first.yes.asks), (second, "YES", second.yes.asks)],
                    payout_per_share=1.0,
                    min_net_edge=min_net_edge,
                )
            )
            candidates.append(
                _candidate_row(
                    "complement_no_bundle",
                    [(first, "NO", first.no.asks), (second, "NO", second.no.asks)],
                    payout_per_share=1.0,
                    min_net_edge=min_net_edge,
                )
            )

    return [candidate for candidate in candidates if candidate is not None]


def _latest_snapshot_batch(path: Path) -> List[BinaryMarketSnapshot]:
    snapshots = list(snapshots_from_ndjson_lines(path.read_text().splitlines()))
    if not snapshots:
        return []
    latest_ts = snapshots[-1].ts
    return [snapshot for snapshot in snapshots if snapshot.ts == latest_ts]


def _candidate_row(
    kind: str,
    leg_specs: List[Tuple[BinaryMarketSnapshot, str, List[Level]]],
    payout_per_share: float,
    min_net_edge: float,
) -> Optional[dict]:
    if not leg_specs or any(not levels for _, _, levels in leg_specs):
        return None

    gross_cost = 0.0
    net_cost = 0.0
    top_quantity = min(levels[0].size for _, _, levels in leg_specs)
    legs = []
    for snapshot, token, levels in leg_specs:
        price = levels[0].price
        fee = polymarket_taker_fee_per_share(price, snapshot.fee_rate)
        fee_adjusted_price = price + fee
        gross_cost += price
        net_cost += fee_adjusted_price
        legs.append(
            {
                "market_id": snapshot.market_id,
                "token": token,
                "top_ask": price,
                "fee_adjusted_top_ask": fee_adjusted_price,
                "fee_per_share": fee,
                "fee_rate": snapshot.fee_rate,
                "top_size": levels[0].size,
            }
        )

    gross_edge = payout_per_share - gross_cost
    net_edge = payout_per_share - net_cost
    return {
        "kind": kind,
        "payout_per_share": payout_per_share,
        "gross_cost_per_share": gross_cost,
        "fee_adjusted_cost_per_share": net_cost,
        "gross_edge_per_share": gross_edge,
        "net_edge_per_share": net_edge,
        "fee_drag_per_share": gross_edge - net_edge,
        "distance_to_min_net_edge": max(0.0, min_net_edge - net_edge),
        "top_quantity": top_quantity,
        "gross_total_edge_at_top": gross_edge * top_quantity,
        "net_total_edge_at_top": net_edge * top_quantity,
        "legs": legs,
    }


def _summary_by_kind(candidates: List[dict], min_net_edge: float) -> list:
    summary = {}
    for candidate in candidates:
        row = summary.setdefault(
            candidate["kind"],
            {
                "kind": candidate["kind"],
                "candidate_count": 0,
                "positive_gross_count": 0,
                "positive_net_count": 0,
                "fee_blocked_count": 0,
                "best_gross_edge_per_share": None,
                "best_net_edge_per_share": None,
            },
        )
        row["candidate_count"] += 1
        if candidate["gross_edge_per_share"] > min_net_edge:
            row["positive_gross_count"] += 1
        if candidate["net_edge_per_share"] > min_net_edge:
            row["positive_net_count"] += 1
        if candidate["gross_edge_per_share"] > min_net_edge and candidate["net_edge_per_share"] <= min_net_edge:
            row["fee_blocked_count"] += 1
        row["best_gross_edge_per_share"] = _max_optional(
            row["best_gross_edge_per_share"],
            candidate["gross_edge_per_share"],
        )
        row["best_net_edge_per_share"] = _max_optional(row["best_net_edge_per_share"], candidate["net_edge_per_share"])
    return sorted(summary.values(), key=lambda row: (-row["best_net_edge_per_share"], row["kind"]))


def _max_optional(first: Optional[float], second: float) -> float:
    if first is None:
        return second
    return max(first, second)


def _maximal_cliques(adjacency) -> List[List[str]]:
    def bronk(r, p, x, cliques):
        if not p and not x:
            cliques.append(sorted(r))
            return

        union = p | x
        pivot = max(union, key=lambda node: len(adjacency.get(node, set())), default=None)
        candidates = set(p) - adjacency.get(pivot, set())
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
