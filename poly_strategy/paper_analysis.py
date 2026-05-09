import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional


def analyze_paper_monitor_report(path: Path, top_n: int = 10) -> dict:
    if top_n < 0:
        raise ValueError("top_n must be non-negative")

    rows = list(_read_jsonl(path))
    iteration_rows = [row for row in rows if row.get("type") == "paper_monitor_iteration"]
    error_rows = [row for row in rows if row.get("type") == "paper_monitor_iteration_error"]
    summary_rows = [row for row in rows if row.get("type") == "paper_monitor_summary"]

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

    return {
        "type": "paper_monitor_analysis",
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
        "current_opportunity_observations": sum(int(row.get("current_opportunity_count") or 0) for row in iteration_rows),
        "stable_opportunity_observations": sum(int(row.get("stable_opportunity_count") or 0) for row in iteration_rows),
        "stable_paper_trade_observations": sum(int(row.get("stable_paper_trade_count") or 0) for row in iteration_rows),
        "stable_paper_capital_used": stable_paper_capital_used,
        "stable_paper_edge": stable_paper_edge,
        "stable_paper_roi": stable_paper_edge / stable_paper_capital_used if stable_paper_capital_used > 0 else 0.0,
        "current_edge": _distribution(current_edges),
        "stable_edge": _distribution(stable_edges),
        "stable_paper_roi_distribution": _distribution(stable_trade_rois),
        "top_current_opportunities": _top_opportunities(iteration_rows, "current_opportunities", top_n),
        "top_stable_opportunities": _top_opportunities(iteration_rows, "stable_opportunities", top_n),
        "top_stable_markets": _top_markets(iteration_rows, "stable_opportunities", top_n),
        "error_summary": _error_summary(error_rows, iteration_rows),
        "latest_summary": latest_summary,
    }


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


def _counter_rows(counter: Counter, key: str) -> list:
    return [{key: name, "count": count} for name, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))]


def _parse_ts(value: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
