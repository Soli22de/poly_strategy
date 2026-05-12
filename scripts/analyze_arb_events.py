#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Arb-persistence event analyzer.

Reads every `groups.ndjson` under `data/snapshots/` (produced by
`snapshot_gamma.py`), reconstructs the time series for each neg-risk
group, detects "edge events" -- contiguous runs of snapshots where the
group sits above the edge threshold -- and reports the two metrics that
decide the long-tail arb thesis go/kill:

    1. event_count    (distinct events with peak_edge > threshold)
    2. median_persistence_minutes  (across those events)

Pass / kill criteria locked upfront (long-tail thesis, 14-day window):
    - GO        : >= 5 events AND median_persistence >= 60 min
    - KILL      : < 2 events  OR median_persistence < 15 min
    - BORDERLINE: anything in between -> extend window or pivot tier

Stdlib only -- no DuckDB dependency yet. Runs over 1300+ snapshots in
a few seconds.

Usage:
    python scripts/analyze_arb_events.py
    python scripts/analyze_arb_events.py --tier explicit_other --min-edge 0.05
    python scripts/analyze_arb_events.py --tier binary --min-edge 0.02
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOTS_ROOT = REPO_ROOT / "data" / "snapshots"


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def load_all_groups(root: Path) -> list[dict]:
    rows: list[dict] = []
    for groups_path in sorted(root.glob("*/*/groups.ndjson")):
        with groups_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows


def detect_events(
    group_rows: list[dict],
    min_edge: float,
    max_gap_minutes: float,
) -> list[dict]:
    """Walk one group's time-sorted rows, emit edge events.

    A new event starts when edge crosses above min_edge.
    An event ends when edge drops below min_edge OR a snapshot gap exceeds
    max_gap_minutes (treated as data outage, not edge persistence).
    """
    events: list[dict] = []
    if not group_rows:
        return events
    group_rows = sorted(group_rows, key=lambda r: r["snapshot_ts"])

    current: dict | None = None
    prev_ts: datetime | None = None

    for r in group_rows:
        ts = parse_ts(r["snapshot_ts"])
        above = r["edge_after_fee"] > min_edge

        gap_too_big = (
            prev_ts is not None
            and (ts - prev_ts).total_seconds() / 60.0 > max_gap_minutes
        )
        if current is not None and gap_too_big:
            events.append(current)
            current = None

        if above:
            if current is None:
                current = {
                    "neg_risk_market_id": r["neg_risk_market_id"],
                    "tier": r["tier"],
                    "start_ts": r["snapshot_ts"],
                    "end_ts": r["snapshot_ts"],
                    "n_snapshots": 1,
                    "peak_edge": r["edge_after_fee"],
                    "peak_edge_ts": r["snapshot_ts"],
                    "min_liquidity_seen": r["min_liquidity"],
                    "has_longtail_member_ever": r["has_longtail_member"],
                    "size": r["size"],
                }
            else:
                current["end_ts"] = r["snapshot_ts"]
                current["n_snapshots"] += 1
                current["min_liquidity_seen"] = min(
                    current["min_liquidity_seen"], r["min_liquidity"]
                )
                current["has_longtail_member_ever"] = (
                    current["has_longtail_member_ever"] or r["has_longtail_member"]
                )
                if r["edge_after_fee"] > current["peak_edge"]:
                    current["peak_edge"] = r["edge_after_fee"]
                    current["peak_edge_ts"] = r["snapshot_ts"]
        else:
            if current is not None:
                events.append(current)
                current = None

        prev_ts = ts

    if current is not None:
        events.append(current)

    for e in events:
        start = parse_ts(e["start_ts"])
        end = parse_ts(e["end_ts"])
        e["persistence_minutes"] = round((end - start).total_seconds() / 60.0, 1)
    return events


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="explicit_other",
                    choices=["explicit_other", "binary", "open_set", "any"])
    ap.add_argument("--min-edge", type=float, default=0.05,
                    help="Edge threshold (after fees). Default 5%%.")
    ap.add_argument("--max-gap-minutes", type=float, default=35.0,
                    help="Snapshots farther apart than this break a run.")
    ap.add_argument("--root", type=Path, default=SNAPSHOTS_ROOT)
    args = ap.parse_args()

    if not args.root.exists():
        print(f"ERROR: snapshots root not found: {args.root}", file=sys.stderr)
        return 2

    print(f"Loading snapshots from {args.root}...")
    rows = load_all_groups(args.root)
    if not rows:
        print("ERROR: no group rows loaded", file=sys.stderr)
        return 2

    # Filter to chosen tier
    if args.tier != "any":
        rows = [r for r in rows if r["tier"] == args.tier]
    print(f"  loaded {len(rows)} group-snapshots (tier={args.tier})")

    # Snapshot range
    timestamps = sorted({r["snapshot_ts"] for r in rows})
    if not timestamps:
        print("ERROR: no rows matched tier filter", file=sys.stderr)
        return 2
    first_ts, last_ts = timestamps[0], timestamps[-1]
    span_hours = (parse_ts(last_ts) - parse_ts(first_ts)).total_seconds() / 3600.0
    print(f"  range: {first_ts}  ->  {last_ts}  ({span_hours:.1f} hr, {len(timestamps)} unique snapshots)")

    # Group by neg_risk_market_id
    by_group: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_group[r["neg_risk_market_id"]].append(r)
    print(f"  distinct groups: {len(by_group)}")

    # Detect events
    all_events: list[dict] = []
    for gid, grows in by_group.items():
        all_events.extend(detect_events(grows, args.min_edge, args.max_gap_minutes))

    # Sort by peak edge desc
    all_events.sort(key=lambda e: -e["peak_edge"])

    # Aggregate metrics
    n_events = len(all_events)
    n_longtail = sum(1 for e in all_events if e["has_longtail_member_ever"])
    persistences = [e["persistence_minutes"] for e in all_events]
    median_persistence = statistics.median(persistences) if persistences else 0.0
    p25 = statistics.quantiles(persistences, n=4)[0] if len(persistences) >= 4 else (min(persistences) if persistences else 0.0)
    p75 = statistics.quantiles(persistences, n=4)[2] if len(persistences) >= 4 else (max(persistences) if persistences else 0.0)

    # Decision banner
    if args.tier == "explicit_other" and abs(args.min_edge - 0.05) < 1e-9:
        if n_events >= 5 and median_persistence >= 60:
            verdict = "GO  (>=5 events AND median persistence >=60min)"
        elif n_events < 2 or median_persistence < 15:
            verdict = "KILL (<2 events OR median persistence <15min)"
        else:
            verdict = "BORDERLINE (extend window or pivot to binary tier)"
    else:
        verdict = f"(custom tier/threshold -- pass/kill criteria undefined)"

    # Render report
    now_iso = datetime.now(tz=timezone.utc).isoformat()
    date_tag = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    lines = [
        f"# Arb-persistence Analysis ({now_iso})",
        "",
        f"**Filter**: tier=`{args.tier}`, edge_after_fee > {args.min_edge:.2%}, max gap {args.max_gap_minutes:.0f}min",
        f"**Snapshot range**: {first_ts}  ->  {last_ts}",
        f"**Window**: {span_hours:.1f} hours across {len(timestamps)} unique snapshots",
        "",
        "## Pass / kill metrics",
        "",
        f"- **Distinct edge events**: {n_events}  (with longtail member: {n_longtail})",
        f"- **Median persistence (min)**: {median_persistence:.1f}  (P25: {p25:.1f}, P75: {p75:.1f})",
        "",
        f"**Verdict**: {verdict}",
        "",
        "## Top events by peak edge",
        "",
        "| neg_risk_market_id | size | peak_edge | persistence (min) | min_liq seen | longtail | start_ts | end_ts |",
        "|---|---:|---:|---:|---:|:---:|---|---|",
    ]
    for e in all_events[:30]:
        lt = "Y" if e["has_longtail_member_ever"] else ""
        lines.append(
            f"| `{e['neg_risk_market_id'][:14]}...` "
            f"| {e['size']} "
            f"| {e['peak_edge']:+.4f} "
            f"| {e['persistence_minutes']:.1f} "
            f"| ${e['min_liquidity_seen']:,.0f} "
            f"| {lt} "
            f"| {e['start_ts']} "
            f"| {e['end_ts']} |"
        )
    if not all_events:
        lines.append("| _no events at this threshold_ |  |  |  |  |  |  |  |")

    lines += [
        "",
        "## Notes",
        "",
        "- An *event* = contiguous run of snapshots where this group's `edge_after_fee` stayed above the threshold. Gap > max_gap_minutes splits a run.",
        "- `persistence_minutes` = end_ts - start_ts. A one-snapshot flash shows 0 min.",
        "- `min_liquidity_seen` = the minimum group-wide min_liquidity across the event (proxy for thinnest leg).",
        "- For thesis decision use `tier=explicit_other --min-edge 0.05`; rerun with `--tier binary --min-edge 0.02` for the pivot view.",
        "",
        f"---\n*Analyzed at {now_iso}*",
    ]

    report_path = REPO_ROOT / "reports" / f"arb-persistence-{date_tag}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")

    print()
    print("=== Summary ===")
    print(f"tier={args.tier}  min_edge={args.min_edge:.2%}  window={span_hours:.1f}hr")
    print(f"events={n_events}  longtail_events={n_longtail}")
    print(f"median_persistence={median_persistence:.1f}min  (P25={p25:.1f}, P75={p75:.1f})")
    print(f"verdict: {verdict}")
    print(f"report: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
