import json
import copy
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
            verification = _semantic_verification(poly["title"], kalshi["title"], score)
            matches.append(
                {
                    "polymarket_market_id": poly["market_id"],
                    "polymarket_title": poly["title"],
                    "kalshi_ticker": kalshi["ticker"],
                    "kalshi_title": kalshi["title"],
                    "score": score,
                    "status": verification["status"],
                    "trade_allowed": verification["trade_allowed"],
                    "semantic_verification": verification,
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


def cross_platform_signal_rows(match_report: dict, source: str = "kalshi_matcher", verified_only: bool = False) -> list:
    rows = []
    for match in match_report.get("top", []):
        trade_allowed = bool(match.get("trade_allowed"))
        if verified_only and not trade_allowed:
            continue
        kind = "cross_platform_same_binary_verified" if trade_allowed else "cross_platform_candidate_unverified"
        token = "BINARY" if trade_allowed else None
        rows.append(
            {
                "source": source,
                "source_id": f"{match.get('polymarket_market_id')}:{match.get('kalshi_ticker')}",
                "kind": kind,
                "event_title": match.get("polymarket_title") or match.get("kalshi_title") or "",
                "quoted_edge": None,
                "quoted_roi": None,
                "legs": [
                    {"venue": "polymarket", "market_id": match.get("polymarket_market_id"), "token": token, "side": "watch"},
                    {"venue": "kalshi", "market_id": match.get("kalshi_ticker"), "token": token, "side": "watch"},
                ],
                "raw": match,
            }
        )
    return rows


def cross_platform_pairs(match_report: dict, verified_only: bool = True) -> list:
    pairs = []
    for match in match_report.get("top", []):
        if verified_only and not match.get("trade_allowed"):
            continue
        poly_market_id = str(match.get("polymarket_market_id") or "").strip()
        kalshi_ticker = str(match.get("kalshi_ticker") or "").strip()
        if not poly_market_id or not kalshi_ticker:
            continue
        pairs.append(
            {
                "polymarket_market_id": poly_market_id,
                "kalshi_ticker": kalshi_ticker,
                "status": match.get("status"),
                "trade_allowed": bool(match.get("trade_allowed")),
                "score": match.get("score"),
                "polymarket_title": match.get("polymarket_title"),
                "kalshi_title": match.get("kalshi_title"),
            }
        )
    return pairs


def apply_cross_platform_verifications(match_report: dict, verifications: Iterable[dict]) -> dict:
    updated = copy.deepcopy(match_report)
    by_pair = {
        (str(row.get("polymarket_market_id") or ""), str(row.get("kalshi_ticker") or "")): row
        for row in verifications
    }
    verified_count = 0
    rejected_count = 0
    for match in updated.get("top", []):
        key = (str(match.get("polymarket_market_id") or ""), str(match.get("kalshi_ticker") or ""))
        verification = by_pair.get(key)
        if not verification:
            continue
        match["llm_verification"] = verification
        match["trade_allowed"] = bool(verification.get("trade_allowed"))
        if verification.get("trade_allowed"):
            verified_count += 1
            match["status"] = "verified_same_binary_event"
        else:
            rejected_count += 1
            match["status"] = "candidate_rejected_by_llm"
    updated["llm_verified_count"] = verified_count
    updated["llm_rejected_count"] = rejected_count
    return updated


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


def _semantic_verification(poly_title: str, kalshi_title: str, score: float) -> dict:
    poly_normalized = _normalize_semantic_title(poly_title)
    kalshi_normalized = _normalize_semantic_title(kalshi_title)
    risk_flags = []
    if not _numeric_tokens_match(poly_title, kalshi_title):
        risk_flags.append("numeric_mismatch")
    if _has_conditional_terms(poly_title) or _has_conditional_terms(kalshi_title):
        risk_flags.append("conditional_resolution_wording")

    exact_match = bool(poly_normalized and poly_normalized == kalshi_normalized)
    high_overlap = score >= 0.75 and _required_tokens_match(poly_title, kalshi_title)
    trade_allowed = (exact_match or high_overlap) and not risk_flags
    status = "verified_same_binary_event" if trade_allowed else "candidate_needs_llm_or_manual_verification"
    return {
        "status": status,
        "trade_allowed": trade_allowed,
        "score": score,
        "exact_normalized_title_match": exact_match,
        "numeric_tokens_match": "numeric_mismatch" not in risk_flags,
        "risk_flags": risk_flags,
    }


def _normalize_semantic_title(text: str) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())
    stop = {"will", "the", "a", "an", "of", "to", "in", "on", "by", "before", "after", "or", "and", "be"}
    return " ".join(word for word in words if word not in stop)


def _numeric_tokens_match(first: str, second: str) -> bool:
    return _numeric_tokens(first) == _numeric_tokens(second)


def _numeric_tokens(text: str) -> set:
    return {token.replace(",", "") for token in re.findall(r"\d[\d,]*(?:\.\d+)?%?", text.lower())}


def _required_tokens_match(first: str, second: str) -> bool:
    first_tokens = _tokens(first)
    second_tokens = _tokens(second)
    important = {
        token
        for token in first_tokens | second_tokens
        if len(token) >= 4 and token not in {"market", "event", "above", "below", "before", "after"}
    }
    if not important:
        return False
    overlap = first_tokens & second_tokens
    return len(overlap & important) / len(important) >= 0.75


def _has_conditional_terms(text: str) -> bool:
    lowered = text.lower()
    phrases = ["if neither", "fallback", "50-50", "50/50", "conditional on", "void if", "cancelled if"]
    return any(phrase in lowered for phrase in phrases)


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
