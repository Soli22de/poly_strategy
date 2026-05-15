#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pull Kalshi markets by series, in the same NDJSON format that
poly_strategy.cross_platform expects.

The default `poly-strategy collect-kalshi` is dominated by KXMVE*/KXMVS*
parlay markets (98%+ of the first ~10,000 in pagination order). To get
real liquid markets you must query by event_ticker. This script picks
known-active series, lists their events, lists each event's markets, and
writes everything as `type: raw_kalshi_market` NDJSON rows.

Usage:
  python scripts/collect_kalshi_targeted.py --out data/kalshi-markets-targeted.ndjson
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
KALSHI_BASE = "https://external-api.kalshi.com/trade-api/v2"

# Series tickers known to host real (non-parlay) liquid markets. From observation:
# - Macro/economic: KXFED, KXCPI, KXJOBS, KXGDP, KXFEDRATEDEC
# - Crypto: KXBTC, KXETH, KXSOL
# - Politics: KXPRES (US presidential), KXSENATE, KXHOUSE, KXBALANCEPOWER
# - Sport championships (no game-by-game parlays): KXNBAFINALS, KXNFLSB,
#   KXWORLDCUPCHAMP, KXSTANLEYCUP, KXMLBWS
# - Other: KXIMPEACHMENT, KXSUPREMECT, KXNATSEC
DEFAULT_SERIES = [
    "KXFED", "KXCPI", "KXJOBS", "KXGDP", "KXFEDRATEDEC",
    "KXBTC", "KXETH", "KXSOL",
    "KXPRES", "KXSENATE", "KXHOUSE", "KXBALANCEPOWER",
    "KXNBAFINALS", "KXNFLSB", "KXWORLDCUP", "KXSTANLEYCUP", "KXMLBWS",
    "KXIMPEACHMENT", "KXSUPREMECT", "KXNATSEC", "KXNEWPOPE",
    "KXPGAR1LEAD", "KXNHL", "KXEUROVISION", "KXTRUMPACTIONS",
    "KXMUSKACTIONS", "KXAITECH", "KXSPACEX", "KXOPENAI",
]


def _fetch_json(url: str, timeout: float = 15.0, retries: int = 3) -> dict:
    for i in range(retries):
        try:
            req = Request(url, headers={"User-Agent": "poly_strategy-targeted-kalshi/1.0"})
            with urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            if i == retries - 1:
                return {}
            time.sleep(2 + i)
    return {}


def collect(series_list, out_path: Path, status: str = "open") -> int:
    rows_written = 0
    seen_tickers: set = set()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f_out:
        for series in series_list:
            params = urlencode({"series_ticker": series, "limit": 100, "status": status})
            d = _fetch_json(f"{KALSHI_BASE}/events?{params}")
            events = d.get("events", []) or []
            print(f"  series={series:20s}  events={len(events)}")
            for e in events:
                event_ticker = str(e.get("event_ticker") or "").strip()
                if not event_ticker:
                    continue
                # Fetch all markets for this event
                params2 = urlencode({"event_ticker": event_ticker, "limit": 200, "status": status})
                d2 = _fetch_json(f"{KALSHI_BASE}/markets?{params2}")
                markets = d2.get("markets", []) or []
                for m in markets:
                    ticker = str(m.get("ticker") or "").strip()
                    if not ticker or ticker in seen_tickers:
                        continue
                    # Inject series info because the markets endpoint may not return it
                    if not m.get("series_ticker"):
                        m["series_ticker"] = series
                    if not m.get("event_ticker"):
                        m["event_ticker"] = event_ticker
                    if not m.get("event_title"):
                        m["event_title"] = e.get("title", "")
                    if not m.get("category"):
                        m["category"] = e.get("category", "")
                    row = {
                        "market_id": ticker,
                        "raw": m,
                        "ts": datetime.now(tz=timezone.utc).isoformat(),
                        "type": "raw_kalshi_market",
                    }
                    f_out.write(json.dumps(row, ensure_ascii=False) + "\n")
                    seen_tickers.add(ticker)
                    rows_written += 1
    return rows_written


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--series", action="append", default=None,
                    help="Kalshi series ticker (e.g. KXFED). Repeatable. Defaults to DEFAULT_SERIES.")
    ap.add_argument("--status", default="open")
    args = ap.parse_args()

    series_list = args.series if args.series else DEFAULT_SERIES
    print(f"Pulling Kalshi markets for {len(series_list)} series via /events → /markets")
    n = collect(series_list, args.out, status=args.status)
    print(f"\nwrote={n} out={args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
