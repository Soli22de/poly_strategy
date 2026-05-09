import json
from pathlib import Path
from typing import Iterable

from poly_strategy.collectors import (
    expand_market_ids_with_neg_risk_groups,
    market_fee_rate,
    market_ids_from_rule_file,
    raw_gamma_markets_from_ndjson,
)


def build_polymarket_watchlist(gamma_path: Path, rules_path: Path, expand_neg_risk_groups: bool = True) -> list:
    markets = raw_gamma_markets_from_ndjson(gamma_path)
    market_ids = market_ids_from_rule_file(rules_path)
    if expand_neg_risk_groups:
        market_ids = expand_market_ids_with_neg_risk_groups(markets, market_ids)
    return _watchlist_rows(markets, market_ids)


def write_watchlist(rows: Iterable[dict], path: Path) -> int:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"type": "polymarket_watchlist", "markets": rows}, indent=2, sort_keys=True) + "\n")
    return len(rows)


def _watchlist_rows(markets: Iterable[dict], market_ids: Iterable[str]) -> list:
    wanted = {str(market_id) for market_id in market_ids if market_id}
    rows = []
    seen = set()
    for market in markets:
        market_id = str(market.get("id") or market.get("conditionId") or "").strip()
        if not market_id or market_id not in wanted or market_id in seen:
            continue
        seen.add(market_id)
        token_ids = _loads_json_list(market.get("clobTokenIds"))
        rows.append(
            {
                "venue": "polymarket",
                "market_id": market_id,
                "question": market.get("question"),
                "fee_rate": market_fee_rate(market),
                "neg_risk": bool(market.get("negRisk")),
                "neg_risk_market_id": str(market.get("negRiskMarketID") or "").strip() or None,
                "group_item_title": str(market.get("groupItemTitle") or "").strip() or None,
                "group_item_threshold": str(market.get("groupItemThreshold") or "").strip() or None,
                "yes_token_id": str(token_ids[0]) if len(token_ids) >= 1 else None,
                "no_token_id": str(token_ids[1]) if len(token_ids) >= 2 else None,
            }
        )
    rows.sort(key=lambda row: (row.get("neg_risk_market_id") or "", _threshold_key(row), row["market_id"]))
    return rows


def _loads_json_list(value) -> list:
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        loaded = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(loaded, list):
        return []
    return loaded


def _threshold_key(row: dict) -> tuple:
    value = row.get("group_item_threshold")
    try:
        return (0, float(value))
    except (TypeError, ValueError):
        return (1, str(value or ""))
