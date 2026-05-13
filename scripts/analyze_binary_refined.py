#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Refined binary-tier analysis: filter to TRUE exhaustive 2-member groups.

Today's `binary` tier classifier (size == 2) eats too many false positives:
e.g. Aston Villa vs Freiburg in UEFA Europa League looks "binary" but
dozens of teams compete. Real arbitrage requires the 2 members truly
covering 100% of outcomes.

Sub-classification of each 2-member neg-risk group:
  - `dvr`     : one question mentions Democrats, other mentions Republicans,
                and they share a race noun (Senate / governor / House /
                Presidential election). Real exhaustive binary in US politics.
  - `yes_no`  : one question is "Will X happen" form, other negates it
                ("Will X NOT happen" or matching opposite). Exhaustive Y/N.
  - `pseudo`  : default fallback. Likely a sample of a larger universe
                (sports leagues, primaries). Treat as open_set false signal.

Inputs:
  - data/snapshots/*/*/markets.ndjson (use today's most recent live snapshot
    as the source of truth for question text per market_id; questions don't
    change historically)
  - data/snapshots/*/*/groups.ndjson (full 14-day history of group rows)

Outputs:
  - reports/binary-refined-<date>.md (per-subtier events + persistence stats)
  - data/experiments/<date>/binary-classification.json (per-group sub-tag)
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOTS_ROOT = REPO_ROOT / "data" / "snapshots"


def load_ndjson(p: Path) -> list[dict]:
    rows: list[dict] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ----- Sub-tier classifier --------------------------------------------------

DEMO_PAT = re.compile(r"\bdemocrat", re.IGNORECASE)
REP_PAT = re.compile(r"\brepublican", re.IGNORECASE)
RACE_NOUNS = (
    "senate", "governor", "house", "presidential", "president",
    "secretary of state", "attorney general", "lieutenant governor",
)
# "Will X happen" / "Will X NOT happen"
NEG_HINTS = re.compile(r"\b(not |fail to |miss |stay |remain )\b", re.IGNORECASE)


def share_race_token(q1: str, q2: str) -> str | None:
    q1l, q2l = q1.lower(), q2.lower()
    for noun in RACE_NOUNS:
        if noun in q1l and noun in q2l:
            return noun
    return None


def classify_binary_pair(q_a: str, q_b: str) -> dict:
    """Return {sub_tier: str, label: str} for a 2-question pair."""
    ql_a, ql_b = q_a.lower(), q_b.lower()

    a_demo = bool(DEMO_PAT.search(ql_a))
    a_rep = bool(REP_PAT.search(ql_a))
    b_demo = bool(DEMO_PAT.search(ql_b))
    b_rep = bool(REP_PAT.search(ql_b))

    if (a_demo and b_rep) or (a_rep and b_demo):
        race_token = share_race_token(q_a, q_b)
        if race_token:
            return {"sub_tier": "dvr", "label": f"D vs R ({race_token})"}
        # Same parties but no shared race noun -> still likely real if both mention party
        return {"sub_tier": "dvr", "label": "D vs R (no shared race noun)"}

    # Naive Yes/No: same question minus "not"
    a_neg = bool(NEG_HINTS.search(ql_a))
    b_neg = bool(NEG_HINTS.search(ql_b))
    if a_neg != b_neg:
        # heuristic: if removing neg-hints makes one a prefix of the other
        a_clean = NEG_HINTS.sub("", ql_a).strip()
        b_clean = NEG_HINTS.sub("", ql_b).strip()
        # Cheap similarity: length-normalized longest common prefix
        common = 0
        for ca, cb in zip(a_clean, b_clean):
            if ca == cb:
                common += 1
            else:
                break
        if common > 25 and common > 0.6 * min(len(a_clean), len(b_clean)):
            return {"sub_tier": "yes_no", "label": "Yes/No (negation pattern)"}

    return {"sub_tier": "pseudo", "label": "pseudo (sample-of-many likely)"}


# ----- Event detection (same shape as analyze_arb_events.py) -----------------

def detect_events(rows: list[dict], min_edge: float, max_gap_min: float) -> list[dict]:
    rows = sorted(rows, key=lambda r: r["snapshot_ts"])
    events: list[dict] = []
    current: dict | None = None
    prev_ts: datetime | None = None
    for r in rows:
        ts = parse_ts(r["snapshot_ts"])
        above = r["edge_after_fee"] > min_edge
        gap = prev_ts is not None and (ts - prev_ts).total_seconds() / 60.0 > max_gap_min
        if current is not None and gap:
            events.append(current)
            current = None
        if above:
            if current is None:
                current = {
                    "neg_risk_market_id": r["neg_risk_market_id"],
                    "start_ts": r["snapshot_ts"],
                    "end_ts": r["snapshot_ts"],
                    "peak_edge": r["edge_after_fee"],
                    "n_snapshots": 1,
                    "min_liquidity_seen": r["min_liquidity"],
                }
            else:
                current["end_ts"] = r["snapshot_ts"]
                current["peak_edge"] = max(current["peak_edge"], r["edge_after_fee"])
                current["min_liquidity_seen"] = min(current["min_liquidity_seen"], r["min_liquidity"])
                current["n_snapshots"] += 1
        elif current is not None:
            events.append(current)
            current = None
        prev_ts = ts
    if current is not None:
        events.append(current)
    for e in events:
        e["persistence_minutes"] = round(
            (parse_ts(e["end_ts"]) - parse_ts(e["start_ts"])).total_seconds() / 60.0, 1
        )
    return events


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-edge", type=float, default=0.02)
    ap.add_argument("--max-gap-minutes", type=float, default=35.0)
    ap.add_argument("--live-only", action="store_true",
                    help="Drop is_backfill=true rows (use only live snapshot data).")
    args = ap.parse_args()

    # Find latest live markets.ndjson for question lookup
    markets_files = sorted(SNAPSHOTS_ROOT.glob("*/*/markets.ndjson"))
    if not markets_files:
        print("ERROR: no markets.ndjson found (live snapshot didn't run yet)", file=sys.stderr)
        return 2
    latest_mk = markets_files[-1]
    print(f"Question source: {latest_mk}")
    live_markets = load_ndjson(latest_mk)
    question_by_mid: dict[str, str] = {m["market_id"]: m["question"] for m in live_markets}
    # Build today's group -> 2 questions map (only the groups that are size==2 today)
    today_groups: dict[str, list[str]] = defaultdict(list)
    today_member_ids: dict[str, list[str]] = defaultdict(list)
    for m in live_markets:
        today_groups[m["neg_risk_market_id"]].append(m["question"])
        today_member_ids[m["neg_risk_market_id"]].append(m["market_id"])

    # Classify every 2-member group seen today
    classifications: dict[str, dict] = {}
    for gid, qs in today_groups.items():
        if len(qs) != 2:
            continue
        classifications[gid] = classify_binary_pair(qs[0], qs[1])
        classifications[gid]["questions"] = [q[:80] for q in qs]
        classifications[gid]["member_ids"] = today_member_ids[gid]
    print(f"2-member groups classified: {len(classifications)}")
    by_subtier: dict[str, int] = defaultdict(int)
    for c in classifications.values():
        by_subtier[c["sub_tier"]] += 1
    print(f"  sub-tiers: {dict(by_subtier)}")

    # Load all historical binary group-rows (live + backfill)
    print(f"\nLoading historical group rows...")
    all_rows: list[dict] = []
    for gp in sorted(SNAPSHOTS_ROOT.glob("*/*/groups.ndjson")):
        all_rows.extend(load_ndjson(gp))
    if args.live_only:
        before = len(all_rows)
        all_rows = [r for r in all_rows if not r.get("is_backfill")]
        print(f"  --live-only: dropped {before - len(all_rows)} backfill rows, kept {len(all_rows)}")
    binary_rows = [r for r in all_rows if r["tier"] == "binary"]
    print(f"  total: {len(all_rows)} group-rows, of which binary: {len(binary_rows)}")

    # Attach sub_tier from today's classification (groups that weren't 2-member today are dropped)
    enriched: list[dict] = []
    for r in binary_rows:
        c = classifications.get(r["neg_risk_market_id"])
        if not c:
            continue
        r = dict(r)
        r["sub_tier"] = c["sub_tier"]
        enriched.append(r)
    print(f"  rows enriched with sub_tier: {len(enriched)}")

    # Detect events per sub_tier
    print(f"\nDetecting events at min_edge={args.min_edge:.2%}, max_gap={args.max_gap_minutes:.0f}min")
    subtier_groups: dict[str, dict[str, list[dict]]] = {
        st: defaultdict(list) for st in ("dvr", "yes_no", "pseudo")
    }
    for r in enriched:
        subtier_groups[r["sub_tier"]][r["neg_risk_market_id"]].append(r)

    subtier_events: dict[str, list[dict]] = {}
    for st, by_gid in subtier_groups.items():
        evs: list[dict] = []
        for gid, rows in by_gid.items():
            evs.extend(detect_events(rows, args.min_edge, args.max_gap_minutes))
        subtier_events[st] = evs
        evs_sorted = sorted(evs, key=lambda e: -e["peak_edge"])
        if not evs:
            print(f"  {st}: 0 events")
            continue
        pers = [e["persistence_minutes"] for e in evs]
        med = statistics.median(pers)
        print(f"  {st}: events={len(evs)}  groups={len(by_gid)}  median_persistence={med:.0f}min  peak_top3={[round(e['peak_edge'],3) for e in evs_sorted[:3]]}")

    # Render report
    now = datetime.now(tz=timezone.utc)
    iso = now.isoformat()
    date_tag = now.strftime("%Y-%m-%d")
    lines = [
        f"# Refined Binary-tier Analysis ({iso})",
        "",
        f"**Source**: today's `markets.ndjson` (question text) + 14-day backfill (`groups.ndjson`).",
        f"**Threshold**: edge_after_fee > {args.min_edge:.2%}",
        "",
        f"## 1. Sub-tier counts (today's 2-member groups)",
        "",
    ]
    for st in ("dvr", "yes_no", "pseudo"):
        lines.append(f"- `{st}`: {by_subtier.get(st, 0)} groups")

    lines += ["", "## 2. Event metrics by sub-tier", "", "| sub_tier | events | distinct groups | median persistence (min) | top peak edge |", "|---|---:|---:|---:|---:|"]
    for st in ("dvr", "yes_no", "pseudo"):
        evs = subtier_events[st]
        if not evs:
            lines.append(f"| `{st}` | 0 | 0 | — | — |")
            continue
        pers = [e["persistence_minutes"] for e in evs]
        groups_n = len(subtier_groups[st])
        top_peak = max(e["peak_edge"] for e in evs)
        lines.append(f"| `{st}` | {len(evs)} | {groups_n} | {statistics.median(pers):.0f} | {top_peak:+.4f} |")

    lines += ["", "## 3. Top 15 `dvr` events (real D vs R races)", ""]
    dvr_evs = sorted(subtier_events["dvr"], key=lambda e: -e["peak_edge"])[:15]
    if not dvr_evs:
        lines.append("_no events at this threshold_")
    else:
        lines.append("| group | peak_edge | persistence (min) | min_liq | start | end |")
        lines.append("|---|---:|---:|---:|---|---|")
        for e in dvr_evs:
            gid = e["neg_risk_market_id"]
            c = classifications.get(gid)
            qhint = c["questions"][0][:30] + " vs ..." if c else ""
            lines.append(
                f"| `{gid[:14]}...` ({qhint}) "
                f"| {e['peak_edge']:+.4f} "
                f"| {e['persistence_minutes']:.0f} "
                f"| ${e['min_liquidity_seen']:,.0f} "
                f"| {e['start_ts'][:19]} "
                f"| {e['end_ts'][:19]} |"
            )

    lines += ["", "## 4. Notes", "",
              "- `dvr` (D vs R) is the only sub-tier that is structurally exhaustive in US politics — third parties get < 1% of vote in modern Senate/Governor general elections.",
              "- `yes_no` heuristic is naive (negation-substring + similarity). Likely under-counts.",
              "- `pseudo` events are NOT tradeable as basket arb — the listed 2 members are a sample, not the whole universe.",
              "- Verdict on dvr depends on event count AND median persistence AND a depth check (NOT done yet — same trap as James Bond, where mid edge > bestAsk edge after slippage).",
              "",
              f"---\n*Generated at {iso}*"]

    out_path = REPO_ROOT / "reports" / f"binary-refined-{date_tag}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")

    cls_path = REPO_ROOT / "data" / "experiments" / date_tag / "binary-classification.json"
    cls_path.parent.mkdir(parents=True, exist_ok=True)
    with cls_path.open("w", encoding="utf-8") as f:
        json.dump(classifications, f, indent=2, ensure_ascii=False)

    print(f"\nreport: {out_path}")
    print(f"classification: {cls_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
