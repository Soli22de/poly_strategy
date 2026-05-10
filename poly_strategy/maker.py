from collections import defaultdict
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from poly_strategy.backtest import RuleSet, load_rule_set, snapshots_from_ndjson_lines
from poly_strategy.models import BinaryMarketSnapshot, OrderBook
from poly_strategy.recent_lines import read_recent_lines


def maker_scan_report(
    snapshots_path: Path,
    rules_path: Optional[Path] = None,
    gamma_path: Optional[Path] = None,
    tick_size: float = 0.001,
    min_edge: float = 0.0,
    min_roi: Optional[float] = None,
    max_capital: Optional[float] = None,
    max_leg_count: int = 30,
    top_n: int = 25,
    include_yes_no_pairs: bool = False,
    quote_mode: str = "near_ask",
) -> dict:
    if tick_size <= 0:
        raise ValueError("tick_size must be positive")
    if max_leg_count < 2:
        raise ValueError("max_leg_count must be at least 2")
    if top_n < 0:
        raise ValueError("top_n must be non-negative")
    if min_roi is not None and min_roi < 0:
        raise ValueError("min_roi must be non-negative")
    if max_capital is not None and max_capital < 0:
        raise ValueError("max_capital must be non-negative")

    snapshots = latest_snapshot_batch(snapshots_path)
    rule_set = load_rule_set(rules_path, gamma_path=gamma_path)
    candidates = scan_maker_candidates(
        snapshots,
        rule_set,
        tick_size=tick_size,
        min_edge=min_edge,
        min_roi=min_roi,
        max_capital=max_capital,
        max_leg_count=max_leg_count,
        include_yes_no_pairs=include_yes_no_pairs,
        quote_mode=quote_mode,
    )
    return {
        "type": "maker_scan_report",
        "snapshots_path": str(snapshots_path),
        "rules_path": str(rules_path) if rules_path else None,
        "gamma_path": str(gamma_path) if gamma_path else None,
        "latest_snapshot_ts": snapshots[-1].ts if snapshots else None,
        "latest_snapshot_count": len(snapshots),
        "tick_size": tick_size,
        "min_edge": min_edge,
        "min_roi": min_roi,
        "max_capital": max_capital,
        "max_leg_count": max_leg_count,
        "quote_mode": _normalize_quote_mode(quote_mode),
        "candidate_count": len(candidates),
        "by_kind": _summary_by_kind(candidates),
        "top": candidates[:top_n],
    }


def scan_maker_candidates(
    snapshots: List[BinaryMarketSnapshot],
    rule_set: RuleSet,
    tick_size: float = 0.001,
    min_edge: float = 0.0,
    min_roi: Optional[float] = None,
    max_capital: Optional[float] = None,
    max_leg_count: int = 30,
    include_yes_no_pairs: bool = False,
    quote_mode: str = "near_ask",
) -> List[dict]:
    quote_mode = _normalize_quote_mode(quote_mode)
    by_market_id = {snapshot.market_id: snapshot for snapshot in snapshots}
    rows = []

    if include_yes_no_pairs:
        for snapshot in snapshots:
            row = _maker_candidate_row(
                "maker_yes_no_pair",
                [(snapshot, "YES"), (snapshot, "NO")],
                payout_per_share=1.0,
                tick_size=tick_size,
                min_edge=min_edge,
                min_roi=min_roi,
                max_capital=max_capital,
                quote_mode=quote_mode,
            )
            if row:
                rows.append(row)

    for rule in rule_set.neg_risk_groups:
        market_ids = _unique_market_ids(rule.market_ids)
        if len(market_ids) < 2 or len(market_ids) > max_leg_count:
            continue
        group_snapshots = [by_market_id.get(market_id) for market_id in market_ids]
        if any(snapshot is None for snapshot in group_snapshots):
            continue
        row = _maker_candidate_row(
            "maker_neg_risk_no_basket",
            [(snapshot, "NO") for snapshot in group_snapshots],
            payout_per_share=len(group_snapshots) - 1,
            tick_size=tick_size,
            min_edge=min_edge,
            min_roi=min_roi,
            max_capital=max_capital,
            quote_mode=quote_mode,
            extra={"neg_risk_market_id": rule.neg_risk_market_id},
        )
        if row:
            rows.append(row)

    for clique in _mutual_exclusion_cliques(rule_set, by_market_id, max_leg_count=max_leg_count):
        group_snapshots = [by_market_id[market_id] for market_id in clique]
        row = _maker_candidate_row(
            "maker_mutual_exclusion_no_basket",
            [(snapshot, "NO") for snapshot in group_snapshots],
            payout_per_share=len(group_snapshots) - 1,
            tick_size=tick_size,
            min_edge=min_edge,
            min_roi=min_roi,
            max_capital=max_capital,
            quote_mode=quote_mode,
        )
        if row:
            rows.append(row)

    for rule in rule_set.exhaustive_groups:
        market_ids = _unique_market_ids(rule.market_ids)
        if len(market_ids) < 2 or len(market_ids) > max_leg_count:
            continue
        group_snapshots = [by_market_id.get(market_id) for market_id in market_ids]
        if any(snapshot is None for snapshot in group_snapshots):
            continue
        row = _maker_candidate_row(
            "maker_exhaustive_yes_basket",
            [(snapshot, "YES") for snapshot in group_snapshots],
            payout_per_share=1.0,
            tick_size=tick_size,
            min_edge=min_edge,
            min_roi=min_roi,
            max_capital=max_capital,
            quote_mode=quote_mode,
        )
        if row:
            rows.append(row)

    rows = _dedupe_rows(rows)
    rows.sort(key=_candidate_sort_key)
    return rows


def latest_snapshot_batch(path: Path) -> List[BinaryMarketSnapshot]:
    snapshots = list(snapshots_from_ndjson_lines(read_recent_lines(path)))
    if not snapshots:
        return []
    latest_ts = snapshots[-1].ts
    return [snapshot for snapshot in snapshots if snapshot.ts == latest_ts]


def _maker_candidate_row(
    kind: str,
    leg_specs: List[Tuple[BinaryMarketSnapshot, str]],
    payout_per_share: float,
    tick_size: float,
    min_edge: float,
    min_roi: Optional[float],
    max_capital: Optional[float],
    quote_mode: str,
    extra: Optional[dict] = None,
) -> Optional[dict]:
    if len(leg_specs) < 2:
        return None
    passive_legs = []
    cost = 0.0
    for snapshot, token in leg_specs:
        leg = _passive_buy_leg(snapshot, token, tick_size, quote_mode)
        if leg is None:
            return None
        passive_legs.append(leg)
        cost += leg["limit_price"]
    if cost <= 0:
        return None
    edge = payout_per_share - cost
    if edge <= min_edge:
        return None
    roi = edge / cost
    if min_roi is not None and roi < min_roi:
        return None
    suggested_quantity = None
    expected_edge_at_cap = None
    capital_used_at_cap = None
    if max_capital is not None and max_capital > 0:
        suggested_quantity = max_capital / cost
        capital_used_at_cap = suggested_quantity * cost
        expected_edge_at_cap = suggested_quantity * edge

    row = {
        "type": "maker_candidate",
        "kind": kind,
        "ts": leg_specs[0][0].ts,
        "market_ids": [snapshot.market_id for snapshot, _ in leg_specs],
        "leg_count": len(leg_specs),
        "payout_per_share": payout_per_share,
        "passive_cost_per_share": cost,
        "maker_edge_per_share": edge,
        "maker_roi": roi,
        "suggested_quantity": suggested_quantity,
        "capital_used_at_cap": capital_used_at_cap,
        "expected_edge_at_cap": expected_edge_at_cap,
        "min_spread": min(leg["spread"] for leg in passive_legs),
        "max_spread": max(leg["spread"] for leg in passive_legs),
        "avg_spread": sum(leg["spread"] for leg in passive_legs) / len(passive_legs),
        "quote_mode": quote_mode,
        "risk_flags": [
            "requires_all_legs_fill",
            "non_atomic_execution",
            "partial_fill_directional_exposure",
            "maker_queue_and_adverse_selection_risk",
        ],
        "legs": passive_legs,
    }
    if extra:
        row.update(extra)
    return row


def _passive_buy_leg(snapshot: BinaryMarketSnapshot, token: str, tick_size: float, quote_mode: str) -> Optional[dict]:
    book = _token_book(snapshot, token)
    if not book.asks:
        return None
    best_ask = book.asks[0].price
    best_bid = book.bids[0].price if book.bids else 0.0
    if best_ask <= tick_size:
        return None

    if quote_mode == "near_ask":
        limit_price = best_ask - tick_size
    elif quote_mode == "improve_bid":
        limit_price = min(best_bid + tick_size, best_ask - tick_size)
    else:
        raise ValueError(f"unsupported quote_mode: {quote_mode}")
    limit_price = _floor_to_tick(limit_price, tick_size)
    if limit_price <= 0 or limit_price >= best_ask:
        return None

    return {
        "venue": snapshot.venue,
        "market_id": snapshot.market_id,
        "token": token,
        "token_id": book.token_id,
        "side": "buy",
        "limit_price": limit_price,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "spread": best_ask - best_bid,
        "improvement_over_best_bid": max(0.0, limit_price - best_bid),
        "distance_to_best_ask": best_ask - limit_price,
        "fee_rate_assumption": 0.0,
        "quote_mode": quote_mode,
    }


def _normalize_quote_mode(value: str) -> str:
    normalized = (value or "near_ask").strip().lower().replace("-", "_")
    if normalized in {"near_ask", "ask_minus_tick", "aggressive"}:
        return "near_ask"
    if normalized in {"improve_bid", "bid_plus_tick", "passive"}:
        return "improve_bid"
    raise ValueError("quote_mode must be near_ask or improve_bid")


def _token_book(snapshot: BinaryMarketSnapshot, token: str) -> OrderBook:
    if token == "YES":
        return snapshot.yes
    if token == "NO":
        return snapshot.no
    raise ValueError(f"unsupported token: {token}")


def _floor_to_tick(price: float, tick_size: float) -> float:
    ticks = int((price + 1e-12) / tick_size)
    return round(ticks * tick_size, 6)


def _mutual_exclusion_cliques(rule_set: RuleSet, by_market_id: dict, max_leg_count: int) -> List[List[str]]:
    adjacency = defaultdict(set)
    for rule in rule_set.mutual_exclusions:
        if rule.first_market_id in by_market_id and rule.second_market_id in by_market_id:
            adjacency[rule.first_market_id].add(rule.second_market_id)
            adjacency[rule.second_market_id].add(rule.first_market_id)
    return [clique for clique in _maximal_cliques(adjacency) if 3 <= len(clique) <= max_leg_count]


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

    cliques = []
    bronk(set(), set(adjacency), set(), cliques)
    return cliques


def _unique_market_ids(market_ids: Iterable[str]) -> List[str]:
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


def _dedupe_rows(rows: List[dict]) -> List[dict]:
    deduped = {}
    for row in rows:
        key = (
            row["kind"],
            tuple((leg["venue"], leg["market_id"], leg["token"], leg["side"]) for leg in row["legs"]),
        )
        previous = deduped.get(key)
        if previous is None or row["maker_edge_per_share"] > previous["maker_edge_per_share"]:
            deduped[key] = row
    return list(deduped.values())


def _candidate_sort_key(row: dict) -> tuple:
    return (
        -float(row.get("expected_edge_at_cap") or 0.0),
        -float(row.get("maker_roi") or 0.0),
        -float(row.get("maker_edge_per_share") or 0.0),
        int(row.get("leg_count") or 0),
        ",".join(row.get("market_ids") or []),
    )


def _summary_by_kind(rows: List[dict]) -> list:
    summary = {}
    for row in rows:
        item = summary.setdefault(
            row["kind"],
            {
                "kind": row["kind"],
                "candidate_count": 0,
                "max_maker_edge_per_share": 0.0,
                "max_maker_roi": 0.0,
                "max_expected_edge_at_cap": 0.0,
            },
        )
        item["candidate_count"] += 1
        item["max_maker_edge_per_share"] = max(item["max_maker_edge_per_share"], row["maker_edge_per_share"])
        item["max_maker_roi"] = max(item["max_maker_roi"], row["maker_roi"])
        item["max_expected_edge_at_cap"] = max(item["max_expected_edge_at_cap"], row.get("expected_edge_at_cap") or 0.0)
    return sorted(summary.values(), key=lambda row: (-row["max_expected_edge_at_cap"], row["kind"]))
