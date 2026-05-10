import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from poly_strategy.recent_lines import read_recent_lines


ITERATION_TYPES = {"paper_monitor_iteration", "realtime_monitor_iteration"}


def success_status_report(
    monitor_report_path: Optional[Path] = None,
    execution_plans_path: Optional[Path] = None,
    maker_adaptive_path: Optional[Path] = None,
    cross_platform_scan_path: Optional[Path] = None,
    min_cross_platform_capital_edge: float = 0.0,
    generated_at: Optional[str] = None,
) -> dict:
    monitor = _monitor_summary(monitor_report_path)
    plans = _execution_plan_summary(execution_plans_path)
    maker = _maker_adaptive_summary(maker_adaptive_path)
    cross_platform = _cross_platform_summary(cross_platform_scan_path, min_cross_platform_capital_edge)
    status = _success_status(monitor, plans, maker, cross_platform)
    return {
        "type": "success_status_report",
        "generated_at": generated_at or _utc_now(),
        "status": status,
        "live_success": status == "live_success",
        "dry_run_executable": status == "dry_run_executable",
        "paper_success_candidate": status
        in {"live_success", "dry_run_executable", "stable_paper_opportunity", "cross_platform_paper_opportunity"},
        "monitor": monitor,
        "execution_plans": plans,
        "maker_adaptive": maker,
        "cross_platform": cross_platform,
    }


def write_success_status(
    out_path: Path,
    report: dict,
    success_log_path: Optional[Path] = None,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if success_log_path and report.get("status") != "no_success":
        success_log_path.parent.mkdir(parents=True, exist_ok=True)
        with success_log_path.open("a") as handle:
            handle.write(json.dumps(report, sort_keys=True) + "\n")


def _monitor_summary(path: Optional[Path]) -> dict:
    row = _latest_jsonl_row(path, ITERATION_TYPES)
    if not row:
        return {"path": str(path) if path else None, "found": False}
    stable_trades = list(row.get("stable_paper_trades") or [])
    return {
        "path": str(path),
        "found": True,
        "ts": row.get("ts"),
        "iteration": row.get("iteration"),
        "current_opportunity_count": int(row.get("current_opportunity_count") or 0),
        "stable_opportunity_count": int(row.get("stable_opportunity_count") or 0),
        "stable_paper_trade_count": int(row.get("stable_paper_trade_count") or len(stable_trades)),
        "stable_paper_edge": float(row.get("stable_paper_edge") or 0.0),
        "stable_paper_roi": float(row.get("stable_paper_roi") or 0.0),
        "top_stable_paper_trade": stable_trades[0] if stable_trades else None,
    }


def _execution_plan_summary(path: Optional[Path]) -> dict:
    rows = _jsonl_rows(path, row_type="execution_plan")
    dry_run_passed = [row for row in rows if _plan_pretrade_passed(row) and _plan_risk_passed(row) and bool(row.get("dry_run", True))]
    live_success = [
        row
        for row in rows
        if _plan_pretrade_passed(row)
        and _plan_risk_passed(row)
        and not bool(row.get("dry_run", True))
        and (row.get("reconciliation") or {}).get("status") == "submitted"
    ]
    return {
        "path": str(path) if path else None,
        "found": bool(rows),
        "plan_count": len(rows),
        "dry_run_passed_count": len(dry_run_passed),
        "live_success_count": len(live_success),
        "top_dry_run_plan": dry_run_passed[0] if dry_run_passed else None,
        "top_live_success_plan": live_success[0] if live_success else None,
    }


def _maker_adaptive_summary(path: Optional[Path]) -> dict:
    row = _read_json(path)
    if not row:
        return {"path": str(path) if path else None, "found": False}
    return {
        "path": str(path),
        "found": True,
        "status": row.get("status"),
        "batch_count": int(row.get("batch_count") or 0),
        "recommended_config": row.get("recommended_config"),
        "top_config": (row.get("ranked_configs") or [None])[0],
    }


def _cross_platform_summary(path: Optional[Path], min_capital_edge: float = 0.0) -> dict:
    row = _read_json(path)
    if not row:
        return {"path": str(path) if path else None, "found": False}
    opportunities = list(row.get("opportunities") or [])
    positive = [
        opportunity
        for opportunity in opportunities
        if float(opportunity.get("net_edge_per_share") or 0.0) > 0
        and bool((opportunity.get("pair") or {}).get("trade_allowed"))
    ]
    positive.sort(
        key=lambda opportunity: -float(
            ((opportunity.get("capital_capped") or {}).get("edge"))
            if (opportunity.get("capital_capped") or {}).get("edge") is not None
            else opportunity.get("total_edge") or 0.0
        )
    )
    top = positive[0] if positive else None
    actionable = [
        opportunity
        for opportunity in positive
        if float(((opportunity.get("capital_capped") or {}).get("edge")) or opportunity.get("total_edge") or 0.0)
        >= min_capital_edge
    ]
    return {
        "path": str(path),
        "found": True,
        "min_capital_edge": min_capital_edge,
        "pair_count": int(row.get("pair_count") or 0),
        "opportunity_count": int(row.get("opportunity_count") or 0),
        "verified_positive_count": len(positive),
        "actionable_verified_positive_count": len(actionable),
        "top_verified_positive": top,
        "top_capital_capped_edge": float(((top or {}).get("capital_capped") or {}).get("edge") or 0.0),
    }


def _success_status(monitor: dict, plans: dict, maker: dict, cross_platform: dict) -> str:
    if plans.get("live_success_count", 0) > 0:
        return "live_success"
    if plans.get("dry_run_passed_count", 0) > 0:
        return "dry_run_executable"
    if monitor.get("stable_paper_trade_count", 0) > 0 and monitor.get("stable_paper_edge", 0.0) > 0:
        return "stable_paper_opportunity"
    if cross_platform.get("actionable_verified_positive_count", 0) > 0:
        return "cross_platform_paper_opportunity"
    if maker.get("status") == "positive_ev_config_found":
        return "maker_positive_ev"
    return "no_success"


def _latest_jsonl_row(path: Optional[Path], row_types: set) -> Optional[dict]:
    if not path or not path.exists():
        return None
    latest = None
    for row in _json_rows_from_lines(read_recent_lines(path, max_lines=5000)):
        if row.get("type") in row_types:
            latest = row
    return latest


def _jsonl_rows(path: Optional[Path], row_type: Optional[str] = None) -> list:
    if not path or not path.exists():
        return []
    rows = []
    with path.open() as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row_type and row.get("type") != row_type:
                continue
            rows.append(row)
    return rows


def _json_rows_from_lines(lines: list) -> list:
    rows = []
    for raw_line in lines:
        line = str(raw_line).strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _read_json(path: Optional[Path]) -> Optional[dict]:
    if not path or not path.exists():
        return None
    try:
        text = path.read_text()
        if not text.strip():
            return None
        row = json.loads(text)
    except (OSError, json.JSONDecodeError):
        return None
    return row if isinstance(row, dict) else None


def _plan_pretrade_passed(row: dict) -> bool:
    return bool((row.get("pretrade_check") or {}).get("passed"))


def _plan_risk_passed(row: dict) -> bool:
    risk = row.get("risk_check")
    return True if risk is None else bool(risk.get("passed"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
