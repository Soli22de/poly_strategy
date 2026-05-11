import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from poly_strategy.near_miss import near_miss_report


def analyze_paper_monitor_report(
    path: Path,
    top_n: int = 10,
    snapshots_path: Optional[Path] = None,
    rules_path: Optional[Path] = None,
    gamma_path: Optional[Path] = None,
    near_miss_top_n: int = 10,
    near_miss_min_net_edge: float = 0.0,
) -> dict:
    if top_n < 0:
        raise ValueError("top_n must be non-negative")
    if near_miss_top_n < 0:
        raise ValueError("near_miss_top_n must be non-negative")

    rows = list(_read_jsonl(path))
    monitor_kind = _monitor_kind(rows)
    iteration_rows = [row for row in rows if row.get("type") in {"paper_monitor_iteration", "realtime_monitor_iteration"}]
    error_rows = [row for row in rows if row.get("type") in {"paper_monitor_iteration_error", "realtime_monitor_iteration_error"}]
    summary_rows = [row for row in rows if row.get("type") in {"paper_monitor_summary", "realtime_monitor_summary"}]
    connection_rows = [row for row in rows if row.get("type") == "realtime_monitor_connection_event"]

    timestamps = [_parse_ts(row.get("ts")) for row in rows if row.get("ts")]
    timestamps = [timestamp for timestamp in timestamps if timestamp is not None]
    started_at = min(timestamps).isoformat().replace("+00:00", "Z") if timestamps else None
    ended_at = max(timestamps).isoformat().replace("+00:00", "Z") if timestamps else None
    duration_seconds = (max(timestamps) - min(timestamps)).total_seconds() if len(timestamps) >= 2 else 0.0

    current_edges = _opportunity_values(iteration_rows, "current_opportunities", "net_edge_per_share")
    stable_edges = _opportunity_values(iteration_rows, "stable_opportunities", "net_edge_per_share")
    stable_trade_rois = _opportunity_values(iteration_rows, "stable_paper_trades", "paper_roi")
    latest_summary = summary_rows[-1] if summary_rows else {}
    attempted_iterations = len(iteration_rows) + len(error_rows)
    stable_paper_capital_used = sum(float(row.get("stable_paper_capital_used") or 0.0) for row in iteration_rows)
    stable_paper_edge = sum(float(row.get("stable_paper_edge") or 0.0) for row in iteration_rows)

    report = {
        "type": "monitor_analysis",
        "monitor_kind": monitor_kind,
        "report_path": str(path),
        "row_count": len(rows),
        "iteration_count": len(iteration_rows),
        "error_iteration_count": len(error_rows),
        "error_rate": len(error_rows) / attempted_iterations if attempted_iterations else 0.0,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_seconds": duration_seconds,
        "snapshots_collected": sum(int(row.get("snapshots_collected") or 0) for row in iteration_rows + error_rows),
        "final_snapshot_count": _latest_numeric(iteration_rows, latest_summary, "snapshot_count"),
        "final_messages_seen": _latest_numeric(iteration_rows, latest_summary, "messages_seen"),
        "final_known_token_count": _latest_numeric(iteration_rows, latest_summary, "known_token_count"),
        "current_opportunity_observations": sum(int(row.get("current_opportunity_count") or 0) for row in iteration_rows),
        "stable_opportunity_observations": sum(int(row.get("stable_opportunity_count") or 0) for row in iteration_rows),
        "stable_paper_trade_observations": sum(int(row.get("stable_paper_trade_count") or 0) for row in iteration_rows),
        "zero_current_opportunity_iterations": _zero_count(iteration_rows, "current_opportunity_count"),
        "zero_stable_opportunity_iterations": _zero_count(iteration_rows, "stable_opportunity_count"),
        "latest_zero_current_opportunity_streak": _latest_zero_streak(iteration_rows, "current_opportunity_count"),
        "latest_zero_stable_opportunity_streak": _latest_zero_streak(iteration_rows, "stable_opportunity_count"),
        "stable_paper_capital_used": stable_paper_capital_used,
        "stable_paper_edge": stable_paper_edge,
        "stable_paper_roi": stable_paper_edge / stable_paper_capital_used if stable_paper_capital_used > 0 else 0.0,
        "current_edge": _distribution(current_edges),
        "stable_edge": _distribution(stable_edges),
        "stable_paper_roi_distribution": _distribution(stable_trade_rois),
        "current_opportunity_by_kind": _opportunity_kind_summary(iteration_rows, "current_opportunities"),
        "stable_opportunity_by_kind": _opportunity_kind_summary(iteration_rows, "stable_opportunities"),
        "last_message_age_seconds": _distribution(_numeric_values(iteration_rows, "last_message_age_seconds")),
        "messages_per_iteration": _distribution(_counter_deltas(iteration_rows, "messages_seen")),
        "connection_events": _connection_event_summary(connection_rows),
        "top_current_opportunities": _top_opportunities(iteration_rows, "current_opportunities", top_n),
        "top_stable_opportunities": _top_opportunities(iteration_rows, "stable_opportunities", top_n),
        "top_stable_markets": _top_markets(iteration_rows, "stable_opportunities", top_n),
        "error_summary": _error_summary(error_rows, iteration_rows),
        "latest_summary": latest_summary,
    }
    if snapshots_path:
        near_miss = near_miss_report(
            snapshots_path,
            rules_path=rules_path,
            gamma_path=gamma_path,
            top_n=near_miss_top_n,
            min_net_edge=near_miss_min_net_edge,
        )
        report["near_miss"] = near_miss
        report["near_miss_rejection_summary"] = _near_miss_rejection_summary(near_miss)
        report["zero_opportunity_diagnosis"] = _zero_opportunity_diagnosis(report, near_miss)
        report["opportunity_chain"] = _opportunity_chain_report(report, near_miss)
        report["strategy_chain_breakdown"] = _strategy_chain_breakdown(near_miss)
    else:
        report["opportunity_chain"] = _opportunity_chain_report(report)
    return report


def analyze_monitor_report(*args, **kwargs) -> dict:
    return analyze_paper_monitor_report(*args, **kwargs)


def _read_jsonl(path: Path) -> Iterable[dict]:
    with path.open() as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            yield json.loads(line)


def _latest_numeric(iteration_rows: list, latest_summary: dict, key: str) -> float:
    if key in latest_summary:
        return latest_summary[key]
    for row in reversed(iteration_rows):
        if key in row:
            return row[key]
    return 0


def _monitor_kind(rows: list) -> str:
    types = {row.get("type") for row in rows}
    if "realtime_monitor_iteration" in types or "realtime_monitor_summary" in types:
        return "realtime"
    if "paper_monitor_iteration" in types or "paper_monitor_summary" in types:
        return "paper"
    return "unknown"


def _opportunity_values(rows: list, field: str, key: str) -> list:
    values = []
    for row in rows:
        for opportunity in row.get(field, []):
            value = opportunity.get(key)
            if value is not None:
                values.append(float(value))
    return values


def _distribution(values: list) -> dict:
    if not values:
        return {
            "count": 0,
            "min": 0.0,
            "p25": 0.0,
            "p50": 0.0,
            "p75": 0.0,
            "p95": 0.0,
            "max": 0.0,
            "mean": 0.0,
        }
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "min": ordered[0],
        "p25": _percentile(ordered, 0.25),
        "p50": _percentile(ordered, 0.50),
        "p75": _percentile(ordered, 0.75),
        "p95": _percentile(ordered, 0.95),
        "max": ordered[-1],
        "mean": sum(ordered) / len(ordered),
    }


def _numeric_values(rows: list, key: str) -> list:
    values = []
    for row in rows:
        value = row.get(key)
        if value is None:
            continue
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue
    return values


def _counter_deltas(rows: list, key: str) -> list:
    values = _numeric_values(rows, key)
    if len(values) < 2:
        return []
    deltas = []
    previous = values[0]
    for value in values[1:]:
        if value >= previous:
            deltas.append(value - previous)
        previous = value
    return deltas


def _percentile(ordered: list, q: float) -> float:
    if len(ordered) == 1:
        return ordered[0]
    index = q * (len(ordered) - 1)
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _top_opportunities(rows: list, field: str, top_n: int) -> list:
    stats = {}
    for row in rows:
        for opportunity in row.get(field, []):
            key = opportunity.get("key") or json.dumps(opportunity.get("legs", []), sort_keys=True)
            record = stats.setdefault(
                key,
                {
                    "key": key,
                    "kind": opportunity.get("kind"),
                    "count": 0,
                    "max_edge_per_share": 0.0,
                    "max_total_edge": 0.0,
                    "markets": sorted(_market_ids(opportunity)),
                },
            )
            record["count"] += 1
            record["max_edge_per_share"] = max(
                record["max_edge_per_share"],
                float(opportunity.get("net_edge_per_share") or 0.0),
            )
            record["max_total_edge"] = max(record["max_total_edge"], float(opportunity.get("total_edge") or 0.0))
            record["markets"] = sorted(set(record["markets"]) | _market_ids(opportunity))
    return sorted(
        stats.values(),
        key=lambda row: (-row["count"], -row["max_edge_per_share"], row["key"]),
    )[:top_n]


def _top_markets(rows: list, field: str, top_n: int) -> list:
    counts = Counter()
    max_edge_by_market = {}
    for row in rows:
        for opportunity in row.get(field, []):
            edge = float(opportunity.get("net_edge_per_share") or 0.0)
            for market_id in _market_ids(opportunity):
                counts[market_id] += 1
                max_edge_by_market[market_id] = max(max_edge_by_market.get(market_id, 0.0), edge)
    return [
        {
            "market_id": market_id,
            "count": count,
            "max_edge_per_share": max_edge_by_market.get(market_id, 0.0),
        }
        for market_id, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:top_n]
    ]


def _opportunity_kind_summary(rows: list, field: str) -> list:
    counts = Counter()
    max_edge_by_kind = {}
    max_total_edge_by_kind = {}
    for row in rows:
        for opportunity in row.get(field, []):
            kind = str(opportunity.get("kind") or "unknown")
            counts[kind] += 1
            max_edge_by_kind[kind] = max(
                max_edge_by_kind.get(kind, 0.0),
                float(opportunity.get("net_edge_per_share") or 0.0),
            )
            max_total_edge_by_kind[kind] = max(
                max_total_edge_by_kind.get(kind, 0.0),
                float(opportunity.get("total_edge") or 0.0),
            )
    return [
        {
            "kind": kind,
            "count": count,
            "max_edge_per_share": max_edge_by_kind.get(kind, 0.0),
            "max_total_edge": max_total_edge_by_kind.get(kind, 0.0),
        }
        for kind, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _zero_count(rows: list, key: str) -> int:
    return sum(1 for row in rows if int(row.get(key) or 0) == 0)


def _latest_zero_streak(rows: list, key: str) -> int:
    count = 0
    for row in reversed(rows):
        if int(row.get(key) or 0) != 0:
            break
        count += 1
    return count


def _near_miss_rejection_summary(near_miss: dict) -> dict:
    rows = near_miss.get("neg_risk_expanded_groups", [])
    statuses = Counter(str(row.get("status") or "unknown") for row in rows)
    trade_statuses = Counter(str(row.get("trade_status") or "unknown") for row in rows)
    rejection_reasons = Counter(str(row.get("rejection_reason") or "none") for row in rows)
    return {
        "neg_risk_group_count": len(rows),
        "by_status": _counter_rows(statuses, "status"),
        "by_trade_status": _counter_rows(trade_statuses, "trade_status"),
        "by_rejection_reason": _counter_rows(rejection_reasons, "rejection_reason"),
        "missing_snapshot_market_count": sum(len(row.get("missing_snapshot_market_ids") or []) for row in rows),
        "extra_known_market_count": sum(len(row.get("extra_known_market_ids") or []) for row in rows),
    }


def _market_ids(opportunity: dict) -> set:
    return {str(leg.get("market_id")) for leg in opportunity.get("legs", []) if leg.get("market_id")}


def _error_summary(error_rows: list, iteration_rows: list) -> dict:
    error_types = Counter(str(row.get("error_type") or "unknown") for row in error_rows)
    phases = Counter(str(row.get("phase") or "unknown") for row in error_rows)
    collection_error_kinds = Counter()
    for row in iteration_rows + error_rows:
        for error in row.get("errors", []):
            collection_error_kinds[str(error.get("kind") or "unknown")] += 1
    return {
        "by_error_type": _counter_rows(error_types, "error_type"),
        "by_phase": _counter_rows(phases, "phase"),
        "collection_error_kinds": _counter_rows(collection_error_kinds, "kind"),
        "collection_error_count": sum(int(row.get("error_count") or 0) for row in iteration_rows + error_rows),
    }


def _connection_event_summary(connection_rows: list) -> dict:
    by_event = Counter(str(row.get("event") or "unknown") for row in connection_rows)
    error_types = Counter(str(row.get("error_type") or "unknown") for row in connection_rows if row.get("error_type"))
    latest = connection_rows[-1] if connection_rows else None
    return {
        "event_count": len(connection_rows),
        "by_event": _counter_rows(by_event, "event"),
        "by_error_type": _counter_rows(error_types, "error_type"),
        "latest_event": latest,
    }


def _zero_opportunity_diagnosis(report: dict, near_miss: dict) -> dict:
    top = near_miss.get("top", [])
    top_actionable = near_miss.get("top_actionable", [])
    diagnostic_top = near_miss.get("diagnostic_top", [])
    blocked_top = near_miss.get("blocked_top", [])
    by_kind = near_miss.get("by_kind", [])
    best = top[0] if top else None
    best_actionable = top_actionable[0] if top_actionable else None
    positive_gross = sum(int(row.get("positive_gross_count") or 0) for row in by_kind)
    positive_net = sum(int(row.get("positive_net_count") or 0) for row in by_kind)
    actionable_positive_net = sum(int(row.get("actionable_positive_net_count") or 0) for row in by_kind)
    fee_blocked = sum(int(row.get("fee_blocked_count") or 0) for row in by_kind)
    reasons = []
    if report.get("final_known_token_count", 0) and report.get("final_known_token_count", 0) < 100:
        reasons.append("watchlist_too_narrow")
    if not top:
        reasons.append("no_evaluable_candidates")
    elif float(best.get("net_edge_per_share") or 0.0) <= float(near_miss.get("min_net_edge") or 0.0):
        reasons.append("best_candidate_below_min_edge")
    if not best_actionable:
        reasons.append("no_actionable_near_miss_candidates")
    elif float(best_actionable.get("net_edge_per_share") or 0.0) <= float(near_miss.get("min_net_edge") or 0.0):
        reasons.append("best_actionable_candidate_below_min_edge")
    if fee_blocked:
        reasons.append("fees_erase_gross_edge")
    if positive_gross and not positive_net:
        reasons.append("fee_drag_dominates_positive_gross_edges")
    if positive_net and not actionable_positive_net:
        reasons.append("positive_net_candidates_require_verification_or_are_blocked")
    if diagnostic_top:
        reasons.append("diagnostic_candidates_require_rule_promotion")
    if blocked_top:
        reasons.append("some_candidates_blocked_by_resolution_or_group_checks")
    if report.get("connection_events", {}).get("by_event"):
        events = {row.get("event") for row in report["connection_events"]["by_event"]}
        if "disconnected" in events or "reconnect_sleep" in events:
            reasons.append("websocket_reconnects_reduce_continuity")
    return {
        "reasons": sorted(set(reasons)),
        "best_candidate": best,
        "best_actionable_candidate": best_actionable,
        "positive_gross_candidate_count": positive_gross,
        "positive_net_candidate_count": positive_net,
        "actionable_positive_net_candidate_count": actionable_positive_net,
        "fee_blocked_candidate_count": fee_blocked,
        "actionable_candidate_count": near_miss.get("actionable_candidate_count", 0),
        "diagnostic_candidate_count": near_miss.get("diagnostic_candidate_count", 0),
        "blocked_candidate_count": near_miss.get("blocked_candidate_count", 0),
        "closest_by_kind": by_kind[:10],
    }


def _opportunity_chain_report(report: dict, near_miss: Optional[dict] = None) -> dict:
    latest_snapshot_count = int((near_miss or {}).get("latest_snapshot_count") or report.get("final_snapshot_count") or 0)
    known_token_count = int(report.get("final_known_token_count") or 0)
    candidate_count = int((near_miss or {}).get("candidate_count") or 0)
    actionable_count = int((near_miss or {}).get("actionable_candidate_count") or 0)
    by_kind = (near_miss or {}).get("by_kind", [])
    actionable_positive_net_count = sum(int(row.get("actionable_positive_net_count") or 0) for row in by_kind)
    diagnostic_count = int((near_miss or {}).get("diagnostic_candidate_count") or 0)
    blocked_count = int((near_miss or {}).get("blocked_candidate_count") or 0)
    current_count = int(report.get("current_opportunity_observations") or 0)
    stable_count = int(report.get("stable_opportunity_observations") or 0)
    paper_count = int(report.get("stable_paper_trade_observations") or 0)

    stages = [
        _chain_stage(
            "feed",
            input_count=known_token_count,
            output_count=latest_snapshot_count,
            status="block" if latest_snapshot_count == 0 else "pass",
            reason="no_latest_snapshots" if latest_snapshot_count == 0 else "latest_snapshots_available",
            next_action="rebuild watchlist, verify collector/WebSocket connectivity, and seed orderbooks",
        ),
        _chain_stage(
            "candidate_generation",
            input_count=latest_snapshot_count,
            output_count=candidate_count,
            status="block" if latest_snapshot_count > 0 and candidate_count == 0 else ("not_evaluated" if not near_miss else "pass"),
            reason="no_evaluable_candidates" if latest_snapshot_count > 0 and candidate_count == 0 else "candidate_scan_completed",
            next_action="verify snapshots have paired YES/NO books and include rules/gamma metadata",
        ),
        _chain_stage(
            "actionability_filter",
            input_count=candidate_count,
            output_count=actionable_count,
            status=_actionability_stage_status(candidate_count, actionable_count, diagnostic_count, blocked_count),
            reason=_actionability_stage_reason(candidate_count, actionable_count, diagnostic_count, blocked_count),
            next_action="promote verified exhaustive groups, fix rejected rule wording, or expand missing market metadata",
            diagnostics={"diagnostic_candidate_count": diagnostic_count, "blocked_candidate_count": blocked_count},
        ),
        _chain_stage(
            "edge_filter",
            input_count=actionable_count,
            output_count=actionable_positive_net_count,
            status="block" if actionable_count > 0 and actionable_positive_net_count == 0 else ("not_evaluated" if not near_miss else "pass"),
            reason="no_actionable_candidate_clears_min_net_edge" if actionable_count > 0 and actionable_positive_net_count == 0 else "edge_filter_passed",
            next_action="rank near misses by distance_to_min_net_edge, then improve coverage, fee drag, or spread constraints",
            diagnostics=_edge_diagnostics(near_miss),
        ),
        _chain_stage(
            "stability_filter",
            input_count=current_count,
            output_count=stable_count,
            status=_stability_stage_status(current_count, stable_count, actionable_positive_net_count),
            reason=_stability_stage_reason(current_count, stable_count, actionable_positive_net_count),
            next_action="increase scan cadence, reduce reconnects/staleness, or run diagnostic-only lower stability thresholds",
        ),
        _chain_stage(
            "paper_filter",
            input_count=stable_count,
            output_count=paper_count,
            status=_paper_stage_status(stable_count, paper_count),
            reason=_paper_stage_reason(stable_count, paper_count),
            next_action="inspect paper rejection filters: ROI, quantity, bankroll, capital cap, and liquidity",
            diagnostics={
                "stable_paper_capital_used": report.get("stable_paper_capital_used", 0.0),
                "stable_paper_edge": report.get("stable_paper_edge", 0.0),
                "stable_paper_roi": report.get("stable_paper_roi", 0.0),
            },
        ),
    ]
    blocking = _first_stage_with_status(stages, "block")
    warning = _first_stage_with_status(stages, "warn")
    return {
        "type": "opportunity_chain_report",
        "blocking_stage": blocking.get("stage") if blocking else None,
        "first_warning_stage": warning.get("stage") if warning else None,
        "status": "blocked" if blocking else ("warning" if warning else "pass"),
        "stages": stages,
        "recommended_actions": _chain_recommended_actions(stages),
    }


def _strategy_chain_breakdown(near_miss: dict) -> list:
    rows = []
    min_net_edge = float(near_miss.get("min_net_edge") or 0.0)
    for row in near_miss.get("by_kind", []):
        candidate_count = int(row.get("candidate_count") or 0)
        actionable_count = int(row.get("actionable_candidate_count") or 0)
        actionable_positive_net_count = int(row.get("actionable_positive_net_count") or 0)
        fee_blocked_count = int(row.get("fee_blocked_count") or 0)
        dominant_blocker = _strategy_dominant_blocker(row)
        rows.append(
            {
                "kind": row.get("kind"),
                "candidate_count": candidate_count,
                "actionable_candidate_count": actionable_count,
                "actionable_positive_net_count": actionable_positive_net_count,
                "diagnostic_candidate_count": int(row.get("diagnostic_candidate_count") or 0),
                "blocked_candidate_count": int(row.get("blocked_candidate_count") or 0),
                "fee_blocked_count": fee_blocked_count,
                "best_gross_edge_per_share": row.get("best_gross_edge_per_share"),
                "best_net_edge_per_share": row.get("best_net_edge_per_share"),
                "best_actionable_net_edge_per_share": row.get("best_actionable_net_edge_per_share"),
                "distance_to_min_net_edge": _distance_to_threshold(row.get("best_actionable_net_edge_per_share"), min_net_edge),
                "dominant_blocker": dominant_blocker,
                "next_action": _strategy_next_action(dominant_blocker),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            row["dominant_blocker"] != "pass",
            row["distance_to_min_net_edge"] if row["distance_to_min_net_edge"] is not None else 999.0,
            -(row["best_actionable_net_edge_per_share"] if row["best_actionable_net_edge_per_share"] is not None else -999),
            row["kind"] or "",
        ),
    )


def _chain_stage(
    stage: str,
    input_count: int,
    output_count: int,
    status: str,
    reason: str,
    next_action: str,
    diagnostics: Optional[dict] = None,
) -> dict:
    row = {
        "stage": stage,
        "status": status,
        "input_count": input_count,
        "output_count": output_count,
        "drop_count": max(0, input_count - output_count),
        "conversion_rate": output_count / input_count if input_count else 0.0,
        "reason": reason,
        "next_action": next_action,
    }
    if diagnostics:
        row["diagnostics"] = diagnostics
    return row


def _actionability_stage_status(candidate_count: int, actionable_count: int, diagnostic_count: int, blocked_count: int) -> str:
    if candidate_count == 0:
        return "not_evaluated"
    if actionable_count == 0:
        return "block"
    if diagnostic_count or blocked_count:
        return "warn"
    return "pass"


def _actionability_stage_reason(candidate_count: int, actionable_count: int, diagnostic_count: int, blocked_count: int) -> str:
    if candidate_count == 0:
        return "no_candidates_to_filter"
    if actionable_count == 0:
        return "all_candidates_are_diagnostic_or_blocked"
    if diagnostic_count or blocked_count:
        return "some_candidates_require_verification_or_are_rejected"
    return "all_candidates_actionable"


def _edge_diagnostics(near_miss: Optional[dict]) -> dict:
    if not near_miss:
        return {}
    best = (near_miss.get("top_actionable") or near_miss.get("top") or [None])[0]
    if not best:
        return {"best_actionable_net_edge_per_share": None, "distance_to_min_net_edge": None}
    return {
        "best_kind": best.get("kind"),
        "best_actionable_net_edge_per_share": best.get("net_edge_per_share"),
        "best_gross_edge_per_share": best.get("gross_edge_per_share"),
        "fee_drag_per_share": best.get("fee_drag_per_share"),
        "distance_to_min_net_edge": best.get("distance_to_min_net_edge"),
        "min_net_edge": near_miss.get("min_net_edge"),
    }


def _stability_stage_status(current_count: int, stable_count: int, actionable_positive_net_count: int) -> str:
    if current_count == 0:
        return "not_evaluated" if actionable_positive_net_count == 0 else "block"
    if stable_count == 0:
        return "block"
    if stable_count < current_count:
        return "warn"
    return "pass"


def _stability_stage_reason(current_count: int, stable_count: int, actionable_positive_net_count: int) -> str:
    if current_count == 0 and actionable_positive_net_count == 0:
        return "no_positive_edge_candidate_reached_realtime_opportunity_stage"
    if current_count == 0:
        return "positive_edge_candidates_not_observed_as_realtime_opportunities"
    if stable_count == 0:
        return "current_opportunities_did_not_survive_stability_window"
    if stable_count < current_count:
        return "some_current_opportunities_survive_stability_window"
    return "stable_opportunities_available"


def _paper_stage_status(stable_count: int, paper_count: int) -> str:
    if stable_count == 0:
        return "not_evaluated"
    if paper_count == 0:
        return "block"
    if paper_count < stable_count:
        return "warn"
    return "pass"


def _paper_stage_reason(stable_count: int, paper_count: int) -> str:
    if stable_count == 0:
        return "no_stable_opportunities_to_paper_trade"
    if paper_count == 0:
        return "stable_opportunities_failed_paper_trade_filters"
    if paper_count < stable_count:
        return "some_stable_opportunities_failed_paper_trade_filters"
    return "paper_trades_available"


def _first_stage_with_status(stages: list, status: str) -> Optional[dict]:
    for stage in stages:
        if stage.get("status") == status:
            return stage
    return None


def _chain_recommended_actions(stages: list) -> list:
    ranked = []
    priority = 1
    for status in ["block", "warn"]:
        for stage in stages:
            if stage.get("status") != status:
                continue
            ranked.append(
                {
                    "priority": priority,
                    "stage": stage["stage"],
                    "reason": stage["reason"],
                    "action": stage["next_action"],
                }
            )
            priority += 1
    return ranked[:5]


def _strategy_dominant_blocker(row: dict) -> str:
    if int(row.get("candidate_count") or 0) == 0:
        return "candidate_generation"
    if int(row.get("actionable_candidate_count") or 0) == 0:
        return "actionability_filter"
    if int(row.get("actionable_positive_net_count") or 0) == 0:
        if int(row.get("fee_blocked_count") or 0):
            return "fee_filter"
        return "edge_filter"
    return "pass"


def _strategy_next_action(blocker: str) -> str:
    actions = {
        "candidate_generation": "expand snapshots and verify the strategy has the required rule inputs",
        "actionability_filter": "review blocked candidates and promote only verified rules",
        "fee_filter": "target tighter spreads or maker-style execution because taker fees erase the gross edge",
        "edge_filter": "rank closest near misses and expand coverage around those markets",
        "pass": "send passing candidates into stability and paper-trade monitoring",
    }
    return actions.get(blocker, "inspect this strategy chain manually")


def _distance_to_threshold(value: Optional[float], threshold: float) -> Optional[float]:
    if value is None:
        return None
    return max(0.0, threshold - float(value))


def _counter_rows(counter: Counter, key: str) -> list:
    return [{key: name, "count": count} for name, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))]


def _parse_ts(value: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
