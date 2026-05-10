from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

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
    quote_offset_ticks: int = 1,
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
    quote_offset_ticks = _normalize_quote_offset_ticks(quote_offset_ticks)

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
        quote_offset_ticks=quote_offset_ticks,
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
        "quote_offset_ticks": quote_offset_ticks,
        "candidate_count": len(candidates),
        "by_kind": _summary_by_kind(candidates),
        "top": candidates[:top_n],
    }


def maker_fill_sim_report(
    snapshots_path: Path,
    rules_path: Optional[Path] = None,
    gamma_path: Optional[Path] = None,
    tick_size: float = 0.001,
    min_edge: float = 0.0,
    min_roi: Optional[float] = None,
    max_capital: Optional[float] = None,
    max_leg_count: int = 30,
    quote_mode: str = "near_ask",
    horizon_seconds: float = 300.0,
    max_candidates_per_batch: int = 25,
    top_n: int = 25,
    include_yes_no_pairs: bool = False,
    quote_offset_ticks: int = 1,
) -> dict:
    if tick_size <= 0:
        raise ValueError("tick_size must be positive")
    if max_leg_count < 2:
        raise ValueError("max_leg_count must be at least 2")
    if min_roi is not None and min_roi < 0:
        raise ValueError("min_roi must be non-negative")
    if max_capital is not None and max_capital < 0:
        raise ValueError("max_capital must be non-negative")
    if horizon_seconds < 0:
        raise ValueError("horizon_seconds must be non-negative")
    if max_candidates_per_batch < 1:
        raise ValueError("max_candidates_per_batch must be at least 1")
    if top_n < 0:
        raise ValueError("top_n must be non-negative")
    quote_offset_ticks = _normalize_quote_offset_ticks(quote_offset_ticks)

    rule_set = load_rule_set(rules_path, gamma_path=gamma_path)
    batches = list(snapshot_batches_from_path(snapshots_path))
    results = simulate_maker_fills(
        batches,
        rule_set,
        tick_size=tick_size,
        min_edge=min_edge,
        min_roi=min_roi,
        max_capital=max_capital,
        max_leg_count=max_leg_count,
        quote_mode=quote_mode,
        quote_offset_ticks=quote_offset_ticks,
        horizon_seconds=horizon_seconds,
        max_candidates_per_batch=max_candidates_per_batch,
        include_yes_no_pairs=include_yes_no_pairs,
    )

    completed = [row for row in results if row["completed"]]
    partial = [row for row in results if row["partial_fill"] and not row["completed"]]
    no_fill = [row for row in results if row["filled_leg_count"] == 0]
    return {
        "type": "maker_fill_sim_report",
        "snapshots_path": str(snapshots_path),
        "rules_path": str(rules_path) if rules_path else None,
        "gamma_path": str(gamma_path) if gamma_path else None,
        "batch_count": len(batches),
        "candidate_observation_count": len(results),
        "completed_count": len(completed),
        "partial_count": len(partial),
        "no_fill_count": len(no_fill),
        "completion_rate": len(completed) / len(results) if results else 0.0,
        "partial_rate": len(partial) / len(results) if results else 0.0,
        "completed_expected_edge_at_cap": sum(float(row.get("expected_edge_at_cap") or 0.0) for row in completed),
        "max_completed_expected_edge_at_cap": max((float(row.get("expected_edge_at_cap") or 0.0) for row in completed), default=0.0),
        "quote_mode": _normalize_quote_mode(quote_mode),
        "quote_offset_ticks": quote_offset_ticks,
        "by_kind": _fill_summary_by_kind(results),
        "top_completed": sorted(completed, key=_fill_result_sort_key)[:top_n],
        "top_partial": sorted(partial, key=_fill_result_sort_key)[:top_n],
        "top_unfilled": sorted(no_fill, key=_fill_result_sort_key)[:top_n],
    }


def maker_adaptive_quote_report(
    snapshots_path: Path,
    rules_path: Optional[Path] = None,
    gamma_path: Optional[Path] = None,
    tick_size: float = 0.001,
    min_edge: float = 0.0,
    min_roi: Optional[float] = None,
    max_capital: Optional[float] = None,
    max_leg_count: int = 30,
    quote_offset_ticks_options: Optional[Sequence[int]] = None,
    include_improve_bid: bool = True,
    horizon_seconds: float = 300.0,
    max_candidates_per_batch: int = 25,
    top_n: int = 25,
    include_yes_no_pairs: bool = False,
    partial_loss_rate: float = 1.0,
    min_observations: int = 5,
) -> dict:
    if tick_size <= 0:
        raise ValueError("tick_size must be positive")
    if max_leg_count < 2:
        raise ValueError("max_leg_count must be at least 2")
    if min_roi is not None and min_roi < 0:
        raise ValueError("min_roi must be non-negative")
    if max_capital is not None and max_capital < 0:
        raise ValueError("max_capital must be non-negative")
    if horizon_seconds < 0:
        raise ValueError("horizon_seconds must be non-negative")
    if max_candidates_per_batch < 1:
        raise ValueError("max_candidates_per_batch must be at least 1")
    if top_n < 0:
        raise ValueError("top_n must be non-negative")
    if partial_loss_rate < 0:
        raise ValueError("partial_loss_rate must be non-negative")
    if min_observations < 0:
        raise ValueError("min_observations must be non-negative")

    offsets = _normalize_quote_offset_ticks_options(quote_offset_ticks_options)
    configs = [{"quote_mode": "near_ask", "quote_offset_ticks": offset} for offset in offsets]
    if include_improve_bid:
        configs.append({"quote_mode": "improve_bid", "quote_offset_ticks": 1})

    rule_set = load_rule_set(rules_path, gamma_path=gamma_path)
    batches = list(snapshot_batches_from_path(snapshots_path))
    rows = []
    for config in configs:
        results = simulate_maker_fills(
            batches,
            rule_set,
            tick_size=tick_size,
            min_edge=min_edge,
            min_roi=min_roi,
            max_capital=max_capital,
            max_leg_count=max_leg_count,
            quote_mode=config["quote_mode"],
            quote_offset_ticks=config["quote_offset_ticks"],
            horizon_seconds=horizon_seconds,
            max_candidates_per_batch=max_candidates_per_batch,
            include_yes_no_pairs=include_yes_no_pairs,
        )
        rows.append(_adaptive_config_summary(config, results, partial_loss_rate))

    ranked = sorted(rows, key=_adaptive_config_sort_key)
    recommended = next(
        (
            row
            for row in ranked
            if row["candidate_observation_count"] >= min_observations
            and row["risk_adjusted_total_ev_at_cap"] > 0
            and row["completed_count"] > 0
        ),
        None,
    )
    return {
        "type": "maker_adaptive_quote_report",
        "snapshots_path": str(snapshots_path),
        "rules_path": str(rules_path) if rules_path else None,
        "gamma_path": str(gamma_path) if gamma_path else None,
        "batch_count": len(batches),
        "tick_size": tick_size,
        "min_edge": min_edge,
        "min_roi": min_roi,
        "max_capital": max_capital,
        "max_leg_count": max_leg_count,
        "horizon_seconds": horizon_seconds,
        "max_candidates_per_batch": max_candidates_per_batch,
        "partial_loss_rate": partial_loss_rate,
        "min_observations": min_observations,
        "status": "positive_ev_config_found" if recommended else "no_positive_ev_config",
        "recommended_config": recommended,
        "ranked_configs": ranked[:top_n],
    }


def simulate_maker_fills(
    batches: List[List[BinaryMarketSnapshot]],
    rule_set: RuleSet,
    tick_size: float = 0.001,
    min_edge: float = 0.0,
    min_roi: Optional[float] = None,
    max_capital: Optional[float] = None,
    max_leg_count: int = 30,
    quote_mode: str = "near_ask",
    quote_offset_ticks: int = 1,
    horizon_seconds: float = 300.0,
    max_candidates_per_batch: int = 25,
    include_yes_no_pairs: bool = False,
) -> List[dict]:
    results = []
    for index, batch in enumerate(batches[:-1]):
        candidates = scan_maker_candidates(
            batch,
            rule_set,
            tick_size=tick_size,
            min_edge=min_edge,
            min_roi=min_roi,
            max_capital=max_capital,
            max_leg_count=max_leg_count,
            include_yes_no_pairs=include_yes_no_pairs,
            quote_mode=quote_mode,
            quote_offset_ticks=quote_offset_ticks,
        )
        candidates = _dedupe_sim_candidates(candidates)[:max_candidates_per_batch]
        if not candidates:
            continue
        future_batches = _future_batches_within_horizon(batches, index, horizon_seconds)
        for candidate in candidates:
            results.append(_simulate_candidate_fills(candidate, future_batches))
    return results


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
    quote_offset_ticks: int = 1,
) -> List[dict]:
    if tick_size <= 0:
        raise ValueError("tick_size must be positive")
    if max_leg_count < 2:
        raise ValueError("max_leg_count must be at least 2")
    if min_roi is not None and min_roi < 0:
        raise ValueError("min_roi must be non-negative")
    if max_capital is not None and max_capital < 0:
        raise ValueError("max_capital must be non-negative")
    quote_mode = _normalize_quote_mode(quote_mode)
    quote_offset_ticks = _normalize_quote_offset_ticks(quote_offset_ticks)
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
                quote_offset_ticks=quote_offset_ticks,
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
            quote_offset_ticks=quote_offset_ticks,
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
            quote_offset_ticks=quote_offset_ticks,
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
            quote_offset_ticks=quote_offset_ticks,
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


def snapshot_batches_from_path(path: Path) -> Iterable[List[BinaryMarketSnapshot]]:
    batch = []
    current_ts = object()
    with path.open() as handle:
        for snapshot in snapshots_from_ndjson_lines(handle):
            if snapshot.ts != current_ts and batch:
                yield batch
                batch = []
            current_ts = snapshot.ts
            batch.append(snapshot)
    if batch:
        yield batch


def _maker_candidate_row(
    kind: str,
    leg_specs: List[Tuple[BinaryMarketSnapshot, str]],
    payout_per_share: float,
    tick_size: float,
    min_edge: float,
    min_roi: Optional[float],
    max_capital: Optional[float],
    quote_mode: str,
    quote_offset_ticks: int,
    extra: Optional[dict] = None,
) -> Optional[dict]:
    if len(leg_specs) < 2:
        return None
    passive_legs = []
    cost = 0.0
    for snapshot, token in leg_specs:
        leg = _passive_buy_leg(snapshot, token, tick_size, quote_mode, quote_offset_ticks)
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
        "quote_offset_ticks": quote_offset_ticks,
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


def _passive_buy_leg(
    snapshot: BinaryMarketSnapshot,
    token: str,
    tick_size: float,
    quote_mode: str,
    quote_offset_ticks: int,
) -> Optional[dict]:
    book = _token_book(snapshot, token)
    if not book.asks:
        return None
    best_ask = book.asks[0].price
    best_bid = book.bids[0].price if book.bids else 0.0
    if best_ask <= tick_size:
        return None

    if quote_mode == "near_ask":
        limit_price = best_ask - tick_size * quote_offset_ticks
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
        "quote_offset_ticks": quote_offset_ticks,
    }


def _normalize_quote_mode(value: str) -> str:
    normalized = (value or "near_ask").strip().lower().replace("-", "_")
    if normalized in {"near_ask", "ask_minus_tick", "aggressive"}:
        return "near_ask"
    if normalized in {"improve_bid", "bid_plus_tick", "passive"}:
        return "improve_bid"
    raise ValueError("quote_mode must be near_ask or improve_bid")


def _normalize_quote_offset_ticks(value: int) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("quote_offset_ticks must be a positive integer") from exc
    if normalized < 1:
        raise ValueError("quote_offset_ticks must be a positive integer")
    return normalized


def _normalize_quote_offset_ticks_options(values: Optional[Sequence[int]]) -> List[int]:
    raw_values = values if values else [1, 2, 3, 5, 10]
    offsets = sorted({_normalize_quote_offset_ticks(value) for value in raw_values})
    if not offsets:
        raise ValueError("quote_offset_ticks_options must include at least one value")
    return offsets


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


def _adaptive_config_summary(config: dict, results: List[dict], partial_loss_rate: float) -> dict:
    completed = [row for row in results if row["completed"]]
    partial = [row for row in results if row["partial_fill"] and not row["completed"]]
    no_fill = [row for row in results if row["filled_leg_count"] == 0]
    completed_edge_at_cap = sum(float(row.get("expected_edge_at_cap") or 0.0) for row in completed)
    partial_filled_capital_at_cap = sum(float(row.get("filled_capital_at_cap") or 0.0) for row in partial)
    risk_adjusted_total = completed_edge_at_cap - partial_loss_rate * partial_filled_capital_at_cap
    observation_count = len(results)
    return {
        "quote_mode": config["quote_mode"],
        "quote_offset_ticks": config["quote_offset_ticks"],
        "candidate_observation_count": observation_count,
        "completed_count": len(completed),
        "partial_count": len(partial),
        "no_fill_count": len(no_fill),
        "completion_rate": len(completed) / observation_count if observation_count else 0.0,
        "partial_rate": len(partial) / observation_count if observation_count else 0.0,
        "no_fill_rate": len(no_fill) / observation_count if observation_count else 0.0,
        "completed_expected_edge_at_cap": completed_edge_at_cap,
        "partial_filled_capital_at_cap": partial_filled_capital_at_cap,
        "partial_loss_rate": partial_loss_rate,
        "risk_adjusted_total_ev_at_cap": risk_adjusted_total,
        "risk_adjusted_mean_ev_at_cap": risk_adjusted_total / observation_count if observation_count else 0.0,
        "max_completed_expected_edge_at_cap": max(
            (float(row.get("expected_edge_at_cap") or 0.0) for row in completed),
            default=0.0,
        ),
        "max_partial_filled_capital_at_cap": max(
            (float(row.get("filled_capital_at_cap") or 0.0) for row in partial),
            default=0.0,
        ),
        "by_kind": _fill_summary_by_kind(results),
    }


def _adaptive_config_sort_key(row: dict) -> tuple:
    return (
        -float(row.get("risk_adjusted_total_ev_at_cap") or 0.0),
        -float(row.get("risk_adjusted_mean_ev_at_cap") or 0.0),
        -float(row.get("completion_rate") or 0.0),
        float(row.get("partial_rate") or 0.0),
        str(row.get("quote_mode") or ""),
        int(row.get("quote_offset_ticks") or 0),
    )


def _future_batches_within_horizon(
    batches: List[List[BinaryMarketSnapshot]],
    index: int,
    horizon_seconds: float,
) -> List[List[BinaryMarketSnapshot]]:
    future = []
    start_ts = _batch_ts(batches[index])
    start_dt = _parse_ts(start_ts)
    for batch in batches[index + 1 :]:
        if horizon_seconds > 0 and start_dt is not None:
            batch_dt = _parse_ts(_batch_ts(batch))
            if batch_dt is not None and (batch_dt - start_dt).total_seconds() > horizon_seconds:
                break
        future.append(batch)
    return future


def _simulate_candidate_fills(candidate: dict, future_batches: List[List[BinaryMarketSnapshot]]) -> dict:
    open_legs = {index: leg for index, leg in enumerate(candidate.get("legs", []))}
    fills = []
    for batch in future_batches:
        by_market_id = {snapshot.market_id: snapshot for snapshot in batch}
        for index, leg in list(open_legs.items()):
            snapshot = by_market_id.get(str(leg.get("market_id") or ""))
            if snapshot is None:
                continue
            observation = _leg_fill_observation(snapshot, leg)
            if observation is None:
                continue
            fills.append({"leg_index": index, **observation})
            del open_legs[index]
        if not open_legs:
            break

    leg_count = len(candidate.get("legs", []))
    filled_count = leg_count - len(open_legs)
    filled_cost_per_share = sum(float(fill.get("limit_price") or 0.0) for fill in fills)
    passive_cost_per_share = float(candidate.get("passive_cost_per_share") or 0.0)
    unfilled_cost_per_share = max(0.0, passive_cost_per_share - filled_cost_per_share)
    suggested_quantity = candidate.get("suggested_quantity")
    filled_capital_at_cap = None
    if suggested_quantity is not None:
        filled_capital_at_cap = float(suggested_quantity or 0.0) * filled_cost_per_share
    row = {
        "candidate_key": _candidate_identity(candidate),
        "kind": candidate.get("kind"),
        "start_ts": candidate.get("ts"),
        "completion_ts": fills[-1]["fill_ts"] if filled_count == leg_count and fills else None,
        "completed": filled_count == leg_count and leg_count > 0,
        "partial_fill": 0 < filled_count < leg_count,
        "filled_leg_count": filled_count,
        "leg_count": leg_count,
        "fill_ratio": filled_count / leg_count if leg_count else 0.0,
        "maker_edge_per_share": candidate.get("maker_edge_per_share"),
        "maker_roi": candidate.get("maker_roi"),
        "expected_edge_at_cap": candidate.get("expected_edge_at_cap"),
        "passive_cost_per_share": candidate.get("passive_cost_per_share"),
        "filled_cost_per_share": filled_cost_per_share,
        "unfilled_cost_per_share": unfilled_cost_per_share,
        "filled_capital_at_cap": filled_capital_at_cap,
        "market_ids": candidate.get("market_ids"),
        "legs": candidate.get("legs"),
        "fills": fills,
        "unfilled_legs": [open_legs[index] for index in sorted(open_legs)],
        "risk_flags": candidate.get("risk_flags"),
    }
    return row


def _leg_fill_observation(snapshot: BinaryMarketSnapshot, leg: dict) -> Optional[dict]:
    token = str(leg.get("token") or "")
    book = _token_book(snapshot, token)
    if not book.asks:
        return None
    best_ask = book.asks[0].price
    limit_price = float(leg.get("limit_price") or 0.0)
    if best_ask > limit_price:
        return None
    return {
        "fill_ts": snapshot.ts,
        "market_id": snapshot.market_id,
        "token": token,
        "limit_price": limit_price,
        "observed_best_ask": best_ask,
    }


def _dedupe_sim_candidates(candidates: List[dict]) -> List[dict]:
    deduped = {}
    for candidate in candidates:
        key = tuple(
            sorted(
                (
                    str(leg.get("venue") or ""),
                    str(leg.get("market_id") or ""),
                    str(leg.get("token") or ""),
                    float(leg.get("limit_price") or 0.0),
                )
                for leg in candidate.get("legs", [])
            )
        )
        previous = deduped.get(key)
        if previous is None or _candidate_sort_key(candidate) < _candidate_sort_key(previous):
            deduped[key] = candidate
    rows = list(deduped.values())
    rows.sort(key=_candidate_sort_key)
    return rows


def _fill_summary_by_kind(rows: List[dict]) -> list:
    summary = {}
    for row in rows:
        item = summary.setdefault(
            row.get("kind") or "unknown",
            {
                "kind": row.get("kind") or "unknown",
                "candidate_observation_count": 0,
                "completed_count": 0,
                "partial_count": 0,
                "no_fill_count": 0,
                "max_completed_expected_edge_at_cap": 0.0,
            },
        )
        item["candidate_observation_count"] += 1
        if row.get("completed"):
            item["completed_count"] += 1
            item["max_completed_expected_edge_at_cap"] = max(
                item["max_completed_expected_edge_at_cap"],
                float(row.get("expected_edge_at_cap") or 0.0),
            )
        elif row.get("partial_fill"):
            item["partial_count"] += 1
        elif row.get("filled_leg_count") == 0:
            item["no_fill_count"] += 1
    for item in summary.values():
        count = item["candidate_observation_count"]
        item["completion_rate"] = item["completed_count"] / count if count else 0.0
        item["partial_rate"] = item["partial_count"] / count if count else 0.0
    return sorted(summary.values(), key=lambda row: (-row["completed_count"], row["kind"]))


def _fill_result_sort_key(row: dict) -> tuple:
    return (
        not bool(row.get("completed")),
        -float(row.get("expected_edge_at_cap") or 0.0),
        -float(row.get("fill_ratio") or 0.0),
        str(row.get("candidate_key") or ""),
    )


def _candidate_identity(candidate: dict) -> str:
    legs = "|".join(
        sorted(
            f"{leg.get('venue')}:{leg.get('market_id')}:{leg.get('token')}:{leg.get('side')}@{leg.get('limit_price')}"
            for leg in candidate.get("legs", [])
        )
    )
    return f"{candidate.get('kind')}:{legs}"


def _batch_ts(batch: List[BinaryMarketSnapshot]) -> Optional[str]:
    return batch[0].ts if batch else None


def _parse_ts(value: Optional[str]):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
