#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Maker-strategy basket simulator v2 — uses actual trade tape.

v1 (simulate_maker_basket.py) used "did mid touch target_price on day d?" as a
proxy for fill. That over-estimates because mid touching the target doesn't
mean any actual trade happened at-or-below it.

v2 uses Polymarket's `data-api.polymarket.com/trades` endpoint to fetch the
real trade tape per leg, then filters to SELL trades on the YES outcome at
price <= target_price (the only trades that would have hit our resting maker
bid). This is the closest we can get to "would my limit order have filled"
without actually placing the order.

Inputs (built dynamically):
  - Today's Gamma /markets for member condition_ids + bestAsk/bestBid/feeRate
  - 14 days of /trades per leg's condition_id (paginated, client-filtered to
    14-day window)

Output:
  reports/maker-simulation-tradetape-<date>.md
  data/experiments/<date>/maker-simulation-tradetape-results.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from research_simulation_utils import (
    capped_expected_daily_edge,
    maker_target_price,
    qualifying_trade_size,
    zero_maker_stats,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"
TRADES_URL = "https://data-api.polymarket.com/trades"


def fetch_markets_page(limit: int, offset: int, timeout: float = 30.0) -> list[dict]:
    params = urlencode({"limit": limit, "offset": offset, "active": "true", "closed": "false"})
    url = f"{GAMMA_MARKETS_URL}?{params}"
    req = Request(url, headers={"User-Agent": "poly_strategy-sim2/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_trades_paginated(
    condition_id: str,
    cutoff_ts: int,
    page_size: int = 500,
    max_pages: int = 50,
    timeout: float = 30.0,
) -> list[dict]:
    """Fetch all trades for condition_id, paginate until trades go older than cutoff_ts.

    Note: /trades startTime/endTime params don't actually filter — we get the
    full history and slice client-side.
    """
    all_trades: list[dict] = []
    offset = 0
    for _ in range(max_pages):
        params = urlencode({"market": condition_id, "limit": str(page_size), "offset": str(offset)})
        url = f"{TRADES_URL}?{params}"
        req = Request(url, headers={"User-Agent": "poly_strategy-sim2/1.0"})
        try:
            with urlopen(req, timeout=timeout) as resp:
                page = json.loads(resp.read().decode("utf-8"))
        except Exception:
            break
        if not page:
            break
        all_trades.extend(page)
        # Check if oldest trade in this page is older than cutoff
        oldest_ts = min(t["timestamp"] for t in page)
        if oldest_ts < cutoff_ts:
            break
        offset += page_size
    return all_trades


def day_of_ts(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--markups", default="0.005,0.01,0.02,0.03,0.05")
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--basket-size", type=float, default=100)
    ap.add_argument("--min-trade-size", type=float, default=0.0,
                    help="Only count fills where trade size >= this. 0 = any.")
    args = ap.parse_args()
    markups = [float(x) for x in args.markups.split(",")]

    now_dt = datetime.now(tz=timezone.utc)
    cutoff_ts = int((now_dt - timedelta(days=args.days)).timestamp())
    end_ts = int(now_dt.timestamp())
    print(f"Window: {datetime.fromtimestamp(cutoff_ts, tz=timezone.utc).isoformat()}  ->  {now_dt.isoformat()}")

    # 1. Fetch Gamma markets, build meta + map market_id -> condition_id
    print(f"\n[1/4] Fetching today's Gamma markets...")
    metas: dict[str, dict] = {}
    for page in range(6):
        try:
            batch = fetch_markets_page(500, page * 500)
        except Exception as e:
            print(f"  page {page+1} FAILED: {e}", file=sys.stderr)
            continue
        if not batch:
            break
        for m in batch:
            nrid = str(m.get("negRiskMarketID") or "")
            if not nrid or not m.get("negRisk"):
                continue
            cond_id = m.get("conditionId")
            if not cond_id:
                continue
            raw = m.get("clobTokenIds")
            try:
                tokens = json.loads(raw) if isinstance(raw, str) else raw
            except (TypeError, json.JSONDecodeError):
                continue
            if not tokens:
                continue
            fee_schedule = m.get("feeSchedule") or {}
            fee_rate = float((fee_schedule.get("rate") or 0.015))
            if not m.get("feesEnabled", True):
                fee_rate = 0.0
            metas[str(m.get("id"))] = {
                "market_id": str(m.get("id")),
                "condition_id": str(cond_id),
                "neg_risk_market_id": nrid,
                "yes_token_id": str(tokens[0]),
                "question": (m.get("question") or "")[:200],
                "fee_rate": fee_rate,
                "best_ask": float(m.get("bestAsk") or 0.0),
                "best_bid": float(m.get("bestBid") or 0.0),
            }
    print(f"  total negRisk markets today: {len(metas)}")

    # 2. Load dvr classification
    cls_path = REPO_ROOT / "data" / "experiments" / "2026-05-13" / "binary-classification.json"
    if not cls_path.exists():
        cls_path = REPO_ROOT / "data" / "experiments" / "2026-05-12" / "binary-classification.json"
    cls = json.loads(cls_path.read_text(encoding="utf-8")) if cls_path.exists() else {}
    dvr_gids = {gid for gid, c in cls.items() if c.get("sub_tier") == "dvr"}

    # Build group -> members
    by_group: dict[str, list[dict]] = defaultdict(list)
    for m in metas.values():
        by_group[m["neg_risk_market_id"]].append(m)
    target_groups: dict[str, list[dict]] = {}
    for gid, members in by_group.items():
        if gid in dvr_gids and len(members) == 2:
            target_groups[gid] = members
        elif gid.startswith("0xb23e25438839"):
            target_groups[gid] = members
    print(f"  groups: {len(target_groups)}  legs to fetch trades for: {sum(len(ms) for ms in target_groups.values())}")

    # 3. Parallel-fetch trades per condition_id
    print(f"\n[2/4] Fetching trade tape per leg (workers={args.workers})...")
    all_legs = [m for ms in target_groups.values() for m in ms]
    leg_trades: dict[str, list[dict]] = {}
    completed = 0
    failures: list[str] = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        future_to_leg = {
            pool.submit(fetch_trades_paginated, m["condition_id"], cutoff_ts): m
            for m in all_legs
        }
        for fut in as_completed(future_to_leg):
            m = future_to_leg[fut]
            completed += 1
            try:
                leg_trades[m["condition_id"]] = fut.result()
            except Exception as e:
                failures.append(f"{m['condition_id'][:16]}: {type(e).__name__}: {e}")
                leg_trades[m["condition_id"]] = []
            if completed % 30 == 0 or completed == len(future_to_leg):
                n_trades = sum(len(v) for v in leg_trades.values())
                print(f"  {completed}/{len(future_to_leg)} legs ({time.time()-t0:.0f}s, {n_trades} total trades fetched)")

    # Filter to window + outcome=Yes + side=SELL (the trades that would hit our maker bid on YES)
    print(f"\n[3/4] Filtering to window, outcome=Yes, side=SELL...")
    filtered_trades: dict[str, list[dict]] = {}
    raw_total = 0
    kept_total = 0
    for cond_id, trades in leg_trades.items():
        raw_total += len(trades)
        kept = [
            t for t in trades
            if cutoff_ts <= t["timestamp"] <= end_ts
            and t.get("outcome") == "Yes"
            and t.get("side") == "SELL"
            and t.get("size", 0) >= args.min_trade_size
        ]
        filtered_trades[cond_id] = kept
        kept_total += len(kept)
    print(f"  {raw_total} raw trades -> {kept_total} qualified (SELL Yes in window)")

    # 4. For each (group, day, markup), simulate fills
    print(f"\n[4/4] Simulating maker fills with real trade tape...")
    all_days = sorted({day_of_ts(t["timestamp"]) for ts in filtered_trades.values() for t in ts})
    print(f"  {len(all_days)} distinct UTC days with qualifying trade activity")
    if not all_days:
        # Generate the days even if no fills
        cur = datetime.fromtimestamp(cutoff_ts, tz=timezone.utc).strftime("%Y-%m-%d")
        end = now_dt.strftime("%Y-%m-%d")
        all_days = sorted({cur, end})

    # Build per-leg per-day trade lists; target-specific size is computed later.
    leg_day_trades: dict[str, dict[str, list[dict]]] = {}
    for cond_id, trades in filtered_trades.items():
        by_day: dict[str, list[dict]] = defaultdict(list)
        for t in trades:
            by_day[day_of_ts(t["timestamp"])].append(t)
        leg_day_trades[cond_id] = dict(by_day)

    results: dict[str, dict] = {}
    for gid, members in target_groups.items():
        markup_stats: dict[float, dict] = {}
        for markup in markups:
            targets: list[float] = []
            for m in members:
                t = maker_target_price(m["best_bid"], m["best_ask"], markup)
                if t is None:
                    targets = []
                    break
                targets.append(t)
            if not targets:
                markup_stats[markup] = zero_maker_stats(len(all_days), "no_non_crossing_maker_quote")
                continue
            filled_days: list[dict] = []
            for d in all_days:
                fills = []
                sizes = []
                for m, target in zip(members, targets):
                    cond = m["condition_id"]
                    day_trades = leg_day_trades.get(cond, {}).get(d, [])
                    target_size = qualifying_trade_size(day_trades, target)
                    if target_size <= 0:
                        fills.append(False)
                        sizes.append(0.0)
                    else:
                        fills.append(True)
                        sizes.append(target_size)
                if all(fills):
                    basket_cost = sum(targets)
                    fee = sum(
                        m["fee_rate"] * t * (1 - t)
                        for m, t in zip(members, targets)
                    )
                    edge = 1.0 - basket_cost - fee
                    filled_days.append({
                        "day": d, "basket_cost": basket_cost, "fee": fee, "edge": edge,
                        "min_leg_sell_size": min(sizes) if sizes else 0.0,
                    })

            n_filled = len(filled_days)
            n_total = len(all_days)
            fill_rate = n_filled / n_total if n_total else 0.0
            edges = [f["edge"] for f in filled_days]
            avg_edge = statistics.mean(edges) if edges else 0.0
            median_edge = statistics.median(edges) if edges else 0.0
            avg_min_sell_size = statistics.mean([f["min_leg_sell_size"] for f in filled_days]) if filled_days else 0.0
            size_capped = capped_expected_daily_edge(filled_days, n_total, args.basket_size)
            markup_stats[markup] = {
                "targets": [round(t, 4) for t in targets],
                "n_filled_days": n_filled,
                "n_total_days": n_total,
                "fill_rate": fill_rate,
                "avg_edge_given_fill": avg_edge,
                "median_edge_given_fill": median_edge,
                "expected_daily_edge_dollars": size_capped["expected_daily_edge_dollars"],
                "avg_min_leg_sell_size": avg_min_sell_size,
                "avg_effective_basket_size": size_capped["avg_effective_basket_size"],
                "max_effective_basket_size": size_capped["max_effective_basket_size"],
                "n_positive_edge_days": sum(1 for e in edges if e > 0),
                "n_negative_edge_days": sum(1 for e in edges if e <= 0),
            }

        q_short = " vs ".join([m["question"][:30] for m in members])
        bestAsk_sum_today = sum(m["best_ask"] for m in members)
        results[gid] = {
            "neg_risk_market_id": gid,
            "members": [m["question"][:80] for m in members],
            "question_short": q_short,
            "today_bestAsk_sum": bestAsk_sum_today,
            "today_bestBid_sum": sum(m["best_bid"] for m in members),
            "today_spread": bestAsk_sum_today - sum(m["best_bid"] for m in members),
            "markup_stats": markup_stats,
        }

    # 5. Report
    now = datetime.now(tz=timezone.utc)
    iso = now.isoformat()
    date_tag = now.strftime("%Y-%m-%d")

    def best_markup_income(r: dict) -> float:
        return max(s["expected_daily_edge_dollars"] for s in r["markup_stats"].values())

    sorted_groups = sorted(results.values(), key=best_markup_income, reverse=True)
    total_expected_daily = sum(best_markup_income(r) for r in results.values())
    total_expected_annual = total_expected_daily * 365
    n_groups_positive = sum(1 for r in results.values() if best_markup_income(r) > 0)

    lines = [
        f"# Maker Simulation v2 — Trade Tape ({iso})",
        "",
        f"**Method**: real Polymarket trade tape. For each (group, day, markup), check if any SELL Yes trade at price <= target occurred on each leg that day. If ALL legs had a qualifying trade, basket fills up to the smallest at-or-below-target leg trade size.",
        "",
        f"**Window**: {args.days} days ({datetime.fromtimestamp(cutoff_ts, tz=timezone.utc).strftime('%Y-%m-%d')} -> {now.strftime('%Y-%m-%d')})",
        f"**Basket size**: ${args.basket_size:.0f}",
        f"**Trades fetched**: {raw_total} raw -> {kept_total} qualifying (SELL Yes in window)",
        f"**Days with activity**: {len(all_days)}",
        "",
        "## v1 (mid-touch) vs v2 (trade tape) comparison",
        "",
        "v1 mid-touch results from earlier today (see `maker-simulation-2026-05-13.md`):",
        "- Total daily $: $+42.59 across 72 groups",
        "- Annualized: $+15,546/yr",
        "- Caveat: mid touching != trade happening at that price",
        "",
        "## v2 results (this run)",
        "",
        f"- Total expected daily income: **${total_expected_daily:+,.2f}/day** across {len(results)} groups @ max ${args.basket_size:.0f} basket, capped by observed trade size",
        f"- Annualized: **${total_expected_annual:+,.0f}/yr**",
        f"- Groups with positive expected income at any markup: **{n_groups_positive}/{len(results)}**",
        "",
        "## Top 20 by best expected daily income (v2)",
        "",
        "| Group | Q | Best markup | Fill rate | Avg edge | Avg sell size | Avg exec size | Exp daily $ |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in sorted_groups[:20]:
        best_m = max(r["markup_stats"].items(), key=lambda kv: kv[1]["expected_daily_edge_dollars"])
        m_val, s = best_m
        gid_short = r["neg_risk_market_id"][:14]
        lines.append(
            f"| `{gid_short}...` "
            f"| {r['question_short'][:45]} "
            f"| ${m_val:.3f} "
            f"| {s['fill_rate']*100:.1f}% "
            f"| {s['avg_edge_given_fill']*100:+.3f}% "
            f"| {s['avg_min_leg_sell_size']:.0f} "
            f"| {s['avg_effective_basket_size']:.0f} "
            f"| ${s['expected_daily_edge_dollars']:+,.3f} |"
        )

    lines += [
        "",
        "## Markup-level aggregate (v2)",
        "",
        "| Markup | Avg fill rate | Avg edge given fill | Groups positive | Total daily $ |",
        "|---:|---:|---:|---:|---:|",
    ]
    for markup in markups:
        stats_at_markup = [r["markup_stats"][markup] for r in results.values()]
        avg_fr = statistics.mean(s["fill_rate"] for s in stats_at_markup)
        edges_when_filled = [s["avg_edge_given_fill"] for s in stats_at_markup if s["n_filled_days"] > 0]
        avg_e = statistics.mean(edges_when_filled) if edges_when_filled else 0.0
        n_pos = sum(1 for s in stats_at_markup if s["expected_daily_edge_dollars"] > 0)
        total_d = sum(s["expected_daily_edge_dollars"] for s in stats_at_markup)
        lines.append(
            f"| ${markup:.3f} | {avg_fr*100:.1f}% | {avg_e*100:+.3f}% | {n_pos}/{len(stats_at_markup)} | ${total_d:+,.2f} |"
        )

    lines += [
        "",
        "## Notes",
        "",
        "- This uses the REAL trade tape — every SELL Yes trade in the past 14 days at price <= target is counted as a potential fill.",
        "- Still optimistic: assumes (a) our resting bid was first in queue, (b) same-day per-leg fills can be assembled into a completed basket, (c) per-leg fills are independent within a day.",
        "- Expected daily dollars are now capped by min(intended basket size, thinnest at-or-below-target leg sell size) on each filled day.",
        "- avg_min_leg_sell_size = avg of (min at-or-below-target sell-size across legs on filled days); avg_exec_size is the size actually used in PnL.",
        "- Maker fee assumed equal to taker fee_rate from feeSchedule. Polymarket maker fees may be lower or rebated — actual income could be HIGHER.",
        "- v2 vs v1 mismatch: v2 < v1 means mid-touch over-counts (less real trade activity at target); v2 > v1 means mid-touch under-counts (trades happened that mid-snapshot didn't capture).",
        "",
        f"---\n*Snapshot: {iso}*",
    ]

    report_path = REPO_ROOT / "reports" / f"maker-simulation-tradetape-{date_tag}.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")

    data_dir = REPO_ROOT / "data" / "experiments" / date_tag
    data_dir.mkdir(parents=True, exist_ok=True)
    json_path = data_dir / "maker-simulation-tradetape-results.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump({
            "snapshot_ts": iso,
            "window_days": args.days,
            "basket_size_usd": args.basket_size,
            "markups": markups,
            "n_groups": len(results),
            "n_raw_trades": raw_total,
            "n_qualifying_trades": kept_total,
            "n_failures": len(failures),
            "results": results,
        }, f, indent=2, ensure_ascii=False)

    print(f"\nreport: {report_path}")
    print(f"json:   {json_path}")
    print()
    print(f"=== Summary v2 (trade tape) ===")
    print(f"Groups simulated: {len(results)}")
    if sorted_groups:
        print(f"Best per-group expected daily $: ${best_markup_income(sorted_groups[0]):+,.3f}")
    print(f"Total expected daily $ (sum):    ${total_expected_daily:+,.2f}")
    print(f"Annualized:                       ${total_expected_annual:+,.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
