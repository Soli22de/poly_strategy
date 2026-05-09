import json
import time
from pathlib import Path
from typing import Iterable, Optional


ITERATION_TYPES = {"paper_monitor_iteration", "realtime_monitor_iteration"}


def latest_monitor_alerts(
    report_path: Path,
    min_paper_roi: Optional[float] = None,
    min_paper_edge: Optional[float] = None,
    include_current: bool = False,
    max_alerts: int = 20,
) -> list:
    if max_alerts < 0:
        raise ValueError("max_alerts must be non-negative")
    if min_paper_roi is not None and min_paper_roi < 0:
        raise ValueError("min_paper_roi must be non-negative")
    if min_paper_edge is not None and min_paper_edge < 0:
        raise ValueError("min_paper_edge must be non-negative")

    row = _latest_iteration_row(report_path)
    if not row or max_alerts == 0:
        return []

    alerts = []
    for trade in row.get("stable_paper_trades", []):
        if min_paper_roi is not None and float(trade.get("paper_roi") or 0.0) < min_paper_roi:
            continue
        if min_paper_edge is not None and float(trade.get("paper_edge") or 0.0) < min_paper_edge:
            continue
        alerts.append(_alert_row(row, "stable_paper_trade", trade, report_path))

    if include_current:
        for opportunity in row.get("stable_opportunities", []):
            alerts.append(_alert_row(row, "stable_opportunity", opportunity, report_path))
        for opportunity in row.get("current_opportunities", []):
            alerts.append(_alert_row(row, "current_opportunity", opportunity, report_path))

    alerts.sort(key=_alert_sort_key)
    return alerts[:max_alerts]


def write_alerts(
    rows: Iterable[dict],
    out_path: Path,
    state_path: Optional[Path] = None,
    cooldown_seconds: float = 0.0,
) -> int:
    if cooldown_seconds < 0:
        raise ValueError("cooldown_seconds must be non-negative")
    rows = list(rows)
    if state_path:
        rows = _filter_alerts_with_cooldown(rows, state_path, cooldown_seconds)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return len(rows)


def _latest_iteration_row(report_path: Path) -> Optional[dict]:
    latest = None
    with report_path.open() as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("type") in ITERATION_TYPES:
                latest = row
    return latest


def _alert_row(iteration_row: dict, alert_kind: str, payload: dict, report_path: Path) -> dict:
    return {
        "type": "opportunity_alert",
        "alert_kind": alert_kind,
        "ts": iteration_row.get("ts"),
        "source_report": str(report_path),
        "source_type": iteration_row.get("type"),
        "iteration": iteration_row.get("iteration"),
        "last_snapshot_ts": iteration_row.get("last_snapshot_ts"),
        "key": payload.get("key"),
        "kind": payload.get("kind"),
        "market_ids": _market_ids(payload),
        "net_edge_per_share": payload.get("net_edge_per_share"),
        "total_edge": payload.get("total_edge"),
        "paper_roi": payload.get("paper_roi"),
        "paper_edge": payload.get("paper_edge"),
        "payload": payload,
    }


def _market_ids(payload: dict) -> list:
    market_ids = []
    for leg in payload.get("legs", []):
        market_id = leg.get("market_id")
        if market_id:
            market_ids.append(str(market_id))
    return list(dict.fromkeys(market_ids))


def _alert_sort_key(row: dict) -> tuple:
    paper_roi = row.get("paper_roi")
    paper_edge = row.get("paper_edge")
    net_edge = row.get("net_edge_per_share")
    total_edge = row.get("total_edge")
    return (
        {"stable_paper_trade": 0, "stable_opportunity": 1, "current_opportunity": 2}.get(row.get("alert_kind"), 3),
        -float(paper_roi or 0.0),
        -float(paper_edge or 0.0),
        -float(net_edge or 0.0),
        -float(total_edge or 0.0),
        str(row.get("key") or ""),
    )


def _filter_alerts_with_cooldown(rows: list, state_path: Path, cooldown_seconds: float) -> list:
    now = time.time()
    state = _read_alert_state(state_path)
    emitted = []
    for row in rows:
        key = _alert_state_key(row)
        last_emitted_at = float(state.get(key, 0.0) or 0.0)
        if cooldown_seconds > 0 and now - last_emitted_at < cooldown_seconds:
            continue
        emitted.append(row)
        state[key] = now
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    return emitted


def _read_alert_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        row = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return row if isinstance(row, dict) else {}


def _alert_state_key(row: dict) -> str:
    return "|".join(
        [
            str(row.get("alert_kind") or ""),
            str(row.get("kind") or ""),
            str(row.get("key") or ""),
            ",".join(row.get("market_ids") or []),
        ]
    )
