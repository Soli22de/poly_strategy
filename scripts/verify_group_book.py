#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate any neg-risk group's basket arb on real CLOB orderbook depth.

Generalization of verify_james_bond_book.py to any negRiskMarketID prefix.
Same algorithm: pull the group from Gamma, hit /book for each member's
YES tokenID, simulate basket fills at increasing sizes to find where
slippage destroys the edge.

Usage:
    python scripts/verify_group_book.py --group-id 0xa8574c0caacc
    python scripts/verify_group_book.py --group-id 0xb23e25438839 \\
        --basket-sizes 10,30,80,150

Output: reports/group-book-validation-<short>-<date>.md
        data/experiments/<date>/group-book-<short>-raw.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from research_simulation_utils import simulate_basket_fill

REPO_ROOT = Path(__file__).resolve().parent.parent
GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"
CLOB_BOOK_URL = "https://clob.polymarket.com/book"


def fetch_book(token_id: str, timeout: float = 30.0) -> dict:
    params = urlencode({"token_id": token_id})
    url = f"{CLOB_BOOK_URL}?{params}"
    req = Request(url, headers={"User-Agent": "poly_strategy-verify/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_group_members(prefix: str, max_pages: int = 6) -> list[dict]:
    """Pull today's Gamma /markets, return group members whose negRiskMarketID
    starts with `prefix`."""
    out: list[dict] = []
    for page in range(max_pages):
        params = urlencode({"limit": 500, "offset": page * 500,
                            "active": "true", "closed": "false"})
        url = f"{GAMMA_MARKETS_URL}?{params}"
        req = Request(url, headers={"User-Agent": "poly_strategy-verify/1.0"})
        with urlopen(req, timeout=30) as resp:
            batch = json.loads(resp.read().decode("utf-8"))
        if not batch:
            break
        for m in batch:
            nrid = str(m.get("negRiskMarketID") or "")
            if not nrid.startswith(prefix):
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
                "neg_risk_market_id": nrid,
                "question": m.get("question") or "",
                "yes_token_id": str(tokens[0]),
                "fee_rate": fee_rate,
                "best_ask_gamma": float(m.get("bestAsk") or 0.0),
                "best_bid_gamma": float(m.get("bestBid") or 0.0),
                "liquidity": float(m.get("liquidityNum") or m.get("liquidityClob") or 0.0),
                "vol24hr": float(m.get("volume24hr") or 0.0),
            })
    return out


def simulate_buy(asks: list[tuple[float, float]], target_units: float) -> tuple[float, float]:
    """Walk the ask ladder, return (units_filled, avg_price_paid)."""
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


def shorthand_from_questions(questions: list[str]) -> str:
    """Generate a filesystem-safe short name from member questions."""
    if not questions:
        return "unknown"
    q = questions[0]
    # Pull out a few key tokens: race name (state + senate/governor), or first 3 words
    words = re.findall(r"[A-Za-z0-9]+", q)
    pick = "-".join(words[:5]).lower()[:40]
    return pick or "group"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--group-id", required=True,
                    help="Prefix of negRiskMarketID to validate (e.g. 0xa8574c0caacc)")
    ap.add_argument("--basket-sizes", default="50,200,1000,5000",
                    help="Comma-separated basket sizes in units (= dollars of payout)")
    args = ap.parse_args()

    sizes = [float(s) for s in args.basket_sizes.split(",")]

    print(f"[1/3] Fetching group {args.group_id}... from Gamma...")
    members = fetch_group_members(args.group_id)
    if not members:
        print(f"ERROR: no members found for group prefix {args.group_id}", file=sys.stderr)
        return 2
    print(f"  {len(members)} members")
    short = shorthand_from_questions([m["question"] for m in members])

    print(f"[2/3] Fetching CLOB /book for each YES token...")
    book_data: list[dict] = []
    for i, m in enumerate(members, 1):
        try:
            book = fetch_book(m["yes_token_id"])
        except Exception as e:
            print(f"  [{i}/{len(members)}] FAIL: {e}", file=sys.stderr)
            book_data.append({"member": m, "asks": [], "bids": [], "error": str(e)})
            continue
        asks_raw = book.get("asks") or []
        bids_raw = book.get("bids") or []
        asks = sorted([(float(a["price"]), float(a["size"])) for a in asks_raw], key=lambda x: x[0])
        bids = sorted([(float(b["price"]), float(b["size"])) for b in bids_raw], key=lambda x: -x[0])
        best_ask = asks[0][0] if asks else None
        depth = asks[0][1] if asks else 0
        book_data.append({
            "member": m,
            "asks": asks,
            "bids": bids,
            "best_ask": best_ask,
            "best_bid": bids[0][0] if bids else None,
            "depth_at_bestAsk": depth,
        })
        print(f"  [{i:>2}/{len(members)}] {m['question'][:60]}: bestAsk={best_ask} depth={depth}")

    if any(b.get("best_ask") is None for b in book_data):
        print("WARNING: some members have no asks", file=sys.stderr)

    print(f"\n[3/3] Simulating fills at basket sizes: {sizes}")
    bestAsk_sum = sum(b.get("best_ask") or 1.0 for b in book_data)
    marginal_fee = sum(
        b["member"]["fee_rate"] * (b.get("best_ask") or 0) * (1 - (b.get("best_ask") or 0))
        for b in book_data
    )
    print(f"  marginal bestAsk basket sum (1 unit): {bestAsk_sum:.4f}")
    print(f"  marginal fee (1 unit):                {marginal_fee:.5f}")
    print(f"  marginal edge_after_fee:              {1.0 - bestAsk_sum - marginal_fee:+.4f}")
    print()

    size_rows = []
    for size in sizes:
        row = simulate_basket_fill(book_data, size)
        size_rows.append(row)
        executable = row["effective_size"]
        avg_cost = row["total_cost"] / executable if executable > 0 else 0.0
        status = "full" if row["is_full_size_fillable"] else "capped"
        print(f"  size={size:>5.0f}u : executable={executable:.2f}u  "
              f"avg_basket_cost={avg_cost:.4f}  fee={row['total_fee']:.4f}  "
              f"edge=${row['edge_dollars']:+,.2f} ({row['edge_pct']*100:+.2f}%)  {status}")

    now = datetime.now(tz=timezone.utc)
    iso = now.isoformat()
    date_tag = now.strftime("%Y-%m-%d")

    lines = [
        f"# Group Book Validation: {short} ({iso})",
        "",
        f"Real-orderbook depth check of basket arb candidate.",
        f"Group: `{args.group_id}...`  (members={len(members)})",
        "",
        "## Per-member top-of-book",
        "",
        "| # | Question | bestAsk | depth @ bestAsk | bestBid | gamma_ask | fee | vol24hr | liq |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
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
            f"| {m['fee_rate']:.3f} "
            f"| ${m['vol24hr']:,.0f} "
            f"| ${m['liquidity']:,.0f} |"
        )
    lines += [
        "",
        "## Marginal (1-unit) edge",
        "",
        f"- bestAsk basket sum: **{bestAsk_sum:.4f}**",
        f"- marginal fee: {marginal_fee:.5f}",
        f"- marginal edge_after_fee: **{1.0 - bestAsk_sum - marginal_fee:+.4f}**",
        "",
        "## Fill simulation",
        "",
        "Buy up to the requested units of EACH member. Executable size is capped by "
        "the thinnest leg's ask depth, because incomplete baskets do not pay the requested notional.",
        "",
        "| Requested size | Executable size | Avg basket cost | Total fee | Edge $ | Edge % | Full size? |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in size_rows:
        executable = r["effective_size"]
        avg_cost = r["total_cost"] / executable if executable > 0 else 0.0
        lines.append(
            f"| {r['requested_size']:.0f} "
            f"| {executable:.2f} "
            f"| {avg_cost:.4f} "
            f"| ${r['total_fee']:.2f} "
            f"| ${r['edge_dollars']:+,.2f} "
            f"| {r['edge_pct']*100:+.2f}% "
            f"| {'yes' if r['is_full_size_fillable'] else 'no'} |"
        )

    lines += [
        "",
        f"---\n*Snapshot: {iso}*",
    ]

    out_path = REPO_ROOT / "reports" / f"group-book-validation-{short}-{date_tag}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")

    data_dir = REPO_ROOT / "data" / "experiments" / date_tag
    data_dir.mkdir(parents=True, exist_ok=True)
    raw_path = data_dir / f"group-book-{short}-raw.json"
    with raw_path.open("w", encoding="utf-8") as f:
        json.dump({
            "snapshot_ts": iso,
            "group_id": args.group_id,
            "shorthand": short,
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
            "fill_simulation": size_rows,
        }, f, indent=2, ensure_ascii=False)

    print(f"\nreport: {out_path}")
    print(f"raw:    {raw_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
