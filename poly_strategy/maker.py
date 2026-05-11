from collections import Counter, defaultdict
import json
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from poly_strategy.backtest import RuleSet, load_rule_set, snapshots_from_ndjson_lines
from poly_strategy.fees import taker_fee_per_share
from poly_strategy.models import BinaryMarketSnapshot, OrderBook
from poly_strategy.orderbook import insufficient_liquidity, take_levels
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


def maker_hedge_scan_report(
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
    candidates = scan_maker_hedge_candidates(
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
        "type": "maker_hedge_scan_report",
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
        "by_kind": _summary_by_hedge_kind(candidates),
        "top": candidates[:top_n],
    }


def maker_hedge_sim_report(
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
    results = simulate_maker_hedges(
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
    unsafe = [row for row in results if row["maker_filled"] and not row["completed"]]
    no_fill = [row for row in results if not row["maker_filled"]]
    completed_edge_at_cap = sum(float(row.get("realized_edge_at_cap") or 0.0) for row in completed)
    unsafe_capital_at_cap = sum(float(row.get("maker_capital_at_cap") or 0.0) for row in unsafe)
    return {
        "type": "maker_hedge_sim_report",
        "snapshots_path": str(snapshots_path),
        "rules_path": str(rules_path) if rules_path else None,
        "gamma_path": str(gamma_path) if gamma_path else None,
        "batch_count": len(batches),
        "candidate_observation_count": len(results),
        "completed_count": len(completed),
        "unsafe_fill_count": len(unsafe),
        "no_fill_count": len(no_fill),
        "completion_rate": len(completed) / len(results) if results else 0.0,
        "unsafe_fill_rate": len(unsafe) / len(results) if results else 0.0,
        "completed_realized_edge_at_cap": completed_edge_at_cap,
        "max_completed_realized_edge_at_cap": max(
            (float(row.get("realized_edge_at_cap") or 0.0) for row in completed),
            default=0.0,
        ),
        "unsafe_maker_capital_at_cap": unsafe_capital_at_cap,
        "quote_mode": _normalize_quote_mode(quote_mode),
        "quote_offset_ticks": quote_offset_ticks,
        "by_kind": _hedge_fill_summary_by_kind(results),
        "top_completed": sorted(completed, key=_hedge_result_sort_key)[:top_n],
        "top_unsafe": sorted(unsafe, key=_hedge_result_sort_key)[:top_n],
        "top_unfilled": sorted(no_fill, key=_hedge_result_sort_key)[:top_n],
        "status": "positive_ev_hedge_found" if completed_edge_at_cap > 0 and completed else "no_positive_ev_hedge",
    }


def maker_hybrid_scan_report(
    snapshots_path: Path,
    rules_path: Optional[Path] = None,
    gamma_path: Optional[Path] = None,
    tick_size: float = 0.001,
    min_edge: float = 0.0,
    min_roi: Optional[float] = None,
    max_capital: Optional[float] = None,
    max_leg_count: int = 80,
    min_maker_legs: int = 2,
    max_maker_legs: int = 3,
    maker_selection_pool_size: int = 8,
    max_maker_combinations: int = 25,
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
    min_maker_legs, max_maker_legs = _normalize_maker_leg_bounds(min_maker_legs, max_maker_legs)
    maker_selection_pool_size = _normalize_positive_int(maker_selection_pool_size, "maker_selection_pool_size")
    max_maker_combinations = _normalize_positive_int(max_maker_combinations, "max_maker_combinations")
    quote_offset_ticks = _normalize_quote_offset_ticks(quote_offset_ticks)

    snapshots = latest_snapshot_batch(snapshots_path)
    rule_set = load_rule_set(rules_path, gamma_path=gamma_path)
    candidates = scan_maker_hybrid_candidates(
        snapshots,
        rule_set,
        tick_size=tick_size,
        min_edge=min_edge,
        min_roi=min_roi,
        max_capital=max_capital,
        max_leg_count=max_leg_count,
        min_maker_legs=min_maker_legs,
        max_maker_legs=max_maker_legs,
        maker_selection_pool_size=maker_selection_pool_size,
        max_maker_combinations=max_maker_combinations,
        include_yes_no_pairs=include_yes_no_pairs,
        quote_mode=quote_mode,
        quote_offset_ticks=quote_offset_ticks,
    )
    return {
        "type": "maker_hybrid_scan_report",
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
        "min_maker_legs": min_maker_legs,
        "max_maker_legs": max_maker_legs,
        "maker_selection_pool_size": maker_selection_pool_size,
        "max_maker_combinations": max_maker_combinations,
        "quote_mode": _normalize_quote_mode(quote_mode),
        "quote_offset_ticks": quote_offset_ticks,
        "candidate_count": len(candidates),
        "by_kind": _summary_by_hybrid_kind(candidates),
        "top": candidates[:top_n],
    }


def maker_hybrid_sim_report(
    snapshots_path: Path,
    rules_path: Optional[Path] = None,
    gamma_path: Optional[Path] = None,
    tick_size: float = 0.001,
    min_edge: float = 0.0,
    min_roi: Optional[float] = None,
    max_capital: Optional[float] = None,
    max_leg_count: int = 80,
    min_maker_legs: int = 2,
    max_maker_legs: int = 3,
    maker_selection_pool_size: int = 8,
    max_maker_combinations: int = 25,
    quote_mode: str = "near_ask",
    fill_model: str = "crossed_ask",
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
    min_maker_legs, max_maker_legs = _normalize_maker_leg_bounds(min_maker_legs, max_maker_legs)
    maker_selection_pool_size = _normalize_positive_int(maker_selection_pool_size, "maker_selection_pool_size")
    max_maker_combinations = _normalize_positive_int(max_maker_combinations, "max_maker_combinations")
    fill_model = _normalize_fill_model(fill_model)
    quote_offset_ticks = _normalize_quote_offset_ticks(quote_offset_ticks)

    rule_set = load_rule_set(rules_path, gamma_path=gamma_path)
    batches = list(snapshot_batches_from_path(snapshots_path))
    results = simulate_maker_hybrids(
        batches,
        rule_set,
        tick_size=tick_size,
        min_edge=min_edge,
        min_roi=min_roi,
        max_capital=max_capital,
        max_leg_count=max_leg_count,
        min_maker_legs=min_maker_legs,
        max_maker_legs=max_maker_legs,
        maker_selection_pool_size=maker_selection_pool_size,
        max_maker_combinations=max_maker_combinations,
        quote_mode=quote_mode,
        quote_offset_ticks=quote_offset_ticks,
        fill_model=fill_model,
        horizon_seconds=horizon_seconds,
        max_candidates_per_batch=max_candidates_per_batch,
        include_yes_no_pairs=include_yes_no_pairs,
    )

    completed = [row for row in results if row["completed"]]
    unsafe = [row for row in results if row["maker_filled"] and not row["completed"]]
    partial = [row for row in results if row["partial_maker_fill"] and not row["maker_filled"]]
    no_fill = [row for row in results if not row["maker_filled"] and not row["partial_maker_fill"]]
    completed_edge_at_cap = sum(float(row.get("realized_edge_at_cap") or 0.0) for row in completed)
    partial_capital_at_cap = sum(float(row.get("filled_maker_capital_at_cap") or 0.0) for row in partial)
    unsafe_capital_at_cap = sum(float(row.get("maker_capital_at_cap") or 0.0) for row in unsafe)
    return {
        "type": "maker_hybrid_sim_report",
        "snapshots_path": str(snapshots_path),
        "rules_path": str(rules_path) if rules_path else None,
        "gamma_path": str(gamma_path) if gamma_path else None,
        "batch_count": len(batches),
        "candidate_observation_count": len(results),
        "completed_count": len(completed),
        "unsafe_fill_count": len(unsafe),
        "partial_maker_fill_count": len(partial),
        "no_fill_count": len(no_fill),
        "completion_rate": len(completed) / len(results) if results else 0.0,
        "unsafe_fill_rate": len(unsafe) / len(results) if results else 0.0,
        "partial_maker_fill_rate": len(partial) / len(results) if results else 0.0,
        "completed_realized_edge_at_cap": completed_edge_at_cap,
        "max_completed_realized_edge_at_cap": max(
            (float(row.get("realized_edge_at_cap") or 0.0) for row in completed),
            default=0.0,
        ),
        "unsafe_maker_capital_at_cap": unsafe_capital_at_cap,
        "partial_filled_maker_capital_at_cap": partial_capital_at_cap,
        "min_maker_legs": min_maker_legs,
        "max_maker_legs": max_maker_legs,
        "maker_selection_pool_size": maker_selection_pool_size,
        "max_maker_combinations": max_maker_combinations,
        "quote_mode": _normalize_quote_mode(quote_mode),
        "quote_offset_ticks": quote_offset_ticks,
        "fill_model": fill_model,
        "by_kind": _hybrid_fill_summary_by_kind(results),
        "top_completed": sorted(completed, key=_hybrid_result_sort_key)[:top_n],
        "top_unsafe": sorted(unsafe, key=_hybrid_result_sort_key)[:top_n],
        "top_partial": sorted(partial, key=_hybrid_result_sort_key)[:top_n],
        "top_unfilled": sorted(no_fill, key=_hybrid_result_sort_key)[:top_n],
        "status": "positive_ev_hybrid_found" if completed_edge_at_cap > 0 and completed else "no_positive_ev_hybrid",
    }


def maker_hybrid_tape_sim_report(
    snapshots_path: Path,
    trades_path: Path,
    rules_path: Optional[Path] = None,
    gamma_path: Optional[Path] = None,
    tick_size: float = 0.001,
    min_edge: float = 0.0,
    min_roi: Optional[float] = None,
    max_capital: Optional[float] = None,
    max_leg_count: int = 80,
    min_maker_legs: int = 2,
    max_maker_legs: int = 3,
    maker_selection_pool_size: int = 8,
    max_maker_combinations: int = 25,
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
    min_maker_legs, max_maker_legs = _normalize_maker_leg_bounds(min_maker_legs, max_maker_legs)
    maker_selection_pool_size = _normalize_positive_int(maker_selection_pool_size, "maker_selection_pool_size")
    max_maker_combinations = _normalize_positive_int(max_maker_combinations, "max_maker_combinations")
    quote_offset_ticks = _normalize_quote_offset_ticks(quote_offset_ticks)

    rule_set = load_rule_set(rules_path, gamma_path=gamma_path)
    batches = list(snapshot_batches_from_path(snapshots_path))
    trades = _trade_tape_rows_from_path(trades_path)
    results = simulate_maker_hybrid_tape_fills(
        batches,
        trades,
        rule_set,
        tick_size=tick_size,
        min_edge=min_edge,
        min_roi=min_roi,
        max_capital=max_capital,
        max_leg_count=max_leg_count,
        min_maker_legs=min_maker_legs,
        max_maker_legs=max_maker_legs,
        maker_selection_pool_size=maker_selection_pool_size,
        max_maker_combinations=max_maker_combinations,
        quote_mode=quote_mode,
        quote_offset_ticks=quote_offset_ticks,
        horizon_seconds=horizon_seconds,
        max_candidates_per_batch=max_candidates_per_batch,
        include_yes_no_pairs=include_yes_no_pairs,
    )

    completed = [row for row in results if row["completed"]]
    unsafe = [row for row in results if row["maker_filled"] and not row["completed"]]
    partial = [row for row in results if row["partial_maker_fill"] and not row["maker_filled"]]
    no_fill = [row for row in results if not row["maker_filled"] and not row["partial_maker_fill"]]
    completed_edge_at_cap = sum(float(row.get("realized_edge_at_cap") or 0.0) for row in completed)
    unique_completed = _unique_tape_completed_rows(completed)
    unique_completed_edge_at_cap = sum(float(row.get("realized_edge_at_cap") or 0.0) for row in unique_completed)
    return {
        "type": "maker_hybrid_tape_sim_report",
        "snapshots_path": str(snapshots_path),
        "trades_path": str(trades_path),
        "rules_path": str(rules_path) if rules_path else None,
        "gamma_path": str(gamma_path) if gamma_path else None,
        "batch_count": len(batches),
        "trade_count": len(trades),
        "candidate_observation_count": len(results),
        "completed_count": len(completed),
        "unique_completed_count": len(unique_completed),
        "unsafe_fill_count": len(unsafe),
        "partial_maker_fill_count": len(partial),
        "no_fill_count": len(no_fill),
        "completion_rate": len(completed) / len(results) if results else 0.0,
        "unsafe_fill_rate": len(unsafe) / len(results) if results else 0.0,
        "partial_maker_fill_rate": len(partial) / len(results) if results else 0.0,
        "completed_realized_edge_at_cap": completed_edge_at_cap,
        "unique_completed_realized_edge_at_cap": unique_completed_edge_at_cap,
        "max_completed_realized_edge_at_cap": max(
            (float(row.get("realized_edge_at_cap") or 0.0) for row in completed),
            default=0.0,
        ),
        "min_maker_legs": min_maker_legs,
        "max_maker_legs": max_maker_legs,
        "maker_selection_pool_size": maker_selection_pool_size,
        "max_maker_combinations": max_maker_combinations,
        "quote_mode": _normalize_quote_mode(quote_mode),
        "quote_offset_ticks": quote_offset_ticks,
        "fill_model": "trade_tape_sell_through",
        "diagnostic_only": True,
        "diagnostic_warning": "public trade prints can prove sell-through, but queue position is still uncertain without live order fills",
        "by_kind": _hybrid_fill_summary_by_kind(results),
        "rejection_by_reason": _hybrid_rejection_summary(results),
        "maker_fill_progress_distribution": _maker_fill_progress_distribution(results),
        "top_unfilled_maker_legs": _top_unfilled_maker_legs(results, top_n),
        "top_completed": sorted(completed, key=_hybrid_result_sort_key)[:top_n],
        "top_unique_completed": sorted(unique_completed, key=_hybrid_result_sort_key)[:top_n],
        "top_unsafe": sorted(unsafe, key=_hybrid_result_sort_key)[:top_n],
        "top_partial": sorted(partial, key=_hybrid_result_sort_key)[:top_n],
        "top_unfilled": sorted(no_fill, key=_hybrid_result_sort_key)[:top_n],
        "status": "tape_positive_ev_candidate_found" if unique_completed_edge_at_cap > 0 and unique_completed else "no_tape_positive_ev_candidate",
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


def simulate_maker_hedges(
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
        candidates = scan_maker_hedge_candidates(
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
        candidates = _dedupe_hedge_candidates(candidates)[:max_candidates_per_batch]
        if not candidates:
            continue
        future_batches = _future_batches_within_horizon(batches, index, horizon_seconds)
        for candidate in candidates:
            results.append(_simulate_hedge_candidate(candidate, future_batches, min_edge=min_edge))
    return results


def simulate_maker_hybrids(
    batches: List[List[BinaryMarketSnapshot]],
    rule_set: RuleSet,
    tick_size: float = 0.001,
    min_edge: float = 0.0,
    min_roi: Optional[float] = None,
    max_capital: Optional[float] = None,
    max_leg_count: int = 80,
    min_maker_legs: int = 2,
    max_maker_legs: int = 3,
    maker_selection_pool_size: int = 8,
    max_maker_combinations: int = 25,
    quote_mode: str = "near_ask",
    quote_offset_ticks: int = 1,
    fill_model: str = "crossed_ask",
    horizon_seconds: float = 300.0,
    max_candidates_per_batch: int = 25,
    include_yes_no_pairs: bool = False,
) -> List[dict]:
    min_maker_legs, max_maker_legs = _normalize_maker_leg_bounds(min_maker_legs, max_maker_legs)
    maker_selection_pool_size = _normalize_positive_int(maker_selection_pool_size, "maker_selection_pool_size")
    max_maker_combinations = _normalize_positive_int(max_maker_combinations, "max_maker_combinations")
    fill_model = _normalize_fill_model(fill_model)
    results = []
    for index, batch in enumerate(batches[:-1]):
        candidates = scan_maker_hybrid_candidates(
            batch,
            rule_set,
            tick_size=tick_size,
            min_edge=min_edge,
            min_roi=min_roi,
            max_capital=max_capital,
            max_leg_count=max_leg_count,
            min_maker_legs=min_maker_legs,
            max_maker_legs=max_maker_legs,
            maker_selection_pool_size=maker_selection_pool_size,
            max_maker_combinations=max_maker_combinations,
            include_yes_no_pairs=include_yes_no_pairs,
            quote_mode=quote_mode,
            quote_offset_ticks=quote_offset_ticks,
        )
        candidates = _dedupe_hybrid_candidates(candidates)[:max_candidates_per_batch]
        if not candidates:
            continue
        future_batches = _future_batches_within_horizon(batches, index, horizon_seconds)
        for candidate in candidates:
            results.append(_simulate_hybrid_candidate(candidate, future_batches, min_edge=min_edge, fill_model=fill_model))
    return results


def simulate_maker_hybrid_tape_fills(
    batches: List[List[BinaryMarketSnapshot]],
    trades: List[dict],
    rule_set: RuleSet,
    tick_size: float = 0.001,
    min_edge: float = 0.0,
    min_roi: Optional[float] = None,
    max_capital: Optional[float] = None,
    max_leg_count: int = 80,
    min_maker_legs: int = 2,
    max_maker_legs: int = 3,
    maker_selection_pool_size: int = 8,
    max_maker_combinations: int = 25,
    quote_mode: str = "near_ask",
    quote_offset_ticks: int = 1,
    horizon_seconds: float = 300.0,
    max_candidates_per_batch: int = 25,
    include_yes_no_pairs: bool = False,
) -> List[dict]:
    min_maker_legs, max_maker_legs = _normalize_maker_leg_bounds(min_maker_legs, max_maker_legs)
    maker_selection_pool_size = _normalize_positive_int(maker_selection_pool_size, "maker_selection_pool_size")
    max_maker_combinations = _normalize_positive_int(max_maker_combinations, "max_maker_combinations")
    min_dt = datetime.min.replace(tzinfo=timezone.utc)
    ordered_trades = sorted(trades, key=lambda row: (_parse_ts(row.get("trade_ts")) or min_dt, row.get("asset_id") or ""))
    results = []
    for index, batch in enumerate(batches[:-1]):
        candidates = scan_maker_hybrid_candidates(
            batch,
            rule_set,
            tick_size=tick_size,
            min_edge=min_edge,
            min_roi=min_roi,
            max_capital=max_capital,
            max_leg_count=max_leg_count,
            min_maker_legs=min_maker_legs,
            max_maker_legs=max_maker_legs,
            maker_selection_pool_size=maker_selection_pool_size,
            max_maker_combinations=max_maker_combinations,
            include_yes_no_pairs=include_yes_no_pairs,
            quote_mode=quote_mode,
            quote_offset_ticks=quote_offset_ticks,
        )
        candidates = _dedupe_hybrid_candidates(candidates)[:max_candidates_per_batch]
        if not candidates:
            continue
        future_batches = _future_batches_within_horizon(batches, index, horizon_seconds)
        for candidate in candidates:
            results.append(
                _simulate_hybrid_candidate_with_trade_tape(
                    candidate,
                    ordered_trades,
                    future_batches,
                    horizon_seconds=horizon_seconds,
                    min_edge=min_edge,
                )
            )
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
    snapshots = [snapshot for snapshot in snapshots if _snapshot_has_valid_spreads(snapshot)]
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


def scan_maker_hedge_candidates(
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

    rows = []
    for spec in _hedge_basket_specs(
        snapshots,
        rule_set,
        max_leg_count=max_leg_count,
        include_yes_no_pairs=include_yes_no_pairs,
    ):
        leg_specs = spec["leg_specs"]
        for maker_leg_index in range(len(leg_specs)):
            row = _maker_hedge_candidate_row(
                spec["kind"],
                leg_specs,
                payout_per_share=spec["payout_per_share"],
                maker_leg_index=maker_leg_index,
                tick_size=tick_size,
                min_edge=min_edge,
                min_roi=min_roi,
                max_capital=max_capital,
                quote_mode=quote_mode,
                quote_offset_ticks=quote_offset_ticks,
                extra=spec.get("extra"),
            )
            if row:
                rows.append(row)

    rows = _dedupe_hedge_candidates(rows)
    rows.sort(key=_hedge_candidate_sort_key)
    return rows


def scan_maker_hybrid_candidates(
    snapshots: List[BinaryMarketSnapshot],
    rule_set: RuleSet,
    tick_size: float = 0.001,
    min_edge: float = 0.0,
    min_roi: Optional[float] = None,
    max_capital: Optional[float] = None,
    max_leg_count: int = 80,
    min_maker_legs: int = 2,
    max_maker_legs: int = 3,
    maker_selection_pool_size: int = 8,
    max_maker_combinations: int = 25,
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
    min_maker_legs, max_maker_legs = _normalize_maker_leg_bounds(min_maker_legs, max_maker_legs)
    maker_selection_pool_size = _normalize_positive_int(maker_selection_pool_size, "maker_selection_pool_size")
    max_maker_combinations = _normalize_positive_int(max_maker_combinations, "max_maker_combinations")
    quote_mode = _normalize_quote_mode(quote_mode)
    quote_offset_ticks = _normalize_quote_offset_ticks(quote_offset_ticks)

    rows = []
    for spec in _hedge_basket_specs(
        snapshots,
        rule_set,
        max_leg_count=max_leg_count,
        include_yes_no_pairs=include_yes_no_pairs,
    ):
        leg_specs = spec["leg_specs"]
        if len(leg_specs) < 3:
            continue
        max_for_spec = min(max_maker_legs, len(leg_specs) - 1)
        if min_maker_legs > max_for_spec:
            continue
        for maker_leg_count in range(min_maker_legs, max_for_spec + 1):
            for maker_indices in _maker_hybrid_index_combinations(
                leg_specs,
                maker_leg_count=maker_leg_count,
                tick_size=tick_size,
                quote_mode=quote_mode,
                quote_offset_ticks=quote_offset_ticks,
                maker_selection_pool_size=maker_selection_pool_size,
                max_maker_combinations=max_maker_combinations,
            ):
                row = _maker_hybrid_candidate_row(
                    spec["kind"],
                    leg_specs,
                    payout_per_share=spec["payout_per_share"],
                    maker_leg_count=maker_leg_count,
                    maker_leg_indices=maker_indices,
                    tick_size=tick_size,
                    min_edge=min_edge,
                    min_roi=min_roi,
                    max_capital=max_capital,
                    quote_mode=quote_mode,
                    quote_offset_ticks=quote_offset_ticks,
                    extra=spec.get("extra"),
                )
                if row:
                    rows.append(row)

    rows = _dedupe_hybrid_candidates(rows)
    rows.sort(key=_hybrid_candidate_sort_key)
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


def _maker_hedge_candidate_row(
    kind: str,
    leg_specs: List[Tuple[BinaryMarketSnapshot, str]],
    payout_per_share: float,
    maker_leg_index: int,
    tick_size: float,
    min_edge: float,
    min_roi: Optional[float],
    max_capital: Optional[float],
    quote_mode: str,
    quote_offset_ticks: int,
    extra: Optional[dict] = None,
) -> Optional[dict]:
    if len(leg_specs) < 2 or maker_leg_index < 0 or maker_leg_index >= len(leg_specs):
        return None

    maker_snapshot, maker_token = leg_specs[maker_leg_index]
    maker_leg = _passive_buy_leg(maker_snapshot, maker_token, tick_size, quote_mode, quote_offset_ticks)
    if maker_leg is None:
        return None

    hedge_legs = []
    taker_cost = 0.0
    max_quantity = None
    for index, (snapshot, token) in enumerate(leg_specs):
        if index == maker_leg_index:
            continue
        leg = _taker_buy_leg(snapshot, token)
        if leg is None:
            return None
        hedge_legs.append({**leg, "source_leg_index": index})
        taker_cost += leg["cost_per_share"]
        top_size = float(leg.get("top_size") or 0.0)
        max_quantity = top_size if max_quantity is None else min(max_quantity, top_size)

    cost = maker_leg["limit_price"] + taker_cost
    if cost <= 0:
        return None
    edge = payout_per_share - cost
    if edge <= min_edge:
        return None
    roi = edge / cost
    if min_roi is not None and roi < min_roi:
        return None

    suggested_quantity = max_quantity
    if max_capital is not None and max_capital > 0:
        suggested_quantity = min(max_quantity or 0.0, max_capital / cost)
    expected_edge_at_cap = None
    capital_used_at_cap = None
    maker_capital_at_cap = None
    if suggested_quantity is not None:
        capital_used_at_cap = suggested_quantity * cost
        maker_capital_at_cap = suggested_quantity * maker_leg["limit_price"]
        expected_edge_at_cap = suggested_quantity * edge

    row = {
        "type": "maker_hedge_candidate",
        "kind": kind,
        "ts": leg_specs[0][0].ts,
        "market_ids": [snapshot.market_id for snapshot, _ in leg_specs],
        "leg_count": len(leg_specs),
        "maker_leg_index": maker_leg_index,
        "payout_per_share": payout_per_share,
        "maker_limit_price": maker_leg["limit_price"],
        "hedge_taker_cost_per_share": taker_cost,
        "combined_cost_per_share": cost,
        "maker_edge_per_share": edge,
        "maker_roi": roi,
        "suggested_quantity": suggested_quantity,
        "capital_used_at_cap": capital_used_at_cap,
        "maker_capital_at_cap": maker_capital_at_cap,
        "expected_edge_at_cap": expected_edge_at_cap,
        "quote_mode": quote_mode,
        "quote_offset_ticks": quote_offset_ticks,
        "risk_flags": [
            "maker_leg_fill_then_immediate_taker_hedge",
            "requires_fast_hedge_after_fill",
            "non_atomic_execution",
            "partial_fill_unhedged_exposure",
            "maker_queue_and_adverse_selection_risk",
        ],
        "maker_leg": maker_leg,
        "hedge_legs": hedge_legs,
        "legs": _ordered_hedge_candidate_legs(maker_leg, hedge_legs, maker_leg_index),
    }
    if extra:
        row.update(extra)
    return row


def _maker_hybrid_candidate_row(
    kind: str,
    leg_specs: List[Tuple[BinaryMarketSnapshot, str]],
    payout_per_share: float,
    maker_leg_count: int,
    maker_leg_indices: Optional[Sequence[int]],
    tick_size: float,
    min_edge: float,
    min_roi: Optional[float],
    max_capital: Optional[float],
    quote_mode: str,
    quote_offset_ticks: int,
    extra: Optional[dict] = None,
) -> Optional[dict]:
    if len(leg_specs) < 3 or maker_leg_count < 2 or maker_leg_count >= len(leg_specs):
        return None

    passive_by_index = {}
    taker_by_index = {}
    savings = []
    all_taker_cost = 0.0
    for index, (snapshot, token) in enumerate(leg_specs):
        taker_leg = _taker_buy_leg(snapshot, token)
        maker_leg = _passive_buy_leg(snapshot, token, tick_size, quote_mode, quote_offset_ticks)
        if taker_leg is None or maker_leg is None:
            return None
        taker_by_index[index] = taker_leg
        passive_by_index[index] = maker_leg
        all_taker_cost += taker_leg["cost_per_share"]
        saving = float(taker_leg["cost_per_share"] or 0.0) - float(maker_leg["limit_price"] or 0.0)
        if saving > 0:
            savings.append((saving, index))

    savings_by_index = {index: saving for saving, index in savings}
    if maker_leg_indices is None:
        if len(savings) < maker_leg_count:
            return None
        savings.sort(key=lambda item: (-item[0], item[1]))
        maker_indices = sorted(index for _, index in savings[:maker_leg_count])
    else:
        maker_indices = sorted({int(index) for index in maker_leg_indices})
        if len(maker_indices) != maker_leg_count:
            return None
        if any(index < 0 or index >= len(leg_specs) or savings_by_index.get(index, 0.0) <= 0 for index in maker_indices):
            return None

    maker_legs = []
    hedge_legs = []
    maker_cost = 0.0
    hedge_cost = 0.0
    max_quantity = None
    for index in range(len(leg_specs)):
        if index in maker_indices:
            leg = dict(passive_by_index[index])
            leg["source_leg_index"] = index
            maker_legs.append(leg)
            maker_cost += leg["limit_price"]
            continue
        leg = dict(taker_by_index[index])
        leg["source_leg_index"] = index
        hedge_legs.append(leg)
        hedge_cost += leg["cost_per_share"]
        top_size = float(leg.get("top_size") or 0.0)
        max_quantity = top_size if max_quantity is None else min(max_quantity, top_size)

    if not hedge_legs or max_quantity is None or max_quantity <= 0:
        return None

    cost = maker_cost + hedge_cost
    if cost <= 0:
        return None
    edge = payout_per_share - cost
    if edge <= min_edge:
        return None
    roi = edge / cost
    if min_roi is not None and roi < min_roi:
        return None

    suggested_quantity = max_quantity
    if max_capital is not None and max_capital > 0:
        suggested_quantity = min(max_quantity, max_capital / cost)
    capital_used_at_cap = suggested_quantity * cost
    maker_capital_at_cap = suggested_quantity * maker_cost
    expected_edge_at_cap = suggested_quantity * edge

    row = {
        "type": "maker_hybrid_candidate",
        "kind": kind.replace("maker_hedge_", "maker_hybrid_", 1),
        "ts": leg_specs[0][0].ts,
        "market_ids": [snapshot.market_id for snapshot, _ in leg_specs],
        "leg_count": len(leg_specs),
        "maker_leg_count": maker_leg_count,
        "maker_leg_indices": maker_indices,
        "hedge_leg_count": len(hedge_legs),
        "payout_per_share": payout_per_share,
        "all_taker_cost_per_share": all_taker_cost,
        "maker_limit_cost_per_share": maker_cost,
        "hedge_taker_cost_per_share": hedge_cost,
        "combined_cost_per_share": cost,
        "maker_savings_per_share": all_taker_cost - cost,
        "maker_edge_per_share": edge,
        "maker_roi": roi,
        "suggested_quantity": suggested_quantity,
        "capital_used_at_cap": capital_used_at_cap,
        "maker_capital_at_cap": maker_capital_at_cap,
        "expected_edge_at_cap": expected_edge_at_cap,
        "quote_mode": quote_mode,
        "quote_offset_ticks": quote_offset_ticks,
        "risk_flags": [
            "requires_multiple_maker_legs_fill_before_hedge",
            "requires_fast_taker_hedge_after_all_maker_fills",
            "non_atomic_execution",
            "partial_maker_fill_directional_exposure",
            "maker_queue_and_adverse_selection_risk",
        ],
        "maker_legs": maker_legs,
        "hedge_legs": hedge_legs,
        "legs": _ordered_hybrid_candidate_legs(maker_legs, hedge_legs),
    }
    if extra:
        row.update(extra)
    return row


def _maker_hybrid_index_combinations(
    leg_specs: List[Tuple[BinaryMarketSnapshot, str]],
    maker_leg_count: int,
    tick_size: float,
    quote_mode: str,
    quote_offset_ticks: int,
    maker_selection_pool_size: int,
    max_maker_combinations: int,
) -> List[Tuple[int, ...]]:
    savings = []
    for index, (snapshot, token) in enumerate(leg_specs):
        taker_leg = _taker_buy_leg(snapshot, token)
        maker_leg = _passive_buy_leg(snapshot, token, tick_size, quote_mode, quote_offset_ticks)
        if taker_leg is None or maker_leg is None:
            return []
        saving = float(taker_leg["cost_per_share"] or 0.0) - float(maker_leg["limit_price"] or 0.0)
        if saving > 0:
            savings.append((saving, index))
    if len(savings) < maker_leg_count:
        return []

    savings.sort(key=lambda item: (-item[0], item[1]))
    savings_by_index = {index: saving for saving, index in savings}
    pool_size = max(maker_leg_count, maker_selection_pool_size)
    pool = [index for _, index in savings[:pool_size]]
    ranked = []
    for combo in combinations(pool, maker_leg_count):
        indices = tuple(sorted(combo))
        total_saving = sum(savings_by_index[index] for index in indices)
        ranked.append((-total_saving, indices))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [indices for _, indices in ranked[:max_maker_combinations]]


def _hedge_basket_specs(
    snapshots: List[BinaryMarketSnapshot],
    rule_set: RuleSet,
    max_leg_count: int,
    include_yes_no_pairs: bool,
) -> List[dict]:
    snapshots = [snapshot for snapshot in snapshots if _snapshot_has_valid_spreads(snapshot)]
    by_market_id = {snapshot.market_id: snapshot for snapshot in snapshots}
    specs = []

    if include_yes_no_pairs:
        for snapshot in snapshots:
            specs.append(
                {
                    "kind": "maker_hedge_yes_no_pair",
                    "leg_specs": [(snapshot, "YES"), (snapshot, "NO")],
                    "payout_per_share": 1.0,
                }
            )

    for rule in rule_set.implications:
        antecedent = by_market_id.get(rule.antecedent_market_id)
        consequent = by_market_id.get(rule.consequent_market_id)
        if antecedent is None or consequent is None:
            continue
        specs.append(
            {
                "kind": "maker_hedge_implication",
                "leg_specs": [(consequent, "YES"), (antecedent, "NO")],
                "payout_per_share": 1.0,
            }
        )

    seen_pair_specs = set()
    for rule in rule_set.mutual_exclusions:
        first = by_market_id.get(rule.first_market_id)
        second = by_market_id.get(rule.second_market_id)
        if first is None or second is None:
            continue
        key = tuple(sorted([first.market_id, second.market_id]))
        if key in seen_pair_specs:
            continue
        seen_pair_specs.add(key)
        specs.append(
            {
                "kind": "maker_hedge_mutually_exclusive",
                "leg_specs": [(first, "NO"), (second, "NO")],
                "payout_per_share": 1.0,
            }
        )

    for rule in rule_set.equivalences:
        first = by_market_id.get(rule.first_market_id)
        second = by_market_id.get(rule.second_market_id)
        if first is None or second is None:
            continue
        specs.extend(
            [
                {
                    "kind": "maker_hedge_equivalent",
                    "leg_specs": [(first, "YES"), (second, "NO")],
                    "payout_per_share": 1.0,
                },
                {
                    "kind": "maker_hedge_equivalent",
                    "leg_specs": [(second, "YES"), (first, "NO")],
                    "payout_per_share": 1.0,
                },
            ]
        )

    for rule in rule_set.collectively_exhaustive:
        first = by_market_id.get(rule.first_market_id)
        second = by_market_id.get(rule.second_market_id)
        if first is None or second is None:
            continue
        specs.append(
            {
                "kind": "maker_hedge_collectively_exhaustive",
                "leg_specs": [(first, "YES"), (second, "YES")],
                "payout_per_share": 1.0,
            }
        )

    for rule in rule_set.complements:
        first = by_market_id.get(rule.first_market_id)
        second = by_market_id.get(rule.second_market_id)
        if first is None or second is None:
            continue
        specs.extend(
            [
                {
                    "kind": "maker_hedge_complement_yes_bundle",
                    "leg_specs": [(first, "YES"), (second, "YES")],
                    "payout_per_share": 1.0,
                },
                {
                    "kind": "maker_hedge_complement_no_bundle",
                    "leg_specs": [(first, "NO"), (second, "NO")],
                    "payout_per_share": 1.0,
                },
            ]
        )

    for rule in rule_set.neg_risk_groups:
        market_ids = _unique_market_ids(rule.market_ids)
        if len(market_ids) < 2 or len(market_ids) > max_leg_count:
            continue
        group_snapshots = [by_market_id.get(market_id) for market_id in market_ids]
        if any(snapshot is None for snapshot in group_snapshots):
            continue
        specs.append(
            {
                "kind": "maker_hedge_neg_risk_no_basket",
                "leg_specs": [(snapshot, "NO") for snapshot in group_snapshots],
                "payout_per_share": len(group_snapshots) - 1,
                "extra": {"neg_risk_market_id": rule.neg_risk_market_id},
            }
        )

    for clique in _mutual_exclusion_cliques(rule_set, by_market_id, max_leg_count=max_leg_count):
        group_snapshots = [by_market_id[market_id] for market_id in clique]
        specs.append(
            {
                "kind": "maker_hedge_mutual_exclusion_basket",
                "leg_specs": [(snapshot, "NO") for snapshot in group_snapshots],
                "payout_per_share": len(group_snapshots) - 1,
            }
        )

    for rule in rule_set.exhaustive_groups:
        market_ids = _unique_market_ids(rule.market_ids)
        if len(market_ids) < 2 or len(market_ids) > max_leg_count:
            continue
        group_snapshots = [by_market_id.get(market_id) for market_id in market_ids]
        if any(snapshot is None for snapshot in group_snapshots):
            continue
        specs.append(
            {
                "kind": "maker_hedge_exhaustive_yes_basket",
                "leg_specs": [(snapshot, "YES") for snapshot in group_snapshots],
                "payout_per_share": 1.0,
            }
        )

    return specs


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


def _taker_buy_leg(snapshot: BinaryMarketSnapshot, token: str, quantity: Optional[float] = None) -> Optional[dict]:
    book = _token_book(snapshot, token)
    if not book.asks:
        return None
    if quantity is not None and quantity > 0 and insufficient_liquidity(book.asks, quantity):
        return None
    level = book.asks[0]
    price = level.price
    fee = taker_fee_per_share(snapshot.venue, price, snapshot.fee_rate)
    cost = price + fee
    if quantity is not None and quantity > 0:
        fill = take_levels(book.asks, quantity)
        total = 0.0
        remaining = quantity
        for ask_level in book.asks:
            if remaining <= 0:
                break
            used = min(remaining, ask_level.size)
            total += used * (ask_level.price + taker_fee_per_share(snapshot.venue, ask_level.price, snapshot.fee_rate))
            remaining -= used
        price = fill.average_price
        cost = total / quantity
    best_bid = book.bids[0].price if book.bids else 0.0
    return {
        "venue": snapshot.venue,
        "market_id": snapshot.market_id,
        "token": token,
        "token_id": book.token_id,
        "side": "buy",
        "best_bid": best_bid,
        "best_ask": book.asks[0].price,
        "average_price": price,
        "cost_per_share": cost,
        "taker_fee_per_share": cost - price,
        "fee_rate_assumption": snapshot.fee_rate,
        "top_size": book.asks[0].size,
        "spread": book.asks[0].price - best_bid,
    }


def _ordered_hedge_candidate_legs(maker_leg: dict, hedge_legs: List[dict], maker_leg_index: int) -> List[dict]:
    legs = []
    for hedge_leg in hedge_legs:
        index = int(hedge_leg.get("source_leg_index") or 0)
        leg = {key: value for key, value in hedge_leg.items() if key != "source_leg_index"}
        leg["execution_role"] = "hedge_taker"
        legs.append((index, leg))
    maker = dict(maker_leg)
    maker["execution_role"] = "maker_trigger"
    legs.append((maker_leg_index, maker))
    return [leg for _, leg in sorted(legs, key=lambda item: item[0])]


def _ordered_hybrid_candidate_legs(maker_legs: List[dict], hedge_legs: List[dict]) -> List[dict]:
    legs = []
    for maker_leg in maker_legs:
        index = int(maker_leg.get("source_leg_index") or 0)
        leg = {key: value for key, value in maker_leg.items() if key != "source_leg_index"}
        leg["execution_role"] = "maker_trigger"
        legs.append((index, leg))
    for hedge_leg in hedge_legs:
        index = int(hedge_leg.get("source_leg_index") or 0)
        leg = {key: value for key, value in hedge_leg.items() if key != "source_leg_index"}
        leg["execution_role"] = "hedge_taker"
        legs.append((index, leg))
    return [leg for _, leg in sorted(legs, key=lambda item: item[0])]


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


def _normalize_maker_leg_bounds(min_maker_legs: int, max_maker_legs: int) -> tuple:
    try:
        min_count = int(min_maker_legs)
        max_count = int(max_maker_legs)
    except (TypeError, ValueError) as exc:
        raise ValueError("maker leg bounds must be integers") from exc
    if min_count < 2:
        raise ValueError("min_maker_legs must be at least 2")
    if max_count < min_count:
        raise ValueError("max_maker_legs must be greater than or equal to min_maker_legs")
    return min_count, max_count


def _normalize_positive_int(value: int, name: str) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if normalized < 1:
        raise ValueError(f"{name} must be a positive integer")
    return normalized


def _normalize_fill_model(value: str) -> str:
    normalized = (value or "crossed_ask").strip().lower().replace("-", "_")
    if normalized in {"crossed_ask", "ask_cross", "strict"}:
        return "crossed_ask"
    if normalized in {"touch_bid", "bid_touch", "queue_touch"}:
        return "touch_bid"
    raise ValueError("fill_model must be crossed_ask or touch_bid")


def _token_book(snapshot: BinaryMarketSnapshot, token: str) -> OrderBook:
    if token == "YES":
        return snapshot.yes
    if token == "NO":
        return snapshot.no
    raise ValueError(f"unsupported token: {token}")


def _snapshot_has_valid_spreads(snapshot: BinaryMarketSnapshot) -> bool:
    return _book_has_valid_spread(snapshot.yes) and _book_has_valid_spread(snapshot.no)


def _book_has_valid_spread(book: OrderBook) -> bool:
    if not book.asks or not book.bids:
        return True
    return book.bids[0].price < book.asks[0].price


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


def _dedupe_hedge_candidates(rows: List[dict]) -> List[dict]:
    deduped = {}
    for row in rows:
        key = (
            row["kind"],
            row.get("maker_leg_index"),
            tuple((leg["venue"], leg["market_id"], leg["token"], leg["side"], leg.get("execution_role")) for leg in row["legs"]),
        )
        previous = deduped.get(key)
        if previous is None or row["maker_edge_per_share"] > previous["maker_edge_per_share"]:
            deduped[key] = row
    return list(deduped.values())


def _dedupe_hybrid_candidates(rows: List[dict]) -> List[dict]:
    deduped = {}
    for row in rows:
        key = (
            row["kind"],
            tuple(row.get("maker_leg_indices") or []),
            tuple((leg["venue"], leg["market_id"], leg["token"], leg["side"], leg.get("execution_role")) for leg in row["legs"]),
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


def _hedge_candidate_sort_key(row: dict) -> tuple:
    return (
        -float(row.get("expected_edge_at_cap") or 0.0),
        -float(row.get("maker_roi") or 0.0),
        -float(row.get("maker_edge_per_share") or 0.0),
        int(row.get("leg_count") or 0),
        ",".join(row.get("market_ids") or []),
        int(row.get("maker_leg_index") or 0),
    )


def _hybrid_candidate_sort_key(row: dict) -> tuple:
    return (
        -float(row.get("expected_edge_at_cap") or 0.0),
        -float(row.get("maker_roi") or 0.0),
        -float(row.get("maker_edge_per_share") or 0.0),
        int(row.get("maker_leg_count") or 0),
        int(row.get("leg_count") or 0),
        ",".join(row.get("market_ids") or []),
        ",".join(str(index) for index in row.get("maker_leg_indices") or []),
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


def _summary_by_hybrid_kind(rows: List[dict]) -> list:
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
                "min_maker_leg_count": None,
                "max_maker_leg_count": 0,
            },
        )
        maker_leg_count = int(row.get("maker_leg_count") or 0)
        item["candidate_count"] += 1
        item["max_maker_edge_per_share"] = max(item["max_maker_edge_per_share"], row["maker_edge_per_share"])
        item["max_maker_roi"] = max(item["max_maker_roi"], row["maker_roi"])
        item["max_expected_edge_at_cap"] = max(item["max_expected_edge_at_cap"], row.get("expected_edge_at_cap") or 0.0)
        item["min_maker_leg_count"] = (
            maker_leg_count
            if item["min_maker_leg_count"] is None
            else min(item["min_maker_leg_count"], maker_leg_count)
        )
        item["max_maker_leg_count"] = max(item["max_maker_leg_count"], maker_leg_count)
    return sorted(summary.values(), key=lambda row: (-row["max_expected_edge_at_cap"], row["kind"]))


def _summary_by_hedge_kind(rows: List[dict]) -> list:
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


def _simulate_hedge_candidate(candidate: dict, future_batches: List[List[BinaryMarketSnapshot]], min_edge: float) -> dict:
    maker_leg = dict(candidate.get("maker_leg") or {})
    maker_fill = None
    hedge_rows = []
    realized_cost = None
    realized_edge = None
    rejection_reason = "maker_not_filled"
    quantity = float(candidate.get("suggested_quantity") or 0.0)

    for batch in future_batches:
        by_market_id = {snapshot.market_id: snapshot for snapshot in batch}
        snapshot = by_market_id.get(str(maker_leg.get("market_id") or ""))
        if snapshot is None:
            continue
        observation = _leg_fill_observation(snapshot, maker_leg)
        if observation is None:
            continue
        maker_fill = {"leg_index": candidate.get("maker_leg_index"), **observation}
        hedge_rows = _hedge_rows_at_fill(candidate, batch, quantity)
        if not hedge_rows:
            rejection_reason = "missing_or_insufficient_hedge_liquidity"
            break
        hedge_cost = sum(float(row.get("cost_per_share") or 0.0) for row in hedge_rows)
        realized_cost = float(maker_leg.get("limit_price") or 0.0) + hedge_cost
        realized_edge = float(candidate.get("payout_per_share") or 0.0) - realized_cost
        rejection_reason = "hedge_edge_below_min_edge" if realized_edge <= min_edge else None
        break

    maker_filled = maker_fill is not None
    completed = bool(maker_filled and realized_edge is not None and realized_edge > min_edge)
    realized_edge_at_cap = realized_edge * quantity if completed and quantity > 0 else 0.0
    row = {
        "candidate_key": _hedge_candidate_identity(candidate),
        "kind": candidate.get("kind"),
        "start_ts": candidate.get("ts"),
        "maker_fill_ts": maker_fill.get("fill_ts") if maker_fill else None,
        "completed": completed,
        "maker_filled": maker_filled,
        "rejection_reason": rejection_reason,
        "maker_leg_index": candidate.get("maker_leg_index"),
        "leg_count": candidate.get("leg_count"),
        "payout_per_share": candidate.get("payout_per_share"),
        "expected_edge_per_share": candidate.get("maker_edge_per_share"),
        "expected_edge_at_cap": candidate.get("expected_edge_at_cap"),
        "realized_cost_per_share": realized_cost,
        "realized_edge_per_share": realized_edge,
        "realized_edge_at_cap": realized_edge_at_cap,
        "suggested_quantity": candidate.get("suggested_quantity"),
        "capital_used_at_cap": candidate.get("capital_used_at_cap"),
        "maker_capital_at_cap": candidate.get("maker_capital_at_cap"),
        "market_ids": candidate.get("market_ids"),
        "maker_leg": maker_leg,
        "hedge_legs": candidate.get("hedge_legs"),
        "realized_hedge_legs": hedge_rows,
        "maker_fill": maker_fill,
        "risk_flags": candidate.get("risk_flags"),
    }
    return row


def _simulate_hybrid_candidate(
    candidate: dict,
    future_batches: List[List[BinaryMarketSnapshot]],
    min_edge: float,
    fill_model: str,
) -> dict:
    open_maker_legs = {int(leg.get("source_leg_index") or 0): dict(leg) for leg in candidate.get("maker_legs") or []}
    maker_fills = []
    hedge_rows = []
    realized_cost = None
    realized_edge = None
    rejection_reason = "maker_not_filled"
    quantity = float(candidate.get("suggested_quantity") or 0.0)

    for batch in future_batches:
        by_market_id = {snapshot.market_id: snapshot for snapshot in batch}
        for index, leg in list(open_maker_legs.items()):
            snapshot = by_market_id.get(str(leg.get("market_id") or ""))
            if snapshot is None:
                continue
            observation = _maker_leg_fill_observation(snapshot, leg, fill_model)
            if observation is None:
                continue
            maker_fills.append({"leg_index": index, **observation})
            del open_maker_legs[index]
        if open_maker_legs:
            continue
        hedge_rows = _hedge_rows_at_fill(candidate, batch, quantity)
        if not hedge_rows:
            rejection_reason = "missing_or_insufficient_hedge_liquidity"
            break
        hedge_cost = sum(float(row.get("cost_per_share") or 0.0) for row in hedge_rows)
        maker_cost = sum(float(leg.get("limit_price") or 0.0) for leg in candidate.get("maker_legs") or [])
        realized_cost = maker_cost + hedge_cost
        realized_edge = float(candidate.get("payout_per_share") or 0.0) - realized_cost
        rejection_reason = "hedge_edge_below_min_edge" if realized_edge <= min_edge else None
        break

    maker_leg_count = int(candidate.get("maker_leg_count") or len(candidate.get("maker_legs") or []))
    filled_maker_count = len(maker_fills)
    maker_filled = filled_maker_count == maker_leg_count and maker_leg_count > 0
    partial_maker_fill = 0 < filled_maker_count < maker_leg_count
    completed = bool(maker_filled and realized_edge is not None and realized_edge > min_edge)
    realized_edge_at_cap = realized_edge * quantity if completed and quantity > 0 else 0.0
    filled_maker_cost = sum(float(fill.get("limit_price") or 0.0) for fill in maker_fills)
    filled_maker_capital_at_cap = filled_maker_cost * quantity if quantity > 0 else 0.0
    row = {
        "candidate_key": _hybrid_candidate_identity(candidate),
        "kind": candidate.get("kind"),
        "start_ts": candidate.get("ts"),
        "maker_fill_ts": maker_fills[-1]["fill_ts"] if maker_filled and maker_fills else None,
        "completed": completed,
        "maker_filled": maker_filled,
        "partial_maker_fill": partial_maker_fill,
        "rejection_reason": rejection_reason,
        "maker_leg_indices": candidate.get("maker_leg_indices"),
        "maker_leg_count": maker_leg_count,
        "filled_maker_leg_count": filled_maker_count,
        "hedge_leg_count": candidate.get("hedge_leg_count"),
        "leg_count": candidate.get("leg_count"),
        "payout_per_share": candidate.get("payout_per_share"),
        "expected_edge_per_share": candidate.get("maker_edge_per_share"),
        "expected_edge_at_cap": candidate.get("expected_edge_at_cap"),
        "realized_cost_per_share": realized_cost,
        "realized_edge_per_share": realized_edge,
        "realized_edge_at_cap": realized_edge_at_cap,
        "suggested_quantity": candidate.get("suggested_quantity"),
        "capital_used_at_cap": candidate.get("capital_used_at_cap"),
        "maker_capital_at_cap": candidate.get("maker_capital_at_cap"),
        "filled_maker_capital_at_cap": filled_maker_capital_at_cap,
        "market_ids": candidate.get("market_ids"),
        "maker_legs": candidate.get("maker_legs"),
        "hedge_legs": candidate.get("hedge_legs"),
        "realized_hedge_legs": hedge_rows,
        "maker_fills": maker_fills,
        "unfilled_maker_legs": [open_maker_legs[index] for index in sorted(open_maker_legs)],
        "risk_flags": candidate.get("risk_flags"),
        "fill_model": fill_model,
    }
    return row


def _simulate_hybrid_candidate_with_trade_tape(
    candidate: dict,
    trades: List[dict],
    future_batches: List[List[BinaryMarketSnapshot]],
    horizon_seconds: float,
    min_edge: float,
) -> dict:
    start_dt = _parse_ts(candidate.get("ts"))
    deadline_dt = None
    if start_dt is not None and horizon_seconds > 0:
        deadline_dt = start_dt.timestamp() + horizon_seconds

    maker_fills = []
    for index, maker_leg in enumerate(candidate.get("maker_legs") or []):
        fill = _trade_tape_fill_for_leg(maker_leg, trades, start_dt, deadline_dt)
        if fill is not None:
            maker_fills.append({"leg_index": int(maker_leg.get("source_leg_index", index)), **fill})

    maker_leg_count = int(candidate.get("maker_leg_count") or len(candidate.get("maker_legs") or []))
    filled_maker_count = len(maker_fills)
    maker_filled = filled_maker_count == maker_leg_count and maker_leg_count > 0
    partial_maker_fill = 0 < filled_maker_count < maker_leg_count
    hedge_rows = []
    realized_cost = None
    realized_edge = None
    rejection_reason = "maker_not_filled"
    quantity = float(candidate.get("suggested_quantity") or 0.0)
    maker_fill_ts = None

    if maker_filled:
        maker_fills.sort(key=lambda row: row.get("fill_ts") or "")
        maker_fill_ts = maker_fills[-1].get("fill_ts")
        trade_quantity = min((float(fill.get("trade_size") or 0.0) for fill in maker_fills), default=0.0)
        if trade_quantity > 0 and quantity > 0:
            quantity = min(quantity, trade_quantity)
        hedge_batch = _first_batch_at_or_after(future_batches, maker_fill_ts)
        if hedge_batch is None:
            rejection_reason = "missing_hedge_snapshot_after_tape_fill"
        else:
            hedge_rows = _hedge_rows_at_fill(candidate, hedge_batch, quantity)
            if not hedge_rows:
                rejection_reason = "missing_or_insufficient_hedge_liquidity"
            else:
                hedge_cost = sum(float(row.get("cost_per_share") or 0.0) for row in hedge_rows)
                maker_cost = sum(float(leg.get("limit_price") or 0.0) for leg in candidate.get("maker_legs") or [])
                realized_cost = maker_cost + hedge_cost
                realized_edge = float(candidate.get("payout_per_share") or 0.0) - realized_cost
                rejection_reason = "hedge_edge_below_min_edge" if realized_edge <= min_edge else None

    completed = bool(maker_filled and realized_edge is not None and realized_edge > min_edge and quantity > 0)
    realized_edge_at_cap = realized_edge * quantity if completed else 0.0
    unfilled_indices = set(candidate.get("maker_leg_indices") or [])
    unfilled_indices.difference_update(int(fill.get("leg_index") or 0) for fill in maker_fills)
    row = {
        "candidate_key": _hybrid_candidate_identity(candidate),
        "kind": candidate.get("kind"),
        "start_ts": candidate.get("ts"),
        "maker_fill_ts": maker_fill_ts,
        "completed": completed,
        "maker_filled": maker_filled,
        "partial_maker_fill": partial_maker_fill,
        "rejection_reason": rejection_reason,
        "maker_leg_indices": candidate.get("maker_leg_indices"),
        "maker_leg_count": maker_leg_count,
        "filled_maker_leg_count": filled_maker_count,
        "hedge_leg_count": candidate.get("hedge_leg_count"),
        "leg_count": candidate.get("leg_count"),
        "payout_per_share": candidate.get("payout_per_share"),
        "expected_edge_per_share": candidate.get("maker_edge_per_share"),
        "expected_edge_at_cap": candidate.get("expected_edge_at_cap"),
        "realized_cost_per_share": realized_cost,
        "realized_edge_per_share": realized_edge,
        "realized_edge_at_cap": realized_edge_at_cap,
        "suggested_quantity": candidate.get("suggested_quantity"),
        "simulated_quantity": quantity,
        "capital_used_at_cap": (realized_cost * quantity) if completed and realized_cost is not None else 0.0,
        "maker_capital_at_cap": (sum(float(leg.get("limit_price") or 0.0) for leg in candidate.get("maker_legs") or []) * quantity)
        if maker_filled
        else 0.0,
        "market_ids": candidate.get("market_ids"),
        "maker_legs": candidate.get("maker_legs"),
        "hedge_legs": candidate.get("hedge_legs"),
        "realized_hedge_legs": hedge_rows,
        "maker_fills": maker_fills,
        "unfilled_maker_indices": sorted(unfilled_indices),
        "risk_flags": list(candidate.get("risk_flags") or []) + ["trade_tape_queue_position_uncertain"],
        "fill_model": "trade_tape_sell_through",
        "diagnostic_only": True,
    }
    return row


def _hedge_rows_at_fill(candidate: dict, batch: List[BinaryMarketSnapshot], quantity: float) -> List[dict]:
    by_market_id = {snapshot.market_id: snapshot for snapshot in batch}
    rows = []
    for leg in candidate.get("hedge_legs") or []:
        snapshot = by_market_id.get(str(leg.get("market_id") or ""))
        if snapshot is None:
            return []
        row = _taker_buy_leg(snapshot, str(leg.get("token") or ""), quantity=quantity if quantity > 0 else None)
        if row is None:
            return []
        rows.append(row)
    return rows


def _first_batch_at_or_after(batches: List[List[BinaryMarketSnapshot]], ts: Optional[str]) -> Optional[List[BinaryMarketSnapshot]]:
    if not batches:
        return None
    target_dt = _parse_ts(ts)
    if target_dt is None:
        return batches[0]
    for batch in batches:
        batch_dt = _parse_ts(_batch_ts(batch))
        if batch_dt is None or batch_dt >= target_dt:
            return batch
    return None


def _trade_tape_fill_for_leg(
    maker_leg: dict,
    trades: List[dict],
    start_dt,
    deadline_ts: Optional[float],
) -> Optional[dict]:
    token_id = str(maker_leg.get("token_id") or "").strip()
    limit_price = float(maker_leg.get("limit_price") or 0.0)
    for trade in trades:
        if str(trade.get("asset_id") or "").strip() != token_id:
            continue
        if str(trade.get("side") or "").upper() != "SELL":
            continue
        trade_dt = _parse_ts(trade.get("trade_ts"))
        if start_dt is not None and trade_dt is not None and trade_dt <= start_dt:
            continue
        if deadline_ts is not None and trade_dt is not None and trade_dt.timestamp() > deadline_ts:
            continue
        price = float(trade.get("price") or 0.0)
        if price > limit_price:
            continue
        return {
            "fill_ts": trade.get("trade_ts"),
            "market_id": maker_leg.get("market_id"),
            "token": maker_leg.get("token"),
            "token_id": token_id,
            "limit_price": limit_price,
            "trade_price": price,
            "trade_size": float(trade.get("size") or 0.0),
            "trade_side": trade.get("side"),
            "transaction_hash": trade.get("transaction_hash"),
            "fill_model": "trade_tape_sell_through",
            "diagnostic_only": True,
        }
    return None


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


def _maker_leg_fill_observation(snapshot: BinaryMarketSnapshot, leg: dict, fill_model: str) -> Optional[dict]:
    crossed = _leg_fill_observation(snapshot, leg)
    if crossed is not None:
        crossed["fill_model"] = "crossed_ask"
        return crossed
    if fill_model != "touch_bid":
        return None
    token = str(leg.get("token") or "")
    book = _token_book(snapshot, token)
    if not book.bids:
        return None
    best_bid = book.bids[0].price
    limit_price = float(leg.get("limit_price") or 0.0)
    if best_bid < limit_price:
        return None
    return {
        "fill_ts": snapshot.ts,
        "market_id": snapshot.market_id,
        "token": token,
        "limit_price": limit_price,
        "observed_best_bid": best_bid,
        "fill_model": "touch_bid",
        "diagnostic_only": True,
    }


def _trade_tape_rows_from_path(path: Path) -> List[dict]:
    rows = []
    if not path.exists():
        return rows
    with path.open() as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            normalized = _normalize_trade_tape_row(row)
            if normalized is not None:
                rows.append(normalized)
    return rows


def _normalize_trade_tape_row(row: dict) -> Optional[dict]:
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else row
    asset_id = str(row.get("asset_id") or raw.get("asset") or raw.get("asset_id") or "").strip()
    if not asset_id:
        return None
    price = _float_or_none(row.get("price") if row.get("price") is not None else raw.get("price"))
    if price is None:
        return None
    size = _float_or_none(row.get("size") if row.get("size") is not None else raw.get("size")) or 0.0
    trade_ts = row.get("trade_ts") or _trade_timestamp_to_iso(raw.get("timestamp")) or row.get("ts")
    return {
        "market_id": row.get("market_id") or raw.get("market") or raw.get("conditionId"),
        "condition_id": row.get("condition_id") or raw.get("conditionId"),
        "asset_id": asset_id,
        "side": str(row.get("side") or raw.get("side") or "").upper(),
        "price": price,
        "size": size,
        "trade_ts": trade_ts,
        "transaction_hash": row.get("transaction_hash") or raw.get("transactionHash"),
    }


def _float_or_none(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _trade_timestamp_to_iso(value) -> Optional[str]:
    if value is None or value == "":
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError, OSError):
        return str(value)


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


def _hedge_fill_summary_by_kind(rows: List[dict]) -> list:
    summary = {}
    for row in rows:
        item = summary.setdefault(
            row.get("kind") or "unknown",
            {
                "kind": row.get("kind") or "unknown",
                "candidate_observation_count": 0,
                "completed_count": 0,
                "unsafe_fill_count": 0,
                "no_fill_count": 0,
                "max_completed_realized_edge_at_cap": 0.0,
            },
        )
        item["candidate_observation_count"] += 1
        if row.get("completed"):
            item["completed_count"] += 1
            item["max_completed_realized_edge_at_cap"] = max(
                item["max_completed_realized_edge_at_cap"],
                float(row.get("realized_edge_at_cap") or 0.0),
            )
        elif row.get("maker_filled"):
            item["unsafe_fill_count"] += 1
        else:
            item["no_fill_count"] += 1
    for item in summary.values():
        count = item["candidate_observation_count"]
        item["completion_rate"] = item["completed_count"] / count if count else 0.0
        item["unsafe_fill_rate"] = item["unsafe_fill_count"] / count if count else 0.0
    return sorted(summary.values(), key=lambda row: (-row["completed_count"], -row["max_completed_realized_edge_at_cap"], row["kind"]))


def _hybrid_fill_summary_by_kind(rows: List[dict]) -> list:
    summary = {}
    for row in rows:
        item = summary.setdefault(
            row.get("kind") or "unknown",
            {
                "kind": row.get("kind") or "unknown",
                "candidate_observation_count": 0,
                "completed_count": 0,
                "unsafe_fill_count": 0,
                "partial_maker_fill_count": 0,
                "no_fill_count": 0,
                "max_completed_realized_edge_at_cap": 0.0,
            },
        )
        item["candidate_observation_count"] += 1
        if row.get("completed"):
            item["completed_count"] += 1
            item["max_completed_realized_edge_at_cap"] = max(
                item["max_completed_realized_edge_at_cap"],
                float(row.get("realized_edge_at_cap") or 0.0),
            )
        elif row.get("maker_filled"):
            item["unsafe_fill_count"] += 1
        elif row.get("partial_maker_fill"):
            item["partial_maker_fill_count"] += 1
        else:
            item["no_fill_count"] += 1
    for item in summary.values():
        count = item["candidate_observation_count"]
        item["completion_rate"] = item["completed_count"] / count if count else 0.0
        item["unsafe_fill_rate"] = item["unsafe_fill_count"] / count if count else 0.0
        item["partial_maker_fill_rate"] = item["partial_maker_fill_count"] / count if count else 0.0
    return sorted(summary.values(), key=lambda row: (-row["completed_count"], -row["max_completed_realized_edge_at_cap"], row["kind"]))


def _hybrid_rejection_summary(rows: List[dict]) -> list:
    summary = {}
    for row in rows:
        reason = str(row.get("rejection_reason") or ("completed" if row.get("completed") else "unknown"))
        item = summary.setdefault(
            reason,
            {
                "reason": reason,
                "candidate_observation_count": 0,
                "completed_count": 0,
                "max_expected_edge_at_cap": 0.0,
                "max_expected_edge_per_share": 0.0,
                "max_realized_edge_at_cap": 0.0,
            },
        )
        item["candidate_observation_count"] += 1
        if row.get("completed"):
            item["completed_count"] += 1
        item["max_expected_edge_at_cap"] = max(
            item["max_expected_edge_at_cap"],
            float(row.get("expected_edge_at_cap") or 0.0),
        )
        item["max_expected_edge_per_share"] = max(
            item["max_expected_edge_per_share"],
            float(row.get("expected_edge_per_share") or 0.0),
        )
        item["max_realized_edge_at_cap"] = max(
            item["max_realized_edge_at_cap"],
            float(row.get("realized_edge_at_cap") or 0.0),
        )
    return sorted(
        summary.values(),
        key=lambda row: (
            -row["candidate_observation_count"],
            -row["max_expected_edge_at_cap"],
            row["reason"],
        ),
    )


def _maker_fill_progress_distribution(rows: List[dict]) -> list:
    counts = Counter(
        (
            int(row.get("filled_maker_leg_count") or 0),
            int(row.get("maker_leg_count") or 0),
        )
        for row in rows
    )
    distribution = []
    for (filled_count, maker_count), count in counts.items():
        distribution.append(
            {
                "filled_maker_leg_count": filled_count,
                "maker_leg_count": maker_count,
                "candidate_observation_count": count,
                "maker_leg_fill_ratio": filled_count / maker_count if maker_count else 0.0,
            }
        )
    return sorted(
        distribution,
        key=lambda row: (
            row["filled_maker_leg_count"],
            row["maker_leg_count"],
            -row["candidate_observation_count"],
        ),
    )


def _top_unfilled_maker_legs(rows: List[dict], top_n: int) -> list:
    if top_n <= 0:
        return []
    summary = {}
    for row in rows:
        unfilled_indices = set(int(index) for index in (row.get("unfilled_maker_indices") or []))
        for index, leg in enumerate(row.get("maker_legs") or []):
            source_index = _source_leg_index(leg, index)
            key = (
                str(leg.get("venue") or ""),
                str(leg.get("market_id") or ""),
                str(leg.get("token") or ""),
                str(leg.get("token_id") or ""),
                str(leg.get("side") or ""),
                float(leg.get("limit_price") or 0.0),
                str(leg.get("quote_mode") or ""),
                int(leg.get("quote_offset_ticks") or 0),
            )
            item = summary.setdefault(
                key,
                {
                    "venue": key[0],
                    "market_id": key[1],
                    "token": key[2],
                    "token_id": key[3],
                    "side": key[4],
                    "limit_price": key[5],
                    "quote_mode": key[6],
                    "quote_offset_ticks": key[7],
                    "best_bid": _float_or_none(leg.get("best_bid")),
                    "best_ask": _float_or_none(leg.get("best_ask")),
                    "spread": _float_or_none(leg.get("spread")),
                    "candidate_observation_count": 0,
                    "unfilled_count": 0,
                    "max_expected_edge_at_cap": 0.0,
                    "max_expected_edge_per_share": 0.0,
                    "min_distance_to_best_ask": None,
                    "max_improvement_over_best_bid": 0.0,
                },
            )
            item["candidate_observation_count"] += 1
            item["max_expected_edge_at_cap"] = max(
                item["max_expected_edge_at_cap"],
                float(row.get("expected_edge_at_cap") or 0.0),
            )
            item["max_expected_edge_per_share"] = max(
                item["max_expected_edge_per_share"],
                float(row.get("expected_edge_per_share") or 0.0),
            )
            distance = _leg_distance_to_best_ask(leg)
            if distance is not None:
                item["min_distance_to_best_ask"] = (
                    distance
                    if item["min_distance_to_best_ask"] is None
                    else min(item["min_distance_to_best_ask"], distance)
                )
            improvement = _leg_improvement_over_best_bid(leg)
            if improvement is not None:
                item["max_improvement_over_best_bid"] = max(item["max_improvement_over_best_bid"], improvement)
            if source_index in unfilled_indices:
                item["unfilled_count"] += 1

    rows = []
    for item in summary.values():
        if item["unfilled_count"] <= 0:
            continue
        count = item["candidate_observation_count"]
        item["unfilled_rate"] = item["unfilled_count"] / count if count else 0.0
        rows.append(item)
    return sorted(
        rows,
        key=lambda row: (
            -row["unfilled_count"],
            -row["unfilled_rate"],
            -row["max_expected_edge_at_cap"],
            row["market_id"],
            row["token"],
        ),
    )[:top_n]


def _source_leg_index(leg: dict, default: int) -> int:
    try:
        return int(leg.get("source_leg_index", default))
    except (TypeError, ValueError):
        return default


def _leg_distance_to_best_ask(leg: dict) -> Optional[float]:
    distance = _float_or_none(leg.get("distance_to_best_ask"))
    if distance is not None:
        return distance
    best_ask = _float_or_none(leg.get("best_ask"))
    limit_price = _float_or_none(leg.get("limit_price"))
    if best_ask is None or limit_price is None:
        return None
    return best_ask - limit_price


def _leg_improvement_over_best_bid(leg: dict) -> Optional[float]:
    improvement = _float_or_none(leg.get("improvement_over_best_bid"))
    if improvement is not None:
        return improvement
    best_bid = _float_or_none(leg.get("best_bid"))
    limit_price = _float_or_none(leg.get("limit_price"))
    if best_bid is None or limit_price is None:
        return None
    return max(0.0, limit_price - best_bid)


def _unique_tape_completed_rows(rows: List[dict]) -> List[dict]:
    deduped = {}
    for row in rows:
        key = _tape_completed_identity(row)
        previous = deduped.get(key)
        if previous is None or _hybrid_result_sort_key(row) < _hybrid_result_sort_key(previous):
            deduped[key] = row
    return list(deduped.values())


def _tape_completed_identity(row: dict) -> tuple:
    fill_keys = []
    for fill in row.get("maker_fills") or []:
        fill_keys.append(
            (
                str(fill.get("token_id") or ""),
                str(fill.get("transaction_hash") or ""),
                str(fill.get("fill_ts") or ""),
                float(fill.get("trade_price") or 0.0),
                float(fill.get("trade_size") or 0.0),
            )
        )
    return (
        row.get("kind"),
        tuple(row.get("maker_leg_indices") or []),
        tuple(sorted(fill_keys)),
        round(float(row.get("realized_edge_per_share") or 0.0), 9),
    )


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


def _hedge_result_sort_key(row: dict) -> tuple:
    return (
        not bool(row.get("completed")),
        -float(row.get("realized_edge_at_cap") or row.get("expected_edge_at_cap") or 0.0),
        str(row.get("candidate_key") or ""),
    )


def _hybrid_result_sort_key(row: dict) -> tuple:
    return (
        not bool(row.get("completed")),
        -float(row.get("realized_edge_at_cap") or row.get("expected_edge_at_cap") or 0.0),
        -int(row.get("filled_maker_leg_count") or 0),
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


def _hedge_candidate_identity(candidate: dict) -> str:
    legs = "|".join(
        sorted(
            f"{leg.get('venue')}:{leg.get('market_id')}:{leg.get('token')}:{leg.get('side')}:{leg.get('execution_role')}@{leg.get('limit_price') or leg.get('cost_per_share')}"
            for leg in candidate.get("legs", [])
        )
    )
    return f"{candidate.get('kind')}:maker_index={candidate.get('maker_leg_index')}:{legs}"


def _hybrid_candidate_identity(candidate: dict) -> str:
    legs = "|".join(
        sorted(
            f"{leg.get('venue')}:{leg.get('market_id')}:{leg.get('token')}:{leg.get('side')}:{leg.get('execution_role')}@{leg.get('limit_price') or leg.get('cost_per_share')}"
            for leg in candidate.get("legs", [])
        )
    )
    maker_indices = ",".join(str(index) for index in candidate.get("maker_leg_indices") or [])
    return f"{candidate.get('kind')}:maker_indices={maker_indices}:{legs}"


def _batch_ts(batch: List[BinaryMarketSnapshot]) -> Optional[str]:
    return batch[0].ts if batch else None


def _parse_ts(value: Optional[str]):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
