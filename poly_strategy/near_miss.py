from collections import defaultdict
from pathlib import Path
import re
from typing import List, Optional, Tuple

from poly_strategy.backtest import RuleSet, load_rule_set, snapshots_from_ndjson_lines
from poly_strategy.fees import polymarket_taker_fee_per_share
from poly_strategy.models import BinaryMarketSnapshot
from poly_strategy.orderbook import Level
from poly_strategy.recent_lines import read_recent_lines
from poly_strategy.rule_discovery import MarketText, read_market_texts


def near_miss_report(
    snapshots_path: Path,
    rules_path: Optional[Path] = None,
    gamma_path: Optional[Path] = None,
    top_n: int = 10,
    min_net_edge: float = 0.0,
) -> dict:
    if top_n < 0:
        raise ValueError("top_n must be non-negative")

    snapshots = _latest_snapshot_batch(snapshots_path)
    rule_set = load_rule_set(rules_path, gamma_path=gamma_path)
    candidates = near_miss_candidates(snapshots, rule_set, min_net_edge=min_net_edge)
    market_texts = _market_texts_by_id(gamma_path)
    neg_risk_expanded_groups = _annotate_neg_risk_diagnostics(
        candidates,
        snapshots,
        market_texts,
        min_net_edge,
    )
    candidates.sort(key=lambda row: (row["net_edge_per_share"], row["gross_edge_per_share"]), reverse=True)
    by_kind = _summary_by_kind(candidates, min_net_edge)
    actionable = [row for row in candidates if _is_actionable_candidate(row)]
    diagnostic_only = [row for row in candidates if row.get("diagnostic_only")]
    blocked = [row for row in candidates if _candidate_blocked(row)]
    fee_blocked = [
        row
        for row in candidates
        if row["gross_edge_per_share"] > min_net_edge and row["net_edge_per_share"] <= min_net_edge
    ]
    return {
        "type": "near_miss_report",
        "snapshots_path": str(snapshots_path),
        "rules_path": str(rules_path) if rules_path else None,
        "gamma_path": str(gamma_path) if gamma_path else None,
        "latest_snapshot_ts": snapshots[-1].ts if snapshots else None,
        "latest_snapshot_count": len(snapshots),
        "candidate_count": len(candidates),
        "actionable_candidate_count": len(actionable),
        "diagnostic_candidate_count": len(diagnostic_only),
        "blocked_candidate_count": len(blocked),
        "min_net_edge": min_net_edge,
        "top": candidates[:top_n],
        "top_actionable": actionable[:top_n],
        "diagnostic_top": diagnostic_only[:top_n],
        "blocked_top": blocked[:top_n],
        "fee_blocked_top": fee_blocked[:top_n],
        "by_kind": by_kind,
        "neg_risk_expanded_groups": neg_risk_expanded_groups[:top_n],
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

    for rule in rule_set.neg_risk_groups:
        market_ids = _unique_market_ids(rule.market_ids)
        if len(market_ids) < 2:
            continue
        group_snapshots = [by_market_id[market_id] for market_id in market_ids if market_id in by_market_id]
        if len(group_snapshots) != len(market_ids):
            continue
        yes_row = _candidate_row(
            "potential_exhaustive_yes_basket",
            [(snapshot, "YES", snapshot.yes.asks) for snapshot in group_snapshots],
            payout_per_share=1.0,
            min_net_edge=min_net_edge,
        )
        if yes_row is not None:
            yes_row["diagnostic_only"] = True
            yes_row["risk_note"] = "neg-risk YES basket requires exhaustive-group verification before trading"
            candidates.append(yes_row)
        candidates.append(
            _candidate_row(
                "neg_risk_group_no_basket",
                [(snapshot, "NO", snapshot.no.asks) for snapshot in group_snapshots],
                payout_per_share=len(group_snapshots) - 1,
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


def _latest_snapshot_batch(path: Path) -> List[BinaryMarketSnapshot]:
    snapshots = list(snapshots_from_ndjson_lines(read_recent_lines(path)))
    if not snapshots:
        return []
    latest_ts = snapshots[-1].ts
    return [snapshot for snapshot in snapshots if snapshot.ts == latest_ts]


def _market_texts_by_id(path: Optional[Path]) -> dict:
    if not path:
        return {}
    return {market.market_id: market for market in read_market_texts(path)}


def _annotate_neg_risk_diagnostics(
    candidates: List[dict],
    snapshots: List[BinaryMarketSnapshot],
    market_texts: dict,
    min_net_edge: float,
) -> List[dict]:
    if not market_texts:
        return []

    by_market_id = {snapshot.market_id: snapshot for snapshot in snapshots}
    rows = []
    for candidate in candidates:
        if candidate.get("kind") != "potential_exhaustive_yes_basket":
            continue
        row = _neg_risk_group_diagnostic(candidate, by_market_id, market_texts, min_net_edge)
        _apply_neg_risk_diagnostic(candidate, row)
        rows.append(row)
    rows.sort(
        key=lambda row: (
            -float(row.get("source_net_edge_per_share") or 0.0),
            row.get("status") or "",
            ",".join(row.get("source_market_ids") or []),
        )
    )
    return rows


def _neg_risk_group_diagnostic(
    candidate: dict,
    by_market_id: dict,
    market_texts: dict,
    min_net_edge: float,
) -> dict:
    market_ids = [str(leg["market_id"]) for leg in candidate.get("legs", []) if leg.get("market_id")]
    row = {
        "source_market_ids": market_ids,
        "source_net_edge_per_share": candidate.get("net_edge_per_share"),
        "source_gross_edge_per_share": candidate.get("gross_edge_per_share"),
        "status": "unverified",
        "trade_status": "needs_verification",
    }

    missing_metadata = [market_id for market_id in market_ids if market_id not in market_texts]
    if missing_metadata:
        row.update(
            {
                "status": "missing_metadata",
                "trade_status": "blocked",
                "rejection_reason": "missing_gamma_metadata_for_candidate_markets",
                "missing_metadata_market_ids": missing_metadata,
            }
        )
        return row

    source_markets = [market_texts[market_id] for market_id in market_ids]
    group_ids = [market.neg_risk_market_id for market in source_markets]
    if not group_ids or any(not group_id for group_id in group_ids) or len(set(group_ids)) != 1:
        row.update(
            {
                "status": "not_single_neg_risk_group",
                "rejection_reason": "candidate_markets_do_not_share_one_known_neg_risk_group",
            }
        )
        return row

    group_id = group_ids[0]
    known_group_markets = _known_group_markets(market_texts, group_id)
    known_market_ids = [market.market_id for market in known_group_markets]
    source_market_id_set = set(market_ids)
    extra_known_market_ids = [market_id for market_id in known_market_ids if market_id not in source_market_id_set]
    missing_snapshot_market_ids = [market_id for market_id in known_market_ids if market_id not in by_market_id]
    row.update(
        {
            "neg_risk_market_id": group_id,
            "known_market_ids": known_market_ids,
            "known_markets": [_market_row(market) for market in known_group_markets],
            "extra_known_market_ids": extra_known_market_ids,
            "extra_known_markets": [
                _market_row(market)
                for market in known_group_markets
                if market.market_id in set(extra_known_market_ids)
            ],
            "missing_snapshot_market_ids": missing_snapshot_market_ids,
        }
    )

    expanded_candidate = _expanded_neg_risk_candidate(
        known_market_ids,
        by_market_id,
        min_net_edge,
        source_market_ids=market_ids,
        neg_risk_market_id=group_id,
    )
    if expanded_candidate is not None:
        row["expanded_candidate"] = expanded_candidate

    if extra_known_market_ids:
        row.update(
            {
                "status": "incomplete_known_neg_risk_group",
                "trade_status": "rejected",
                "rejection_reason": "candidate_omits_known_markets_from_the_same_neg_risk_group",
            }
        )
    elif group_rejection := _deterministic_group_exhaustiveness_rejection(known_group_markets):
        row.update(
            {
                "status": "known_neg_risk_group_not_exhaustive_by_wording",
                "trade_status": "rejected",
                "rejection_reason": group_rejection,
            }
        )
    else:
        row.update(
            {
                "status": "complete_known_neg_risk_group",
                "trade_status": "needs_verification",
                "rejection_reason": "known_neg_risk_group_still_requires_verifier_or_manual_promotion",
            }
        )
    return row


def _apply_neg_risk_diagnostic(candidate: dict, diagnostic: dict) -> None:
    candidate["trade_status"] = diagnostic["trade_status"]
    candidate["neg_risk_status"] = diagnostic["status"]
    if diagnostic.get("rejection_reason"):
        candidate["rejection_reason"] = diagnostic["rejection_reason"]
    for key in [
        "neg_risk_market_id",
        "known_market_ids",
        "extra_known_market_ids",
        "extra_known_markets",
        "missing_metadata_market_ids",
        "missing_snapshot_market_ids",
    ]:
        if key in diagnostic:
            candidate[key] = diagnostic[key]


def _known_group_markets(market_texts: dict, group_id: str) -> List[MarketText]:
    return sorted(
        [market for market in market_texts.values() if market.neg_risk_market_id == group_id],
        key=_market_sort_key,
    )


def _market_sort_key(market: MarketText):
    threshold = market.group_item_threshold
    try:
        threshold_key = (0, float(threshold))
    except (TypeError, ValueError):
        threshold_key = (1, str(threshold))
    return (threshold_key, market.group_item_title, market.market_id)


def _deterministic_group_exhaustiveness_rejection(markets: List[MarketText]) -> Optional[str]:
    range_rejection = _range_group_exhaustiveness_rejection(markets)
    if range_rejection:
        return range_rejection
    named_candidate_rejection = _named_candidate_group_exhaustiveness_rejection(markets)
    if named_candidate_rejection:
        return named_candidate_rejection
    return None


def deterministic_group_exhaustiveness_rejection(markets: List[MarketText]) -> Optional[str]:
    return _deterministic_group_exhaustiveness_rejection(markets)


def _range_group_exhaustiveness_rejection(markets: List[MarketText]) -> Optional[str]:
    titles = [str(market.group_item_title or market.question or "").strip().lower() for market in markets]
    if len(titles) < 2 or not _looks_like_ordered_numeric_range_group(titles):
        return None
    first_title = titles[0]
    last_title = titles[-1]
    if not _has_lower_tail_wording(first_title):
        return "ordered_range_group_missing_lower_tail"
    if not _has_upper_tail_wording(last_title):
        return "ordered_range_group_missing_upper_tail"
    return None


def _looks_like_ordered_numeric_range_group(titles: List[str]) -> bool:
    numeric_count = sum(1 for title in titles if re.search(r"\d", title))
    if numeric_count < max(2, len(titles) // 2):
        return False
    has_range = any(re.search(r"\d\s*(?:-|to|through|–|—)\s*\d", title) for title in titles)
    has_tail = any(_has_lower_tail_wording(title) or _has_upper_tail_wording(title) for title in titles)
    has_units = any(re.search(r"(?:°|\bf\b|\bc\b|%|points?|goals?|runs?|seats?|votes?)", title) for title in titles)
    return has_range or has_tail or has_units


def _has_lower_tail_wording(title: str) -> bool:
    return bool(
        re.search(
            r"(?:\bor below\b|\bor less\b|\bor fewer\b|\bunder\b|\bbelow\b|\bless than\b|<=|≤)",
            title,
        )
    )


def _has_upper_tail_wording(title: str) -> bool:
    return bool(
        re.search(
            r"(?:\bor above\b|\bor more\b|\bor higher\b|\bover\b|\babove\b|\bgreater than\b|>=|≥|\+)",
            title,
        )
    )


def _named_candidate_group_exhaustiveness_rejection(markets: List[MarketText]) -> Optional[str]:
    if len(markets) < 3:
        return None
    titles = [str(market.group_item_title or "").strip().lower() for market in markets]
    if any(_is_other_or_field_title(title) for title in titles):
        return None
    questions = " ".join(str(market.question or "").lower() for market in markets)
    open_ended_markers = [
        "nobel",
        "peace prize",
        "oscar",
        "academy award",
        "grammy",
        "emmy",
        "person of the year",
        "ballon d'or",
    ]
    if any(marker in questions for marker in open_ended_markers):
        return "named_candidate_group_missing_other_outcome"
    return None


def _is_other_or_field_title(title: str) -> bool:
    return bool(re.search(r"(?:\bother\b|\bfield\b|\banyone else\b|\bsomeone else\b|\bnone of)", title))


def _market_row(market: MarketText) -> dict:
    return {
        "market_id": market.market_id,
        "question": market.question,
        "group_item_title": market.group_item_title,
        "group_item_threshold": market.group_item_threshold,
        "end_date": market.end_date,
    }


def _expanded_neg_risk_candidate(
    known_market_ids: List[str],
    by_market_id: dict,
    min_net_edge: float,
    source_market_ids: List[str],
    neg_risk_market_id: str,
) -> Optional[dict]:
    if any(market_id not in by_market_id for market_id in known_market_ids):
        return None
    row = _candidate_row(
        "known_neg_risk_full_yes_basket",
        [(by_market_id[market_id], "YES", by_market_id[market_id].yes.asks) for market_id in known_market_ids],
        payout_per_share=1.0,
        min_net_edge=min_net_edge,
    )
    if row is None:
        return None
    row["diagnostic_only"] = True
    row["source_potential_market_ids"] = source_market_ids
    row["neg_risk_market_id"] = neg_risk_market_id
    row["risk_note"] = "known neg-risk full group still requires verifier or manual promotion before trading"
    return row


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
                "actionable_candidate_count": 0,
                "diagnostic_candidate_count": 0,
                "blocked_candidate_count": 0,
                "positive_gross_count": 0,
                "positive_net_count": 0,
                "actionable_positive_net_count": 0,
                "fee_blocked_count": 0,
                "best_gross_edge_per_share": None,
                "best_net_edge_per_share": None,
                "best_actionable_net_edge_per_share": None,
            },
        )
        row["candidate_count"] += 1
        if _is_actionable_candidate(candidate):
            row["actionable_candidate_count"] += 1
        if candidate.get("diagnostic_only"):
            row["diagnostic_candidate_count"] += 1
        if _candidate_blocked(candidate):
            row["blocked_candidate_count"] += 1
        if candidate["gross_edge_per_share"] > min_net_edge:
            row["positive_gross_count"] += 1
        if candidate["net_edge_per_share"] > min_net_edge:
            row["positive_net_count"] += 1
            if _is_actionable_candidate(candidate):
                row["actionable_positive_net_count"] += 1
        if candidate["gross_edge_per_share"] > min_net_edge and candidate["net_edge_per_share"] <= min_net_edge:
            row["fee_blocked_count"] += 1
        row["best_gross_edge_per_share"] = _max_optional(
            row["best_gross_edge_per_share"],
            candidate["gross_edge_per_share"],
        )
        row["best_net_edge_per_share"] = _max_optional(row["best_net_edge_per_share"], candidate["net_edge_per_share"])
        if _is_actionable_candidate(candidate):
            row["best_actionable_net_edge_per_share"] = _max_optional(
                row["best_actionable_net_edge_per_share"],
                candidate["net_edge_per_share"],
            )
    return sorted(summary.values(), key=lambda row: (-(row["best_net_edge_per_share"] or -999), row["kind"]))


def _is_actionable_candidate(candidate: dict) -> bool:
    return not candidate.get("diagnostic_only") and not _candidate_blocked(candidate)


def _candidate_blocked(candidate: dict) -> bool:
    return candidate.get("trade_status") in {"rejected", "blocked"} or bool(candidate.get("rejection_reason"))


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
