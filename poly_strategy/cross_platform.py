import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from poly_strategy.collectors import raw_gamma_markets_from_ndjson


def match_polymarket_kalshi_markets(
    polymarket_gamma_path: Path,
    kalshi_markets_path: Path,
    min_score: float = 0.35,
    top_n: int = 100,
) -> dict:
    if top_n < 0:
        raise ValueError("top_n must be non-negative")
    poly_markets = [_poly_market_row(market) for market in raw_gamma_markets_from_ndjson(polymarket_gamma_path)]
    kalshi_markets = list(_read_kalshi_markets(kalshi_markets_path))
    matches = []
    for poly in poly_markets:
        poly_tokens = _tokens(poly["title"])
        if not poly_tokens:
            continue
        for kalshi in kalshi_markets:
            score = _jaccard(poly_tokens, _tokens(kalshi["title"]))
            if score < min_score:
                continue
            matches.append(
                {
                    "polymarket_market_id": poly["market_id"],
                    "polymarket_title": poly["title"],
                    "kalshi_ticker": kalshi["ticker"],
                    "kalshi_title": kalshi["title"],
                    "score": score,
                    "status": "candidate_needs_manual_or_llm_verification",
                }
            )
    matches.sort(key=lambda row: (-row["score"], row["polymarket_market_id"], row["kalshi_ticker"]))
    return {
        "type": "cross_platform_match_report",
        "polymarket_gamma_path": str(polymarket_gamma_path),
        "kalshi_markets_path": str(kalshi_markets_path),
        "min_score": min_score,
        "match_count": len(matches),
        "top": matches[:top_n],
    }


def cross_platform_signal_rows(match_report: dict, source: str = "kalshi_matcher") -> list:
    rows = []
    for match in match_report.get("top", []):
        rows.append(
            {
                "source": source,
                "source_id": f"{match.get('polymarket_market_id')}:{match.get('kalshi_ticker')}",
                "kind": "cross_platform_candidate",
                "event_title": match.get("polymarket_title") or match.get("kalshi_title") or "",
                "quoted_edge": None,
                "quoted_roi": None,
                "legs": [
                    {"venue": "polymarket", "market_id": match.get("polymarket_market_id"), "token": "YES", "side": "buy"},
                    {"venue": "kalshi", "market_id": match.get("kalshi_ticker"), "token": "NO", "side": "buy"},
                ],
                "raw": match,
            }
        )
    return rows


def write_cross_platform_signal_rows(rows: Iterable[dict], out_path: Path) -> int:
    normalized = [_external_signal_row(row) for row in rows]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a") as handle:
        for row in normalized:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return len(normalized)


def _poly_market_row(market: dict) -> dict:
    return {
        "market_id": str(market.get("id") or market.get("conditionId") or ""),
        "title": str(market.get("question") or market.get("title") or ""),
    }


def _read_kalshi_markets(path: Path) -> Iterable[dict]:
    with path.open() as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("type") != "raw_kalshi_market":
                continue
            raw = row.get("raw") or {}
            ticker = str(row.get("market_id") or raw.get("ticker") or "").strip()
            title = str(raw.get("title") or raw.get("event_title") or raw.get("subtitle") or "").strip()
            if ticker and title:
                yield {"ticker": ticker, "title": title, "raw": raw}


def _tokens(text: str) -> set:
    words = re.findall(r"[a-z0-9]+", text.lower())
    stop = {"will", "the", "a", "an", "of", "to", "in", "on", "by", "before", "after", "or", "and", "be"}
    return {word for word in words if len(word) > 2 and word not in stop}


def _jaccard(first: set, second: set) -> float:
    if not first or not second:
        return 0.0
    return len(first & second) / len(first | second)


def _external_signal_row(row: dict) -> dict:
    return {
        "type": "external_signal",
        "schema_version": 1,
        "ingested_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": row.get("source") or "kalshi_matcher",
        "source_id": row.get("source_id"),
        "ts": None,
        "kind": row.get("kind") or "cross_platform_candidate",
        "event_title": row.get("event_title") or "",
        "quoted_edge": row.get("quoted_edge"),
        "quoted_roi": row.get("quoted_roi"),
        "quoted_depth": None,
        "legs": row.get("legs") or [],
        "raw": row.get("raw") or row,
    }
