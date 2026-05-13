#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Maker-strategy basket simulator.

The previous (taker) depth check showed ~$0.52/event max profit for SC Gov D/R.
That tested ONE thing only: buying the basket at current bestAsk in one shot.
This script tests a different thing: POSTING limit-buys at maker prices (below
current bestAsk, slightly above bestBid) and tracking whether all legs would
have filled across 14 days of mid-price history.

The thesis question:
    If the +2.55% "persistent edge floor" we see is actually market-makers'
    spread income on this thin book, can WE be that market-maker?

Method:
    1. For each dvr neg-risk group + James Bond group:
        - Get today's bestBid / bestAsk per leg (from Gamma)
        - Compute candidate maker_price = bestBid + epsilon for various epsilons
    2. Fetch raw /prices-history (no fidelity) for each leg's YES token over
       past 14 days. Each token returns ~10s-30k mid-price tick points.
    3. For each (group, day_d, markup_level): compute per-leg fill prob =
       (1 if mid touched maker_price at some point during day d else 0).
       Basket fills only when ALL legs fill that day.
    4. Aggregate: per-group P(basket_fill_per_day) × edge_given_fill =
       expected daily income.

Critical caveats (write these into the report explicitly):
    - mid touching maker_price is a proxy for fill, not a guarantee. Real fill
      requires someone to take our resting order.
    - We treat per-leg fill events as independent within a day. For markets
      that move in correlated ways this overestimates basket fill rate.
    - bestBid/bestAsk today is used as reference; historical spread may have
      differed.
    - Maker fees may be 0 or negative (rebates) but we conservatively use the
      same fee_rate as taker — actual maker income would be HIGHER than this
      simulation suggests.

Output:
    reports/maker-simulation-<date>.md
    data/experiments/<date>/maker-simulation-results.json
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
PRICES_HISTORY_URL = "https://clob.polymarket.com/prices-history"
SNAPSHOTS_ROOT = REPO_ROOT / "data" / "snapshots"


def load_ndjson(p: Path) -> list[dict]:
    rows = []
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


def fetch_markets_page(limit: int, offset: int, timeout: float = 30.0) -> list[dict]:
    params = urlencode({"limit": limit, "offset": offset, "active": "true", "closed": "false"})
    url = f"{GAMMA_MARKETS_URL}?{params}"
    req = Request(url, headers={"User-Agent": "poly_strategy-maker-sim/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_raw_ticks(
    token_id: str, start_ts: int, end_ts: int, timeout: float = 30.0
) -> list[tuple[int, float]]:
    """Fetch full mid-price tick history for a token. No fidelity = all changes."""
    params = urlencode({
        "market": token_id,
        "startTs": str(start_ts),
        "endTs": str(end_ts),
    })
    url = f"{PRICES_HISTORY_URL}?{params}"
    req = Request(url, headers={"User-Agent": "poly_strategy-maker-sim/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    pts = data.get("history") or []
    return sorted(((int(p["t"]), float(p["p"])) for p in pts), key=lambda x: x[0])


def day_of_ts(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def min_mid_per_day(ticks: list[tuple[int, float]]) -> dict[str, float]:
    """Bucket ticks by UTC day, return per-day min mid."""
    by_day: dict[str, float] = {}
    for ts, p in ticks:
        d = day_of_ts(ts)
        if d not in by_day or p < by_day[d]:
            by_day[d] = p
    return by_day


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--markups", default="0.005,0.01,0.02,0.03,0.05",
                    help="Maker price = bestAsk - markup. Comma separated, in price units.")
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--basket-size", type=float, default=100,
                    help="Hypothetical basket size in $payout for income estimate")
    args = ap.parse_args()
    markups = [float(x) for x in args.markups.split(",")]

    now_dt = datetime.now(tz=timezone.utc)
    end_ts = int(now_dt.timestamp())
    start_ts = int((now_dt - timedelta(days=args.days)).timestamp())

    # 1. Get today's live markets + their question / fees / bestBid / bestAsk
    print(f"[1/4] Fetching today's Gamma markets...")
    metas: dict[str, dict] = {}  # market_id -> static metadata
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
                "neg_risk_market_id": nrid,
                "yes_token_id": str(tokens[0]),
                "question": (m.get("question") or "")[:200],
                "fee_rate": fee_rate,
                "best_ask": float(m.get("bestAsk") or 0.0),
                "best_bid": float(m.get("bestBid") or 0.0),
            }
    print(f"  total negRisk markets today: {len(metas)}")

    # 2. Load dvr classification + identify groups to simulate
    cls_path = REPO_ROOT / "data" / "experiments" / "2026-05-13" / "binary-classification.json"
    if not cls_path.exists():
        cls_path = REPO_ROOT / "data" / "experiments" / "2026-05-12" / "binary-classification.json"
    cls = json.loads(cls_path.read_text(encoding="utf-8")) if cls_path.exists() else {}
    dvr_gids = {gid for gid, c in cls.items() if c.get("sub_tier") == "dvr"}
    print(f"  dvr classifications loaded: {len(dvr_gids)} groups")

    # Build group -> members map (today's view)
    by_group: dict[str, list[dict]] = defaultdict(list)
    for m in metas.values():
        by_group[m["neg_risk_market_id"]].append(m)

    target_groups: dict[str, list[dict]] = {}
    for gid, members in by_group.items():
        if gid in dvr_gids and len(members) == 2:
            target_groups[gid] = members
        elif gid.startswith("0xb23e25438839"):  # James Bond
            target_groups[gid] = members

    print(f"  groups to simulate: {len(target_groups)} ({len(dvr_gids & set(target_groups))} dvr + 1 explicit_other)")
    all_tokens = [m["yes_token_id"] for ms in target_groups.values() for m in ms]
    print(f"  tokens to fetch: {len(all_tokens)}")

    # 3. Parallel-fetch raw tick history for all tokens
    print(f"\n[2/4] Fetching raw /prices-history ticks (workers={args.workers})...")
    histories: dict[str, list[tuple[int, float]]] = {}
    failures: list[str] = []
    completed = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        future_to_tok = {
            pool.submit(fetch_raw_ticks, tok, start_ts, end_ts): tok
            for tok in all_tokens
        }
        for fut in as_completed(future_to_tok):
            tok = future_to_tok[fut]
            completed += 1
            try:
                histories[tok] = fut.result()
            except Exception as e:
                failures.append(f"{tok[:16]}: {type(e).__name__}: {e}")
                histories[tok] = []
            if completed % 50 == 0 or completed == len(future_to_tok):
                print(f"  {completed}/{len(future_to_tok)} done ({time.time()-t0:.0f}s, {len(failures)} failed)")
    n_points = sum(len(h) for h in histories.values())
    print(f"  done: {n_points} total tick points across {len(histories)} tokens")

    # 4. Simulate maker strategy
    print(f"\n[3/4] Simulating maker strategy at markups {markups}...")
    # All UTC days in window
    all_days = sorted({
        day_of_ts(ts)
        for ticks in histories.values()
        for ts, _ in ticks
    })
    print(f"  {len(all_days)} distinct UTC days seen")

    results: dict[str, dict] = {}  # group_id -> result dict
    for gid, members in target_groups.items():
        per_leg_min_per_day: list[dict[str, float]] = []
        for m in members:
            ticks = histories.get(m["yes_token_id"], [])
            per_leg_min_per_day.append(min_mid_per_day(ticks))

        # For each markup level, compute basket fill rate + avg basket edge
        markup_stats: dict[float, dict] = {}
        for markup in markups:
            # Maker target price per leg = today's bestAsk - markup (clamped >= bestBid)
            targets: list[float] = []
            for m in members:
                t = m["best_ask"] - markup
                # Don't go below today's bestBid (would never realistically fill)
                t = max(t, m["best_bid"] + 0.001)
                targets.append(t)

            filled_days: list[dict] = []
            for d in all_days:
                fills = []
                for leg_idx, mins in enumerate(per_leg_min_per_day):
                    leg_min = mins.get(d)
                    if leg_min is None:
                        fills.append(False)
                    else:
                        fills.append(leg_min <= targets[leg_idx])
                if all(fills):
                    basket_cost = sum(targets)
                    fee = sum(
                        m["fee_rate"] * t * (1 - t)
                        for m, t in zip(members, targets)
                    )
                    edge = 1.0 - basket_cost - fee
                    filled_days.append({"day": d, "basket_cost": basket_cost, "fee": fee, "edge": edge})

            n_days_total = len(all_days)
            n_filled = len(filled_days)
            fill_rate = n_filled / n_days_total if n_days_total else 0.0
            edges = [f["edge"] for f in filled_days]
            avg_edge = statistics.mean(edges) if edges else 0.0
            median_edge = statistics.median(edges) if edges else 0.0
            n_positive = sum(1 for e in edges if e > 0)
            n_neg = sum(1 for e in edges if e <= 0)
            # Expected daily income at given basket size
            expected_daily_edge_dollars = (
                fill_rate * avg_edge * args.basket_size if edges else 0.0
            )
            markup_stats[markup] = {
                "targets": [round(t, 4) for t in targets],
                "n_filled_days": n_filled,
                "n_total_days": n_days_total,
                "fill_rate": fill_rate,
                "avg_edge_given_fill": avg_edge,
                "median_edge_given_fill": median_edge,
                "n_positive_edge_days": n_positive,
                "n_negative_edge_days": n_neg,
                "expected_daily_edge_dollars": expected_daily_edge_dollars,
            }

        # Static metadata
        q_short = " vs ".join([m["question"][:30] for m in members])
        bestAsk_sum_today = sum(m["best_ask"] for m in members)
        bestBid_sum_today = sum(m["best_bid"] for m in members)
        results[gid] = {
            "neg_risk_market_id": gid,
            "members": [m["question"][:80] for m in members],
            "question_short": q_short,
            "today_bestAsk_sum": bestAsk_sum_today,
            "today_bestBid_sum": bestBid_sum_today,
            "today_spread": bestAsk_sum_today - bestBid_sum_today,
            "today_taker_edge": 1.0 - bestAsk_sum_today,
            "today_maker_edge_if_all_fill_at_bestBid": 1.0 - bestBid_sum_today,
            "markup_stats": markup_stats,
        }

    # 5. Aggregate + report
    print(f"\n[4/4] Rendering report...")
    now = datetime.now(tz=timezone.utc)
    iso = now.isoformat()
    date_tag = now.strftime("%Y-%m-%d")

    # Find best groups: highest expected daily $ at any markup
    def best_markup_income(r: dict) -> float:
        return max(s["expected_daily_edge_dollars"] for s in r["markup_stats"].values())

    sorted_groups = sorted(results.values(), key=best_markup_income, reverse=True)

    lines = [
        f"# Maker-strategy Basket Simulation ({iso})",
        "",
        f"**Method**: for each (group, UTC-day, markup-level), check if every leg's "
        f"mid-price touched (today's bestAsk - markup) at some point during the day. "
        f"If ALL legs filled, compute basket cost at maker target prices + fee. "
        f"Aggregate fill_rate * avg_edge as proxy for expected daily $income.",
        "",
        f"**Window**: {args.days} days, {len(all_days)} distinct UTC days seen in tick data.",
        f"**Basket size for $income estimate**: ${args.basket_size:.0f} of payout per fill.",
        "",
        "## Caveats (read first)",
        "",
        "- Mid-touching `target` is a proxy for fill, not a guarantee. Real fill requires someone to hit our resting order at that price.",
        "- Per-leg fill events treated as independent within a day. For correlated markets (D/R move together) this overestimates basket fill rate.",
        "- Today's bestAsk/bestBid used as reference; historical spread may differ.",
        "- Fee = taker rate from feeSchedule. Real maker fee may be 0 or negative (rebate), so this is a CONSERVATIVE estimate.",
        "",
        "## Top 20 groups by best expected daily income",
        "",
        "| Group | Q (short) | Best markup | Fill rate | Avg edge | Exp daily $ |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for r in sorted_groups[:20]:
        best_m = max(r["markup_stats"].items(), key=lambda kv: kv[1]["expected_daily_edge_dollars"])
        m_val = best_m[0]
        s = best_m[1]
        gid_short = r["neg_risk_market_id"][:14]
        lines.append(
            f"| `{gid_short}...` "
            f"| {r['question_short'][:55]} "
            f"| ${m_val:.3f} "
            f"| {s['fill_rate']*100:.1f}% "
            f"| {s['avg_edge_given_fill']*100:+.3f}% "
            f"| ${s['expected_daily_edge_dollars']:+,.3f} |"
        )

    # Total expected income across all groups
    total_expected_daily = sum(best_markup_income(r) for r in results.values())
    total_expected_annual = total_expected_daily * 365
    n_groups_positive = sum(1 for r in results.values() if best_markup_income(r) > 0)

    lines += [
        "",
        "## Aggregate (all groups combined)",
        "",
        f"- Total expected daily income (sum across {len(results)} groups, ${args.basket_size:.0f} basket each): **${total_expected_daily:+,.2f}/day**",
        f"- Annualized: **${total_expected_annual:+,.0f}/yr**",
        f"- Groups with positive expected income at any markup: **{n_groups_positive}/{len(results)}**",
        "",
        "## Markup-level summary (averaged across all groups)",
        "",
        "| Markup | Avg fill rate | Avg edge given fill | Groups with positive exp daily | Total exp daily $ |",
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
            f"| ${markup:.3f} "
            f"| {avg_fr*100:.1f}% "
            f"| {avg_e*100:+.3f}% "
            f"| {n_pos}/{len(stats_at_markup)} "
            f"| ${total_d:+,.2f} |"
        )

    lines += [
        "",
        "## Comparison to previous taker depth check",
        "",
        "Taker: SC Gov bestAsk basket, single $50 fill → +$0.52 profit (one-time).",
        "Taker: James Bond bestAsk basket, single $80 fill → +$3.78 profit (one-time).",
        "",
        f"Maker (this sim): ${total_expected_daily:+,.2f}/day across {len(results)} groups at $100 basket each = up to ${total_expected_daily * 365:+,.0f}/yr theoretical.",
        "",
        "Important: this is the OPTIMISTIC bound. Real fill rates are likely 2-5x lower than mid-touch rates because mid touching doesn't equal trade at that price.",
        "",
        f"---\n*Snapshot: {iso}*",
    ]

    report_path = REPO_ROOT / "reports" / f"maker-simulation-{date_tag}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")

    data_dir = REPO_ROOT / "data" / "experiments" / date_tag
    data_dir.mkdir(parents=True, exist_ok=True)
    json_path = data_dir / "maker-simulation-results.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump({
            "snapshot_ts": iso,
            "window_days": args.days,
            "basket_size_usd": args.basket_size,
            "markups": markups,
            "n_groups": len(results),
            "n_total_tick_points": n_points,
            "n_failures": len(failures),
            "results": results,
        }, f, indent=2, ensure_ascii=False)

    print(f"  report: {report_path}")
    print(f"  json:   {json_path}")
    print()
    print(f"=== Summary ===")
    print(f"Groups simulated:        {len(results)}")
    print(f"Best per-group expected daily $: ${best_markup_income(sorted_groups[0]):+,.3f}")
    print(f"Total expected daily $ (sum):    ${total_expected_daily:+,.2f}")
    print(f"Annualized:                       ${total_expected_annual:+,.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
