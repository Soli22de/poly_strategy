#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backfill 14-day synthetic snapshots from Polymarket CLOB prices-history.

PURPOSE
    Sneak-preview the arb persistence study before the live snapshot loop has
    14 days of data. Reconstructs per-15-min synthetic snapshots using mid
    prices from `/prices-history`, runs the same group classifier, writes
    groups.ndjson per slot under `data/snapshots/YYYY-MM-DD/HH-MM/` tagged
    with is_backfill=true.

CRITICAL CAVEATS
    1. Prices used are MID, not bestAsk. Real basket cost (sum of bestAsk)
       is strictly >= sum of mids. So edge_after_fee is SYSTEMATICALLY
       OVERSTATED. If even the mid-based backfill shows zero events
       crossing the 5% threshold, that's a hard kill on the long-tail
       thesis -- real bestAsk would only make edges smaller.
    2. Group membership is "today's groups projected back". If a market
       in a current group was added <14 days ago, older slots will have a
       missing member; the group is dropped at slots where any member
       lacks a price.
    3. liquidity / vol24hr / has_longtail_member fields are TODAY's
       values copied onto every historical row. They are NOT meaningful
       as time-varying signal -- use them only as approximate filters.
    4. /prices-history is a public endpoint, no auth, no rate limit
       documented. We use 5 parallel workers (anecdotally fine).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"
PRICES_HISTORY_URL = "https://clob.polymarket.com/prices-history"

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
    req = Request(url, headers={"User-Agent": "poly_strategy-backfill/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_price_history(
    token_id: str,
    start_ts: int,
    end_ts: int,
    fidelity: int = 900,
    timeout: float = 30.0,
    retries: int = 2,
) -> list[tuple[int, float]]:
    """Returns [(unix_ts, mid_price)] sorted ascending. Empty list if no data."""
    params = {
        "market": token_id,
        "fidelity": str(fidelity),
        "startTs": str(start_ts),
        "endTs": str(end_ts),
    }
    url = f"{PRICES_HISTORY_URL}?{urlencode(params)}"
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers={"User-Agent": "poly_strategy-backfill/1.0"})
            with urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            pts = data.get("history") or []
            return sorted(((int(p["t"]), float(p["p"])) for p in pts), key=lambda x: x[0])
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise last_err  # type: ignore[misc]


def collect_market_metadata(pages: int, limit: int, fee_default: float) -> list[dict]:
    """Pull every active negRisk market, return list of static metadata dicts."""
    metas: list[dict] = []
    for page in range(pages):
        offset = page * limit
        try:
            batch = fetch_markets_page(limit, offset)
        except Exception as e:
            print(f"  page {page+1}/{pages} FAILED: {e}", file=sys.stderr)
            continue
        if not batch:
            break
        for m in batch:
            nrid = m.get("negRiskMarketID") or m.get("neg_risk_market_id")
            if not nrid or not m.get("negRisk"):
                continue
            raw_tokens = m.get("clobTokenIds")
            if not raw_tokens:
                continue
            try:
                tokens = json.loads(raw_tokens) if isinstance(raw_tokens, str) else raw_tokens
            except (TypeError, json.JSONDecodeError):
                continue
            if not tokens or len(tokens) < 1:
                continue
            yes_token = str(tokens[0])

            fee_schedule = m.get("feeSchedule") or {}
            fee_rate = to_float(fee_schedule.get("rate"), fee_default)
            if not m.get("feesEnabled", True):
                fee_rate = 0.0

            question = m.get("question") or ""
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

            metas.append({
                "market_id": str(m.get("id") or "?"),
                "neg_risk_market_id": str(nrid),
                "yes_token_id": yes_token,
                "question": question[:200],
                "fee_rate": fee_rate,
                "is_other_marker": is_other_marker(question),
                "vol24hr_today": vol24,
                "liquidity_today": liq,
            })
        print(f"  page {page+1}/{pages}: total negRisk so far = {len(metas)}")
    return metas


def forward_fill_price(history: list[tuple[int, float]], target_ts: int) -> float | None:
    """Return latest price with t <= target_ts, or None if none."""
    if not history:
        return None
    lo, hi = 0, len(history) - 1
    if target_ts < history[0][0]:
        return None
    if target_ts >= history[-1][0]:
        return history[-1][1]
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if history[mid][0] <= target_ts:
            lo = mid
        else:
            hi = mid - 1
    return history[lo][1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--slot-minutes", type=int, default=15)
    ap.add_argument("--pages", type=int, default=6, help="Gamma pages to scan (default 6 = up to 3000 markets)")
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--fee-rate-default", type=float, default=0.015)
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--out-root", type=Path, default=REPO_ROOT / "data" / "snapshots")
    ap.add_argument("--max-markets", type=int, default=0, help="Cap markets fetched (0 = all). Use for quick tests.")
    ap.add_argument("--end-buffer-minutes", type=int, default=60,
                    help="Don't write slots in the last N minutes (live loop owns those).")
    args = ap.parse_args()

    now_dt = datetime.now(tz=timezone.utc)
    end_dt = (now_dt - timedelta(minutes=args.end_buffer_minutes)).replace(second=0, microsecond=0)
    end_dt = end_dt - timedelta(minutes=end_dt.minute % args.slot_minutes)
    start_dt = end_dt - timedelta(days=args.days)
    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())
    print(f"Backfill window: {start_dt.isoformat()}  ->  {end_dt.isoformat()}")
    print(f"  ({(end_ts - start_ts) // 60 // args.slot_minutes} slots at {args.slot_minutes}-min cadence)")

    # 1. Collect metadata
    print(f"\n[1/4] Fetching active negRisk markets ({args.pages} pages * {args.limit})...")
    metas = collect_market_metadata(args.pages, args.limit, args.fee_rate_default)
    if args.max_markets and len(metas) > args.max_markets:
        print(f"  --max-markets={args.max_markets} -> truncating from {len(metas)}")
        metas = metas[:args.max_markets]
    print(f"  total negRisk markets: {len(metas)}")
    # Build group membership map
    by_group: dict[str, list[dict]] = defaultdict(list)
    for m in metas:
        by_group[m["neg_risk_market_id"]].append(m)
    multi_group_meta = {gid: ms for gid, ms in by_group.items() if len(ms) >= 2}
    print(f"  neg-risk groups (>=2 members): {len(multi_group_meta)}")
    # Only fetch tokens that are in multi-member groups
    needed_tokens: dict[str, dict] = {}
    for gid, ms in multi_group_meta.items():
        for m in ms:
            needed_tokens[m["yes_token_id"]] = m
    print(f"  YES tokens to fetch: {len(needed_tokens)}")

    # 2. Parallel-fetch prices-history
    print(f"\n[2/4] Fetching prices-history (workers={args.workers})...")
    histories: dict[str, list[tuple[int, float]]] = {}
    failures: list[str] = []
    t0 = time.time()
    completed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        future_to_tok = {
            pool.submit(fetch_price_history, tok, start_ts, end_ts, 900): tok
            for tok in needed_tokens
        }
        for fut in as_completed(future_to_tok):
            tok = future_to_tok[fut]
            completed += 1
            try:
                histories[tok] = fut.result()
            except Exception as e:
                failures.append(f"{tok[:16]}...: {type(e).__name__}: {e}")
                histories[tok] = []
            if completed % 100 == 0 or completed == len(future_to_tok):
                elapsed = time.time() - t0
                print(f"  {completed}/{len(future_to_tok)} fetched ({elapsed:.0f}s, "
                      f"avg {1000*elapsed/max(completed,1):.0f}ms/req, fails={len(failures)})")
    n_pts = sum(len(h) for h in histories.values())
    print(f"  done: {len(histories)} tokens, {n_pts} total price points, {len(failures)} failures")
    if failures[:5]:
        print(f"  sample failures: {failures[:5]}")

    # 3. Build per-slot synthetic snapshots
    print(f"\n[3/4] Building synthetic snapshots ({args.slot_minutes}-min slots)...")
    slot_seconds = args.slot_minutes * 60
    n_slots_written = 0
    n_slots_empty = 0
    n_groups_total = 0
    n_explicit_with_edge = 0

    cur_ts = start_ts
    while cur_ts <= end_ts:
        slot_dt = datetime.fromtimestamp(cur_ts, tz=timezone.utc)
        slot_iso = slot_dt.isoformat()
        date_dir = slot_dt.strftime("%Y-%m-%d")
        time_dir = slot_dt.strftime("%H-%M")
        out_dir = args.out_root / date_dir / time_dir
        groups_path = out_dir / "groups.ndjson"
        if groups_path.exists():
            # Live loop or earlier backfill run already wrote this slot.
            cur_ts += slot_seconds
            continue

        group_rows: list[dict] = []
        for gid, members in multi_group_meta.items():
            prices: list[float | None] = []
            for m in members:
                hist = histories.get(m["yes_token_id"], [])
                p = forward_fill_price(hist, cur_ts)
                prices.append(p)
            # Drop slot if any member has no price (market didn't exist yet)
            if any(p is None for p in prices):
                continue
            # Drop degenerate (0 or 1 prices == resolved)
            if any(p <= 0.001 or p >= 0.999 for p in prices):
                continue

            sum_ask = sum(prices)
            fee_total = sum(
                m["fee_rate"] * p * (1 - p) for m, p in zip(members, prices)
            )
            edge_after_fee = 1.0 - sum_ask - fee_total
            flags = [m["is_other_marker"] for m in members]
            tier = classify_exhaustiveness(flags, len(members))

            # has_longtail / min_liquidity = today's values (stale, see caveats)
            has_lt = any(m["vol24hr_today"] < 40.0 for m in members)
            min_liq = min(m["liquidity_today"] for m in members)

            group_rows.append({
                "snapshot_ts": slot_iso,
                "neg_risk_market_id": gid,
                "size": len(members),
                "tier": tier,
                "sum_ask": round(sum_ask, 6),
                "fee_total": round(fee_total, 6),
                "edge_after_fee": round(edge_after_fee, 6),
                "has_longtail_member": has_lt,
                "min_liquidity": round(min_liq, 2),
                "min_vol24hr": 0.0,
                "max_vol24hr": 0.0,
                "n_other_markers": sum(1 for f in flags if f),
                "member_ids": [m["market_id"] for m in members],
                "is_backfill": True,
            })

        if not group_rows:
            n_slots_empty += 1
            cur_ts += slot_seconds
            continue

        out_dir.mkdir(parents=True, exist_ok=True)
        with groups_path.open("w", encoding="utf-8") as f:
            for row in group_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        n_slots_written += 1
        n_groups_total += len(group_rows)
        n_explicit_with_edge += sum(
            1 for r in group_rows
            if r["tier"] == "explicit_other" and r["edge_after_fee"] > 0.05
        )
        cur_ts += slot_seconds

    # 4. Summary
    print(f"\n[4/4] Done.")
    print(f"  slots written: {n_slots_written}")
    print(f"  slots empty (no groups had full data): {n_slots_empty}")
    print(f"  total backfilled group rows: {n_groups_total}")
    print(f"  explicit_other + edge>5% rows: {n_explicit_with_edge}")
    print(f"\nNext: python -u scripts/analyze_arb_events.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
