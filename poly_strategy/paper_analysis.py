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
    by_kind = near_miss.get("by_kind", [])
    best = top[0] if top else None
    positive_gross = sum(int(row.get("positive_gross_count") or 0) for row in by_kind)
    positive_net = sum(int(row.get("positive_net_count") or 0) for row in by_kind)
    fee_blocked = sum(int(row.get("fee_blocked_count") or 0) for row in by_kind)
    reasons = []
    if report.get("final_known_token_count", 0) and report.get("final_known_token_count", 0) < 100:
        reasons.append("watchlist_too_narrow")
    if not top:
        reasons.append("no_evaluable_candidates")
    elif float(best.get("net_edge_per_share") or 0.0) <= float(near_miss.get("min_net_edge") or 0.0):
        reasons.append("best_candidate_below_min_edge")
    if fee_blocked:
        reasons.append("fees_erase_gross_edge")
    if positive_gross and not positive_net:
        reasons.append("fee_drag_dominates_positive_gross_edges")
    if report.get("connection_events", {}).get("by_event"):
        events = {row.get("event") for row in report["connection_events"]["by_event"]}
        if "disconnected" in events or "reconnect_sleep" in events:
            reasons.append("websocket_reconnects_reduce_continuity")
    return {
        "reasons": sorted(set(reasons)),
        "best_candidate": best,
        "positive_gross_candidate_count": positive_gross,
        "positive_net_candidate_count": positive_net,
        "fee_blocked_candidate_count": fee_blocked,
        "closest_by_kind": by_kind[:10],
    }


def _counter_rows(counter: Counter, key: str) -> list:
    return [{key: name, "count": count} for name, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))]


def _parse_ts(value: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
