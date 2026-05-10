import json
import copy
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

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


def normalize_cross_platform_match_report(match_source: dict, top_n: Optional[int] = None) -> dict:
    if not isinstance(match_source, dict):
        raise ValueError("cross-platform match source must be a JSON object")
    if isinstance(match_source.get("top"), list) and match_source.get("type") == "cross_platform_match_report":
        report = copy.deepcopy(match_source)
        if top_n is not None:
            report["top"] = report.get("top", [])[:top_n]
        report["match_count"] = int(report.get("match_count") or len(report.get("top") or []))
        return report

    candidates = match_source.get("candidates")
    if not isinstance(candidates, list):
        report = copy.deepcopy(match_source)
        report.setdefault("type", "cross_platform_match_report")
        report.setdefault("top", [])
        report.setdefault("match_count", len(report.get("top") or []))
        return report

    top = [_candidate_row_to_match_row(candidate) for candidate in candidates if isinstance(candidate, dict)]
    if top_n is not None:
        top = top[:top_n]
    return {
        "type": "cross_platform_match_report",
        "match_count": len(candidates),
        "top": top,
        "source": "candidate_file",
        "source_top_n": top_n,
    }


def event_tickers_from_cross_platform_candidates(match_source: dict) -> list:
    if not isinstance(match_source, dict):
        raise ValueError("cross-platform candidate source must be a JSON object")
    candidates = match_source.get("candidates")
    if not isinstance(candidates, list):
        candidates = match_source.get("top")
    if not isinstance(candidates, list):
        return []
    seen = set()
    event_tickers = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        event_ticker = str(candidate.get("kalshi_event_ticker") or "").strip()
        if event_ticker and event_ticker not in seen:
            seen.add(event_ticker)
            event_tickers.append(event_ticker)
    return event_tickers


def expand_cross_platform_event_candidates(
    match_source: dict,
    kalshi_markets_path: Path,
    polymarket_gamma_path: Optional[Path] = None,
    top_n: Optional[int] = None,
    min_score: float = 0.0,
) -> dict:
    if min_score < 0:
        raise ValueError("min_score must be non-negative")
    if not isinstance(match_source, dict):
        raise ValueError("cross-platform candidate source must be a JSON object")
    candidates = match_source.get("candidates")
    if not isinstance(candidates, list):
        candidates = match_source.get("top")
    if not isinstance(candidates, list):
        candidates = []

    kalshi_by_event = _read_kalshi_markets_by_event(kalshi_markets_path)
    polymarket_by_id = _read_polymarket_details_by_id(polymarket_gamma_path) if polymarket_gamma_path else {}
    rows = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        event_ticker = str(candidate.get("kalshi_event_ticker") or "").strip()
        polymarket_market = polymarket_by_id.get(str(candidate.get("polymarket_market_id") or ""))
        if not event_ticker:
            row = _candidate_row_to_match_row(candidate)
            _add_polymarket_details(row, polymarket_market)
            if row.get("kalshi_ticker"):
                rows.append(row)
            continue
        for kalshi_market in kalshi_by_event.get(event_ticker, []):
            row = _candidate_event_market_row(candidate, kalshi_market, polymarket_market=polymarket_market)
            if float(row.get("score") or 0.0) >= min_score:
                rows.append(row)

    rows.sort(
        key=lambda row: (
            -float(row.get("score") or 0.0),
            row.get("polymarket_market_id") or "",
            row.get("kalshi_ticker") or "",
        )
    )
    deduped = []
    seen_pairs = set()
    for row in rows:
        key = (row.get("polymarket_market_id"), row.get("kalshi_ticker"))
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        deduped.append(row)
    if top_n is not None:
        deduped = deduped[:top_n]
    return {
        "type": "cross_platform_match_report",
        "source": "event_candidate_expansion",
        "source_candidate_count": len(candidates),
        "kalshi_markets_path": str(kalshi_markets_path),
        "polymarket_gamma_path": str(polymarket_gamma_path) if polymarket_gamma_path else None,
        "min_score": min_score,
        "match_count": len(deduped),
        "top": deduped,
    }


def opportunity_match_report_from_scan(
    scan_report: dict,
    match_report: dict,
    top_n: Optional[int] = None,
    min_net_edge: float = 0.0,
    require_option_match: bool = True,
) -> dict:
    if min_net_edge < 0:
        raise ValueError("min_net_edge must be non-negative")
    normalized_matches = normalize_cross_platform_match_report(match_report)
    matches_by_pair = {
        (str(row.get("polymarket_market_id") or ""), str(row.get("kalshi_ticker") or "")): row
        for row in normalized_matches.get("top", [])
    }
    rows = []
    seen = set()
    opportunities = sorted(
        list(scan_report.get("opportunities") or []),
        key=lambda row: -float(row.get("net_edge_per_share") or 0.0),
    )
    for opportunity in opportunities:
        edge = float(opportunity.get("net_edge_per_share") or 0.0)
        if edge < min_net_edge:
            continue
        pair = opportunity.get("pair") or {}
        key = (str(pair.get("polymarket_market_id") or ""), str(pair.get("kalshi_ticker") or ""))
        if key in seen:
            continue
        source_match = matches_by_pair.get(key, pair)
        row = copy.deepcopy(source_match)
        option_ok, option_reason = _option_match(row)
        row["option_match"] = option_ok
        row["option_match_reason"] = option_reason
        row["scan_edge_per_share"] = edge
        row["scan_total_edge"] = float(opportunity.get("total_edge") or 0.0)
        row["scan_quantity"] = float(opportunity.get("quantity") or 0.0)
        if require_option_match and not option_ok:
            continue
        seen.add(key)
        rows.append(row)
        if top_n is not None and len(rows) >= top_n:
            break
    return {
        "type": "cross_platform_match_report",
        "source": "scan_opportunity_filter",
        "scan_path": scan_report.get("path"),
        "source_opportunity_count": len(scan_report.get("opportunities") or []),
        "min_net_edge": min_net_edge,
        "require_option_match": require_option_match,
        "match_count": len(rows),
        "top": rows,
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
                "polymarket_question": match.get("polymarket_question"),
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
                yield {
                    "ticker": ticker,
                    "title": title,
                    "event_ticker": str(raw.get("event_ticker") or "").strip(),
                    "category": str(raw.get("category") or raw.get("category_name") or "").strip(),
                    "series_ticker": str(raw.get("series_ticker") or raw.get("seriesTicker") or "").strip(),
                    "raw": raw,
                }


def _read_kalshi_markets_by_event(path: Path) -> dict:
    markets_by_event = {}
    for market in _read_kalshi_markets(path):
        event_ticker = str(market.get("event_ticker") or "").strip()
        if not event_ticker:
            continue
        markets_by_event.setdefault(event_ticker, []).append(market)
    return markets_by_event


def _read_polymarket_details_by_id(path: Path) -> dict:
    return {str(market.get("id") or market.get("conditionId") or ""): market for market in raw_gamma_markets_from_ndjson(path)}


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


def _candidate_row_to_match_row(candidate: dict) -> dict:
    kalshi_ticker = str(candidate.get("kalshi_ticker") or candidate.get("kalshi_market_ticker") or "").strip()
    poly_market_id = str(candidate.get("polymarket_market_id") or "").strip()
    poly_title = str(candidate.get("polymarket_title") or candidate.get("polymarket_question") or "").strip()
    kalshi_title = str(candidate.get("kalshi_title") or "").strip()
    score = float(candidate.get("score") or 0.0)
    status = "candidate_needs_llm_or_manual_verification" if kalshi_ticker and poly_market_id else "candidate_needs_market_expansion"
    return {
        "polymarket_market_id": poly_market_id,
        "polymarket_title": poly_title,
        "polymarket_question": str(candidate.get("polymarket_question") or poly_title),
        "polymarket_description": str(candidate.get("polymarket_description") or ""),
        "polymarket_end_date": str(candidate.get("polymarket_end_date") or ""),
        "polymarket_resolution_source": str(candidate.get("polymarket_resolution_source") or ""),
        "kalshi_ticker": kalshi_ticker,
        "kalshi_event_ticker": str(candidate.get("kalshi_event_ticker") or "").strip(),
        "kalshi_title": kalshi_title,
        "kalshi_category": str(candidate.get("kalshi_category") or "").strip(),
        "kalshi_series_ticker": str(candidate.get("kalshi_series_ticker") or "").strip(),
        "score": score,
        "status": status,
        "trade_allowed": False,
        "source_candidate": candidate,
    }


def _candidate_event_market_row(candidate: dict, kalshi_market: dict, polymarket_market: Optional[dict] = None) -> dict:
    base = _candidate_row_to_match_row(candidate)
    _add_polymarket_details(base, polymarket_market)
    raw = kalshi_market.get("raw") or {}
    poly_text = " ".join(
        [
            str(candidate.get("polymarket_question") or ""),
            str(candidate.get("polymarket_title") or ""),
        ]
    )
    kalshi_title = _kalshi_market_prompt_title(kalshi_market)
    market_score = _jaccard(_tokens(poly_text), _tokens(kalshi_title))
    source_score = float(candidate.get("score") or 0.0)
    score = max(market_score, 0.75 * source_score + 0.25 * market_score)
    base.update(
        {
            "kalshi_ticker": kalshi_market.get("ticker"),
            "kalshi_event_ticker": kalshi_market.get("event_ticker") or candidate.get("kalshi_event_ticker"),
            "kalshi_title": kalshi_title,
            "kalshi_category": kalshi_market.get("category") or candidate.get("kalshi_category") or "",
            "kalshi_series_ticker": kalshi_market.get("series_ticker") or candidate.get("kalshi_series_ticker") or "",
            "score": score,
            "event_title_score": source_score,
            "market_title_score": market_score,
            "status": "candidate_needs_llm_or_manual_verification",
            "trade_allowed": False,
            "source_kalshi_market": {
                "ticker": kalshi_market.get("ticker"),
                "event_ticker": kalshi_market.get("event_ticker"),
                "title": raw.get("title") or kalshi_market.get("title"),
                "yes_sub_title": raw.get("yes_sub_title"),
                "no_sub_title": raw.get("no_sub_title"),
            },
        }
    )
    return base


def _add_polymarket_details(row: dict, market: Optional[dict]) -> None:
    if not market:
        return
    row["polymarket_description"] = str(market.get("description") or row.get("polymarket_description") or "")[:2000]
    row["polymarket_end_date"] = str(market.get("endDate") or market.get("endDateIso") or row.get("polymarket_end_date") or "")
    row["polymarket_resolution_source"] = str(market.get("resolutionSource") or row.get("polymarket_resolution_source") or "")
    row["polymarket_slug"] = str(market.get("slug") or row.get("polymarket_slug") or "")


def _kalshi_market_prompt_title(kalshi_market: dict) -> str:
    raw = kalshi_market.get("raw") or {}
    parts = [
        raw.get("event_title"),
        raw.get("title") or kalshi_market.get("title"),
        raw.get("subtitle"),
        raw.get("yes_sub_title"),
        raw.get("no_sub_title"),
        raw.get("rules_primary"),
    ]
    text = " | ".join(str(part).strip() for part in parts if str(part or "").strip())
    return text[:1200]


def _option_match(row: dict) -> tuple:
    pm_text = _normalize_option_text(row.get("polymarket_question") or row.get("polymarket_title") or "")
    kalshi_text = _normalize_option_text(row.get("kalshi_title") or "")
    source_market = row.get("source_kalshi_market") or {}
    explicit_options = [
        _normalize_option_text(source_market.get("yes_sub_title") or ""),
        _normalize_option_text(source_market.get("no_sub_title") or ""),
    ]
    explicit_options = [
        option
        for option in explicit_options
        if option and option not in {"yes", "no", "before 2027", "not before 2027"}
    ]
    pm_tokens = set(pm_text.split())
    for option in explicit_options:
        if option in pm_text:
            return True, f"explicit_option_in_polymarket_question:{option}"
        option_tokens = set(option.split())
        if option_tokens and len(option_tokens & pm_tokens) / len(option_tokens) >= 0.8:
            return True, f"explicit_option_token_overlap:{option}"
    if not explicit_options:
        kalshi_tokens = set(kalshi_text.split())
        union = pm_tokens | kalshi_tokens
        score = (len(pm_tokens & kalshi_tokens) / len(union)) if union else 0.0
        if score >= 0.55:
            return True, f"binary_title_score:{score:.2f}"
    return False, "option_mismatch"


def _normalize_option_text(value) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


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
