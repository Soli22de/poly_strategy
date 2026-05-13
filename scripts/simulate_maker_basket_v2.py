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

    # Build per-leg per-day min trade price
    leg_day_min_price: dict[str, dict[str, float]] = {}
    leg_day_total_sell_size: dict[str, dict[str, float]] = {}
    for cond_id, trades in filtered_trades.items():
        d_min: dict[str, float] = {}
        d_size: dict[str, float] = defaultdict(float)
        for t in trades:
            d = day_of_ts(t["timestamp"])
            p = float(t["price"])
            if d not in d_min or p < d_min[d]:
                d_min[d] = p
            d_size[d] += float(t["size"])
        leg_day_min_price[cond_id] = d_min
        leg_day_total_sell_size[cond_id] = dict(d_size)

    results: dict[str, dict] = {}
    for gid, members in target_groups.items():
        markup_stats: dict[float, dict] = {}
        for markup in markups:
            targets: list[float] = []
            for m in members:
                t = m["best_ask"] - markup
                t = max(t, m["best_bid"] + 0.001)
                targets.append(t)
            filled_days: list[dict] = []
            for d in all_days:
                fills = []
                sizes = []
                for m, target in zip(members, targets):
                    cond = m["condition_id"]
                    min_p = leg_day_min_price.get(cond, {}).get(d)
                    if min_p is None or min_p > target:
                        fills.append(False)
                        sizes.append(0.0)
                    else:
                        fills.append(True)
                        sizes.append(leg_day_total_sell_size.get(cond, {}).get(d, 0.0))
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
            expected_daily_edge_dollars = (
                fill_rate * avg_edge * args.basket_size if edges else 0.0
            )
            markup_stats[markup] = {
                "targets": [round(t, 4) for t in targets],
                "n_filled_days": n_filled,
                "n_total_days": n_total,
                "fill_rate": fill_rate,
                "avg_edge_given_fill": avg_edge,
                "median_edge_given_fill": median_edge,
                "expected_daily_edge_dollars": expected_daily_edge_dollars,
                "avg_min_leg_sell_size": avg_min_sell_size,
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
        f"**Method**: real Polymarket trade tape. For each (group, day, markup), check if any SELL Yes trade at price <= target occurred on each leg that day. If ALL legs had a qualifying trade, basket fills.",
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
        f"- Total expected daily income: **${total_expected_daily:+,.2f}/day** across {len(results)} groups @ ${args.basket_size:.0f} basket",
        f"- Annualized: **${total_expected_annual:+,.0f}/yr**",
        f"- Groups with positive expected income at any markup: **{n_groups_positive}/{len(results)}**",
        "",
        "## Top 20 by best expected daily income (v2)",
        "",
        "| Group | Q | Best markup | Fill rate | Avg edge | Avg sell size | Exp daily $ |",
        "|---|---|---:|---:|---:|---:|---:|",
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
        "- Still optimistic: assumes (a) our resting bid was first in queue, (b) our size was always available, (c) per-leg fills are independent within a day.",
        "- avg_min_leg_sell_size = avg of (min sell-size across legs on filled days). If this is < intended basket size, we couldn't have filled in full.",
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
