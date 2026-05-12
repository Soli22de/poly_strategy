#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate the James Bond explicit_other arb on real CLOB orderbook depth.

The 14-day backfill said this group had multi-day mid-price edges of
+9% to +18%. Mid is an upper bound on real fillable edge -- bestAsk is
always >= mid, so the true tradeable edge is smaller. This script
quantifies HOW MUCH smaller by hitting the CLOB /book endpoint for
each member and simulating fills at increasing basket sizes.

What we compute:
  - bestAsk_sum_now: sum of current top-of-book ask across all 15 members
                    (= cost to buy 1 unit of basket at marginal prices)
  - depth_at_bestAsk: how many units you could fill at current bestAsk
  - avg_basket_cost(N): average cost-per-unit when buying N units of basket
                       (walks up the ask ladder, eats slippage)
  - edge_after_fee(N): 1 - avg_basket_cost(N) - sum(fees)
  - depth_constrained_max_size: largest N where edge_after_fee > 0

Outputs:
  reports/james-bond-book-validation-<date>.md
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"
CLOB_BOOK_URL = "https://clob.polymarket.com/book"

JAMES_BOND_GROUP = "0xb23e25438839"  # prefix; full ID has more chars


def fetch_book(token_id: str, timeout: float = 30.0) -> dict:
    params = urlencode({"token_id": token_id})
    url = f"{CLOB_BOOK_URL}?{params}"
    req = Request(url, headers={"User-Agent": "poly_strategy-verify/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_james_bond_markets(prefix: str) -> list[dict]:
    """Pull today's Gamma /markets, return JB group members with their YES tokens."""
    out: list[dict] = []
    for page in range(6):
        params = urlencode({"limit": 500, "offset": page * 500, "active": "true", "closed": "false"})
        url = f"{GAMMA_MARKETS_URL}?{params}"
        req = Request(url, headers={"User-Agent": "poly_strategy-verify/1.0"})
        with urlopen(req, timeout=30) as resp:
            batch = json.loads(resp.read().decode("utf-8"))
        if not batch:
            break
        for m in batch:
            nrid = m.get("negRiskMarketID") or ""
            if not str(nrid).startswith(prefix):
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
            out.append({
                "market_id": str(m.get("id")),
                "question": m.get("question") or "",
                "yes_token_id": str(tokens[0]),
                "fee_rate": fee_rate,
                "best_ask_gamma": float(m.get("bestAsk") or 0.0),
                "best_bid_gamma": float(m.get("bestBid") or 0.0),
                "liquidity": float(m.get("liquidityNum") or m.get("liquidityClob") or 0.0),
            })
        if len(out) >= 15:
            break
    return out


def simulate_buy(asks: list[tuple[float, float]], target_units: float) -> tuple[float, float]:
    """Walk the ask ladder, return (units_filled, avg_price_paid).
    asks is sorted ascending. Each entry is (price, size_at_that_level)."""
    filled = 0.0
    cost = 0.0
    for price, size in asks:
        if filled >= target_units:
            break
        take = min(size, target_units - filled)
        cost += take * price
        filled += take
    if filled == 0:
        return 0.0, 0.0
    return filled, cost / filled


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--basket-sizes", default="50,200,1000,5000",
                    help="Comma-separated basket sizes in units (= dollars payout)")
    args = ap.parse_args()

    sizes = [float(s) for s in args.basket_sizes.split(",")]

    print(f"[1/3] Fetching James Bond group from Gamma...")
    members = fetch_james_bond_markets(JAMES_BOND_GROUP)
    if not members:
        print(f"ERROR: no James Bond members found", file=sys.stderr)
        return 2
    print(f"  {len(members)} members")

    print(f"[2/3] Fetching CLOB /book for each YES token...")
    book_data: list[dict] = []
    for i, m in enumerate(members, 1):
        try:
            book = fetch_book(m["yes_token_id"])
        except Exception as e:
            print(f"  [{i}/{len(members)}] {m['question'][:40]}... FAIL: {e}", file=sys.stderr)
            book_data.append({"member": m, "asks": [], "bids": [], "error": str(e)})
            continue
        # Asks/bids come as list of {"price": "0.016", "size": "100"}
        asks_raw = book.get("asks") or []
        bids_raw = book.get("bids") or []
        asks = sorted([(float(a["price"]), float(a["size"])) for a in asks_raw], key=lambda x: x[0])
        bids = sorted([(float(b["price"]), float(b["size"])) for b in bids_raw], key=lambda x: -x[0])
        best_ask = asks[0][0] if asks else None
        best_bid = bids[0][0] if bids else None
        depth_at_ba = asks[0][1] if asks else 0
        book_data.append({
            "member": m,
            "asks": asks,
            "bids": bids,
            "best_ask": best_ask,
            "best_bid": best_bid,
            "depth_at_bestAsk": depth_at_ba,
        })
        print(f"  [{i:>2}/{len(members)}] {m['question'][:50]}: bestAsk={best_ask} depth={depth_at_ba}")

    # Marginal basket cost (sum of top-of-book asks)
    if any(b.get("best_ask") is None for b in book_data):
        print("WARNING: some members have no asks - basket arb infeasible right now", file=sys.stderr)

    print(f"\n[3/3] Simulating fills at basket sizes: {sizes}")
    rows = []
    bestAsk_sum = sum(b["best_ask"] or 1.0 for b in book_data)
    marginal_fee = sum(
        b["member"]["fee_rate"] * (b["best_ask"] or 0) * (1 - (b["best_ask"] or 0))
        for b in book_data
    )
    print(f"  marginal bestAsk basket sum (1 unit): {bestAsk_sum:.4f}")
    print(f"  marginal fee (1 unit):                {marginal_fee:.5f}")
    print(f"  marginal edge_after_fee:              {1.0 - bestAsk_sum - marginal_fee:+.4f}")
    print()

    size_rows = []
    for size in sizes:
        total_cost = 0.0
        total_fee = 0.0
        max_fillable = float("inf")
        per_member: list[dict] = []
        for b in book_data:
            filled, avg_px = simulate_buy(b["asks"], size)
            max_fillable = min(max_fillable, filled)
            cost = avg_px * size  # buy `size` units at avg_px (capped by available depth)
            fee = b["member"]["fee_rate"] * avg_px * (1 - avg_px) * size
            total_cost += cost
            total_fee += fee
            per_member.append({"member": b["member"]["question"][:40], "filled": filled, "avg_px": avg_px})

        edge_dollars = size - total_cost - total_fee
        edge_pct = (edge_dollars / size) if size > 0 else 0.0
        size_rows.append({
            "size": size,
            "max_fillable_units": max_fillable,
            "total_cost": total_cost,
            "total_fee": total_fee,
            "edge_dollars": edge_dollars,
            "edge_pct": edge_pct,
            "per_member": per_member,
        })
        print(f"  size={size:>5.0f}u : avg_basket_cost={total_cost/size:.4f}  fee={total_fee:.4f}  edge=${edge_dollars:+,.2f} ({edge_pct*100:+.2f}%)  max_fillable={max_fillable:.0f}u")

    # Render report
    now = datetime.now(tz=timezone.utc)
    iso = now.isoformat()
    date_tag = now.strftime("%Y-%m-%d")

    lines = [
        f"# James Bond CLOB Book Validation ({iso})",
        "",
        f"Real-orderbook check of the long-tail explicit_other arb candidate.",
        f"This is the truth test of the +8.93% mid-edge the backfill found.",
        "",
        f"Group: `{JAMES_BOND_GROUP}...`  (size={len(members)})",
        "",
        "## Per-member top-of-book",
        "",
        "| # | Question | bestAsk | depth @ bestAsk | bestBid | gamma_ask | fee_rate |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for i, b in enumerate(book_data, 1):
        m = b["member"]
        ba = b.get("best_ask")
        bb = b.get("best_bid")
        d = b.get("depth_at_bestAsk", 0)
        lines.append(
            f"| {i} | {m['question'][:55]} "
            f"| {ba if ba is not None else '—'} "
            f"| {d:.0f} "
            f"| {bb if bb is not None else '—'} "
            f"| {m['best_ask_gamma']:.4f} "
            f"| {m['fee_rate']:.3f} |"
        )

    lines += [
        "",
        f"## Marginal (1-unit) edge",
        "",
        f"- bestAsk basket sum:    **{bestAsk_sum:.4f}**",
        f"- marginal fee:          {marginal_fee:.5f}",
        f"- marginal edge_after_fee: **{1.0 - bestAsk_sum - marginal_fee:+.4f}**",
        "",
        f"(For comparison: Gamma snapshot mid-based edge was around +0.0893)",
        "",
        "## Fill simulation",
        "",
        "Buy `size` units of EACH member (so basket payout = size when one wins). "
        "Avg basket cost walks up each ask ladder. Edge after fee is the realized dollar profit.",
        "",
        "| Basket size (units = $payout) | Avg basket cost | Total fee | Edge $ | Edge % | Max fillable units |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for r in size_rows:
        lines.append(
            f"| {r['size']:.0f} "
            f"| {r['total_cost']/r['size']:.4f} "
            f"| ${r['total_fee']:.2f} "
            f"| ${r['edge_dollars']:+,.2f} "
            f"| {r['edge_pct']*100:+.2f}% "
            f"| {r['max_fillable_units']:.0f} |"
        )

    lines += [
        "",
        "## How to read this",
        "",
        "- `Max fillable units` = the size at which the thinnest member's ask ladder runs out. If you order more than this, the basket can't be assembled at any price (book is empty above).",
        "- `Edge %` is the actual return on the bought basket if exactly one member wins (which is the explicit_other assumption).",
        "- A positive edge here = bestAsk-tradeable arb. A negative edge here = the backfill mid-edge was an artifact of bid-ask spread.",
        "- Real-world frictions NOT modeled: gas, withdrawal cost, time-to-resolution opportunity cost, neg-risk adapter contract behavior.",
        "",
        f"---\n*Snapshot: {iso}*",
    ]

    out_path = REPO_ROOT / "reports" / f"james-bond-book-validation-{date_tag}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")

    # Also dump raw book data for forensics
    data_dir = REPO_ROOT / "data" / "experiments" / date_tag
    data_dir.mkdir(parents=True, exist_ok=True)
    raw_path = data_dir / "james-bond-books-raw.json"
    raw_dump = {
        "snapshot_ts": iso,
        "members": [
            {
                "market_id": b["member"]["market_id"],
                "question": b["member"]["question"],
                "yes_token_id": b["member"]["yes_token_id"],
                "asks": b["asks"][:10],
                "bids": b["bids"][:5],
                "best_ask": b.get("best_ask"),
                "depth_at_bestAsk": b.get("depth_at_bestAsk", 0),
            }
            for b in book_data
        ],
        "bestAsk_basket_sum": bestAsk_sum,
        "marginal_edge_after_fee": 1.0 - bestAsk_sum - marginal_fee,
        "fill_simulation": [{k: v for k, v in r.items() if k != "per_member"} for r in size_rows],
    }
    with raw_path.open("w", encoding="utf-8") as f:
        json.dump(raw_dump, f, indent=2, ensure_ascii=False)

    print(f"\nreport: {out_path}")
    print(f"raw:    {raw_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
