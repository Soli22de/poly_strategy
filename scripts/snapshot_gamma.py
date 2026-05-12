#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gamma neg-risk snapshot collector (long-tail arb persistence study).

Fetches the current Gamma /markets payload, filters to negRisk markets, and
writes a paired (markets.ndjson, groups.ndjson) snapshot under
`data/snapshots/YYYY-MM-DD/HH-MM/`.

Intended to run every 15 minutes for 14 days driven by
`run_snapshot_loop.ps1`. Each run is self-contained: a failed fetch on
page N is logged and the rest of the snapshot is written from pages 0..N-1.

Per-snapshot output:
  data/snapshots/YYYY-MM-DD/HH-MM/markets.ndjson  -- per-market row, one line
  data/snapshots/YYYY-MM-DD/HH-MM/groups.ndjson   -- per neg-risk-group row,
                                                     pre-classified with tier
                                                     + edge_after_fee so
                                                     analysis is one SELECT.

Storage budget: ~600B/market * ~1500 markets = ~0.9 MB raw + ~50 KB groups
per snapshot. 14 days * 96 snapshots/day = ~1.3 GB total. Data dir is
gitignored.

The classifier (`classify_exhaustiveness`, `is_other_marker`,
`EXHAUSTIVE_MARKERS`) intentionally duplicates the logic in
`scripts/experiment_negrisk_mispricing.py` so changes to the persistence
study are decoupled from changes to the one-off survey script.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"

EXHAUSTIVE_MARKERS = [
    "no one ", "none of ", "another candidate", "another team", "another player",
    "another company", "another country", "another person",
    "any other", "no candidate", "neither ",
    "someone else", "no one named", "no one announced", "no one wins",
    "no one is", "no one will", "no one ends",
    "different player", "different team",
]


def is_other_marker(question: str) -> bool:
    q = (question or "").lower()
    return any(token in q for token in EXHAUSTIVE_MARKERS)


def classify_exhaustiveness(member_is_other_flags: list[bool], size: int) -> str:
    if any(member_is_other_flags):
        return "explicit_other"
    if size == 2:
        return "binary"
    return "open_set"


def to_float(x, default: float | None = None) -> float | None:
    if x is None:
        return default
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def fetch_markets_page(limit: int, offset: int, timeout: float = 30.0) -> list[dict]:
    params = {"limit": limit, "offset": offset, "active": "true", "closed": "false"}
    url = f"{GAMMA_MARKETS_URL}?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": "poly_strategy-snapshot/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def project_market(m: dict, snapshot_ts: str, fee_rate_default: float) -> dict | None:
    """Extract the stable subset of fields we need. Returns None if degenerate."""
    nrid = m.get("negRiskMarketID") or m.get("neg_risk_market_id")
    if not nrid or not m.get("negRisk"):
        return None

    ask = to_float(m.get("bestAsk"))
    bid = to_float(m.get("bestBid"))
    vol24 = (
        to_float(m.get("volume24hr"), 0.0)
        or to_float(m.get("volume24hrClob"), 0.0)
        or 0.0
    )
    liq = (
        to_float(m.get("liquidityNum"), 0.0)
        or to_float(m.get("liquidityClob"), 0.0)
        or 0.0
    )
    fee_schedule = m.get("feeSchedule") or {}
    fee_rate = to_float(fee_schedule.get("rate"), fee_rate_default)
    fees_enabled = bool(m.get("feesEnabled", True))
    if not fees_enabled:
        fee_rate = 0.0
    question = m.get("question") or ""

    return {
        "snapshot_ts": snapshot_ts,
        "market_id": str(m.get("id") or "?"),
        "neg_risk_market_id": str(nrid),
        "question": question[:200],
        "best_ask": ask,
        "best_bid": bid,
        "vol24hr": vol24,
        "liquidity": liq,
        "fee_rate": fee_rate,
        "fees_enabled": fees_enabled,
        "close_time": m.get("endDate"),
        "is_other_marker": is_other_marker(question),
    }


def derive_groups(markets: list[dict], snapshot_ts: str) -> list[dict]:
    """Group markets by negRiskMarketID, compute tier + edge metrics per group."""
    by_group: dict[str, list[dict]] = defaultdict(list)
    for m in markets:
        by_group[m["neg_risk_market_id"]].append(m)

    rows: list[dict] = []
    for nrid, members in by_group.items():
        if len(members) < 2:
            continue
        # Drop degenerate: missing/extreme asks
        bad = any(
            (m["best_ask"] is None) or (m["best_ask"] <= 0.001) or (m["best_ask"] >= 0.999)
            for m in members
        )
        if bad:
            continue

        sum_ask = sum(m["best_ask"] for m in members)
        fee_total = sum(
            m["fee_rate"] * m["best_ask"] * (1 - m["best_ask"]) for m in members
        )
        edge_after_fee = 1.0 - sum_ask - fee_total

        flags = [m["is_other_marker"] for m in members]
        tier = classify_exhaustiveness(flags, len(members))

        rows.append({
            "snapshot_ts": snapshot_ts,
            "neg_risk_market_id": nrid,
            "size": len(members),
            "tier": tier,
            "sum_ask": round(sum_ask, 6),
            "fee_total": round(fee_total, 6),
            "edge_after_fee": round(edge_after_fee, 6),
            "has_longtail_member": any(m["vol24hr"] < 40.0 for m in members),
            "min_liquidity": round(min(m["liquidity"] for m in members), 2),
            "min_vol24hr": round(min(m["vol24hr"] for m in members), 2),
            "max_vol24hr": round(max(m["vol24hr"] for m in members), 2),
            "n_other_markers": sum(1 for f in flags if f),
            "member_ids": [m["market_id"] for m in members],
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=6, help="Pages to fetch (default 6 = up to 3000 markets)")
    ap.add_argument("--limit", type=int, default=500, help="Markets per page")
    ap.add_argument("--fee-rate-default", type=float, default=0.015)
    ap.add_argument("--out-root", type=Path, default=REPO_ROOT / "data" / "snapshots")
    args = ap.parse_args()

    now = datetime.now(tz=timezone.utc)
    snapshot_ts = now.isoformat()
    date_dir = now.strftime("%Y-%m-%d")
    time_dir = now.strftime("%H-%M")
    out_dir = args.out_root / date_dir / time_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    markets_path = out_dir / "markets.ndjson"
    groups_path = out_dir / "groups.ndjson"
    meta_path = out_dir / "meta.json"

    print(f"[snapshot {snapshot_ts}] fetching up to {args.pages} pages * {args.limit}...")
    t_start = time.time()
    raw_count = 0
    projected: list[dict] = []
    pages_ok = 0
    pages_failed: list[str] = []

    for page in range(args.pages):
        offset = page * args.limit
        t0 = time.time()
        try:
            batch = fetch_markets_page(args.limit, offset)
        except Exception as e:
            msg = f"page {page+1}/{args.pages} (offset={offset}) FAILED: {type(e).__name__}: {e}"
            print(f"  {msg}", file=sys.stderr)
            pages_failed.append(msg)
            continue
        elapsed = time.time() - t0
        raw_count += len(batch)
        n_proj_before = len(projected)
        for m in batch:
            row = project_market(m, snapshot_ts, args.fee_rate_default)
            if row is not None:
                projected.append(row)
        pages_ok += 1
        print(f"  page {page+1}/{args.pages}: raw={len(batch)} negRisk+={len(projected)-n_proj_before} t={elapsed:.1f}s")
        if not batch:
            print(f"  empty batch, stopping early")
            break

    # Write markets.ndjson
    with markets_path.open("w", encoding="utf-8") as f:
        for row in projected:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # Derive + write groups
    group_rows = derive_groups(projected, snapshot_ts)
    with groups_path.open("w", encoding="utf-8") as f:
        for row in group_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # Meta
    tiers = defaultdict(int)
    for g in group_rows:
        tiers[g["tier"]] += 1
    explicit_edge = [g for g in group_rows if g["tier"] == "explicit_other" and g["edge_after_fee"] > 0.05]
    elapsed_total = time.time() - t_start

    meta = {
        "snapshot_ts": snapshot_ts,
        "elapsed_seconds": round(elapsed_total, 2),
        "pages_requested": args.pages,
        "pages_ok": pages_ok,
        "pages_failed": pages_failed,
        "raw_markets_seen": raw_count,
        "neg_risk_markets_kept": len(projected),
        "groups_total": len(group_rows),
        "groups_explicit_other": tiers["explicit_other"],
        "groups_binary": tiers["binary"],
        "groups_open_set": tiers["open_set"],
        "explicit_other_with_edge_gt_5pct": len(explicit_edge),
    }
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"[snapshot {snapshot_ts}] done in {elapsed_total:.1f}s")
    print(f"  raw={raw_count}  negRisk_kept={len(projected)}  groups={len(group_rows)}")
    print(f"  explicit_other={tiers['explicit_other']}  binary={tiers['binary']}  open_set={tiers['open_set']}")
    print(f"  explicit_other with edge>5%: {len(explicit_edge)}")
    if pages_failed:
        print(f"  WARN: {len(pages_failed)} page(s) failed -- snapshot is partial", file=sys.stderr)
    print(f"  -> {markets_path}")
    print(f"  -> {groups_path}")
    print(f"  -> {meta_path}")
    return 0 if pages_ok > 0 else 2


if __name__ == "__main__":
    sys.exit(main())
