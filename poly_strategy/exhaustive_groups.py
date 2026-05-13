import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from poly_strategy.backtest import RuleSet, load_rule_set, snapshots_from_ndjson_lines
from poly_strategy.near_miss import deterministic_group_exhaustiveness_rejection, near_miss_candidates
from poly_strategy.recent_lines import read_recent_lines
from poly_strategy.rule_discovery import MarketText, read_market_texts


@dataclass(frozen=True)
class ExhaustiveGroupPromotionResult:
    candidates_found: int
    verified_count: int
    added_count: int
    rejected_count: int
    skipped_existing_count: int
    out_path: Path
    rows: List[dict] = field(default_factory=list)


def promote_exhaustive_groups(
    gamma_path: Path,
    rules_in_path: Path,
    rules_out_path: Path,
    snapshots_path: Path,
    client,
    min_net_edge: float = 0.0,
    top_n: int = 10,
    min_confidence: float = 0.95,
    state_path: Optional[Path] = None,
    recheck_hours: float = 24.0,
    now: Optional[datetime] = None,
    semantic_client=None,
) -> ExhaustiveGroupPromotionResult:
    if top_n < 0:
        raise ValueError("top_n must be non-negative")
    if recheck_hours < 0:
        raise ValueError("recheck_hours must be non-negative")

    rules_row = _load_rule_row(rules_in_path)
    state_row = _load_state_row(state_path)
    now = now or datetime.now(timezone.utc)
    market_texts = {market.market_id: market for market in read_market_texts(gamma_path)}
    existing_group_keys = _existing_group_keys(rules_row)
    candidates = potential_exhaustive_group_candidates(
        snapshots_path,
        rules_in_path,
        min_net_edge,
        top_n,
        gamma_path=gamma_path,
    )

    report_rows = []
    added_rows = []
    verified_count = 0
    rejected_count = 0
    skipped_existing_count = 0

    for candidate in candidates:
        market_ids = candidate["market_ids"]
        group_key = frozenset(market_ids)
        report_row = {
            "market_ids": market_ids,
            "source_kind": candidate["kind"],
            "source_net_edge_per_share": candidate["net_edge_per_share"],
            "source_gross_edge_per_share": candidate["gross_edge_per_share"],
        }
        if group_key in existing_group_keys:
            skipped_existing_count += 1
            report_row["status"] = "skipped_existing"
            report_rows.append(report_row)
            continue
        cached_status = _cached_group_status(state_row, market_ids, now, recheck_hours)
        if cached_status is not None:
            skipped_existing_count += 1
            report_row["status"] = "skipped_cached"
            report_row["cached_status"] = cached_status
            report_rows.append(report_row)
            continue

        markets, missing_market_ids = _markets_for_group(market_texts, market_ids)
        if missing_market_ids:
            rejected_count += 1
            report_row["status"] = "missing_markets"
            report_row["missing_market_ids"] = missing_market_ids
            _record_state(state_row, market_ids, "missing_markets", report_row, now)
            report_rows.append(report_row)
            continue

        extra_group_market_ids = _extra_known_neg_risk_group_market_ids(markets, market_texts)
        if extra_group_market_ids:
            rejected_count += 1
            report_row["status"] = "incomplete_known_neg_risk_group"
            report_row["extra_known_market_ids"] = extra_group_market_ids
            _record_state(state_row, market_ids, "incomplete_known_neg_risk_group", report_row, now)
            report_rows.append(report_row)
            continue

        group_rejection = _candidate_group_wording_rejection(market_ids, market_texts)
        if group_rejection:
            rejected_count += 1
            report_row["status"] = "known_neg_risk_group_not_exhaustive_by_wording"
            report_row["rejection_reason"] = group_rejection
            _record_state(state_row, market_ids, "known_neg_risk_group_not_exhaustive_by_wording", report_row, now)
            report_rows.append(report_row)
            continue

        verification, verification_provider = _verify_group_with_semantic(
            client,
            semantic_client,
            markets,
            min_confidence,
        )
        report_row["verification"] = verification
        report_row["verification_provider"] = verification_provider
        if _verification_is_tradeable(verification, min_confidence):
            verified_count += 1
            added_rows.append(_rule_row_from_verification(market_ids, verification))
            existing_group_keys.add(group_key)
            report_row["status"] = "added"
            _record_state(state_row, market_ids, "added", report_row, now)
        else:
            rejected_count += 1
            report_row["status"] = "rejected"
            _record_state(state_row, market_ids, "rejected", report_row, now)
        report_rows.append(report_row)

    output_row = dict(rules_row)
    output_row["exhaustive_groups"] = _dedupe_group_rows(
        list(output_row.get("exhaustive_groups", [])) + added_rows
    )
    rules_out_path.parent.mkdir(parents=True, exist_ok=True)
    rules_out_path.write_text(json.dumps(output_row, indent=2, sort_keys=True) + "\n")
    _write_state_row(state_path, state_row)

    return ExhaustiveGroupPromotionResult(
        candidates_found=len(candidates),
        verified_count=verified_count,
        added_count=len(added_rows),
        rejected_count=rejected_count,
        skipped_existing_count=skipped_existing_count,
        out_path=rules_out_path,
        rows=report_rows,
    )


def _verify_group_with_semantic(client, semantic_client, markets: List[MarketText], min_confidence: float) -> Tuple[dict, str]:
    try:
        primary_verification = client.verify_group(markets)
    except Exception as primary_error:
        if semantic_client is None:
            raise
        try:
            return semantic_client.verify_group(markets), "semantic"
        except Exception as semantic_error:
            raise semantic_error from primary_error

    if semantic_client is None or _verification_is_tradeable(primary_verification, min_confidence):
        return primary_verification, "primary"

    return semantic_client.verify_group(markets), "semantic"


def potential_exhaustive_group_candidates(
    snapshots_path: Path,
    rules_path: Path,
    min_net_edge: float = 0.0,
    top_n: int = 10,
    gamma_path: Optional[Path] = None,
) -> List[dict]:
    if top_n < 0:
        raise ValueError("top_n must be non-negative")

    snapshots = _latest_snapshot_batch(snapshots_path)
    rule_set = load_rule_set(rules_path, gamma_path=gamma_path) if rules_path else RuleSet()
    market_texts = {market.market_id: market for market in read_market_texts(gamma_path)} if gamma_path else {}
    rows = near_miss_candidates(snapshots, rule_set, min_net_edge=min_net_edge)
    rows = [
        row
        for row in rows
        if row["kind"] == "potential_exhaustive_yes_basket" and row["net_edge_per_share"] >= min_net_edge
    ]
    rows.sort(key=lambda row: (row["net_edge_per_share"], row["gross_edge_per_share"]), reverse=True)

    candidates = []
    seen = set()
    for row in rows:
        market_ids = [leg["market_id"] for leg in row["legs"]]
        group_key = frozenset(market_ids)
        if len(group_key) != len(market_ids) or group_key in seen:
            continue
        if market_texts and _candidate_group_wording_rejection(market_ids, market_texts):
            continue
        seen.add(group_key)
        candidates.append(
            {
                "kind": row["kind"],
                "market_ids": market_ids,
                "net_edge_per_share": row["net_edge_per_share"],
                "gross_edge_per_share": row["gross_edge_per_share"],
            }
        )
        if len(candidates) >= top_n:
            break
    return candidates


def _candidate_group_wording_rejection(market_ids: List[str], market_texts: dict) -> Optional[str]:
    markets, missing_market_ids = _markets_for_group(market_texts, market_ids)
    if missing_market_ids:
        return None
    group_ids = [market.neg_risk_market_id for market in markets]
    if group_ids and all(group_ids) and len(set(group_ids)) == 1:
        group_id = group_ids[0]
        known_markets = [market for market in market_texts.values() if market.neg_risk_market_id == group_id]
        if known_markets:
            return deterministic_group_exhaustiveness_rejection(known_markets)
    return deterministic_group_exhaustiveness_rejection(markets)


def result_to_row(result: ExhaustiveGroupPromotionResult) -> dict:
    return {
        "type": "exhaustive_group_promotion",
        "candidates_found": result.candidates_found,
        "verified_count": result.verified_count,
        "added_count": result.added_count,
        "rejected_count": result.rejected_count,
        "skipped_existing_count": result.skipped_existing_count,
        "out_path": str(result.out_path),
        "rows": result.rows,
    }


def promotion_candidate_count(
    snapshots_path: Path,
    rules_path: Path,
    min_net_edge: float = 0.0,
    top_n: int = 10,
    gamma_path: Optional[Path] = None,
) -> int:
    return len(potential_exhaustive_group_candidates(snapshots_path, rules_path, min_net_edge, top_n, gamma_path))


def _latest_snapshot_batch(path: Path):
    snapshots = list(snapshots_from_ndjson_lines(read_recent_lines(path)))
    if not snapshots:
        return []
    latest_ts = snapshots[-1].ts
    return [snapshot for snapshot in snapshots if snapshot.ts == latest_ts]


def _load_rule_row(path: Optional[Path]) -> dict:
    if not path or not path.exists():
        return {}
    return json.loads(path.read_text())


def _load_state_row(path: Optional[Path]) -> dict:
    if not path or not path.exists():
        return {"type": "exhaustive_group_promotion_state", "groups": {}}
    try:
        row = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {"type": "exhaustive_group_promotion_state", "groups": {}}
    if not isinstance(row, dict):
        return {"type": "exhaustive_group_promotion_state", "groups": {}}
    row.setdefault("type", "exhaustive_group_promotion_state")
    row.setdefault("groups", {})
    return row


def _write_state_row(path: Optional[Path], row: dict) -> None:
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def _cached_group_status(state_row: dict, market_ids: List[str], now: datetime, recheck_hours: float) -> Optional[dict]:
    row = (state_row.get("groups") or {}).get(_group_key_string(market_ids))
    if not isinstance(row, dict):
        return None
    if row.get("status") == "added":
        return None
    ts = _parse_ts(row.get("ts"))
    if ts is None:
        return None
    if now - ts <= timedelta(hours=recheck_hours):
        return row
    return None


def _record_state(state_row: dict, market_ids: List[str], status: str, report_row: dict, now: datetime) -> None:
    groups = state_row.setdefault("groups", {})
    groups[_group_key_string(market_ids)] = {
        "ts": _utc_iso(now),
        "status": status,
        "market_ids": list(market_ids),
        "source_net_edge_per_share": report_row.get("source_net_edge_per_share"),
        "reason": report_row.get("status"),
        "verification": report_row.get("verification"),
    }


def _group_key_string(market_ids: List[str]) -> str:
    return "|".join(sorted(str(market_id) for market_id in market_ids if market_id))


def _parse_ts(value) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _existing_group_keys(row: dict) -> set:
    keys = set()
    for rule in row.get("exhaustive_groups", []):
        market_ids = _market_ids_from_group_row(rule)
        if market_ids:
            keys.add(frozenset(market_ids))
    return keys


def _market_ids_from_group_row(rule: dict) -> List[str]:
    raw_market_ids = rule.get("market_ids")
    if raw_market_ids is None:
        raw_market_ids = rule.get("markets")
    if not isinstance(raw_market_ids, list):
        return []
    market_ids = []
    seen = set()
    for value in raw_market_ids:
        if not value:
            continue
        market_id = str(value)
        if market_id in seen:
            continue
        seen.add(market_id)
        market_ids.append(market_id)
    return market_ids


def _markets_for_group(market_texts: dict, market_ids: List[str]) -> Tuple[List[MarketText], List[str]]:
    markets = []
    missing = []
    for market_id in market_ids:
        market = market_texts.get(market_id)
        if market is None:
            missing.append(market_id)
        else:
            markets.append(market)
    return markets, missing


def _extra_known_neg_risk_group_market_ids(markets: List[MarketText], market_texts: dict) -> List[str]:
    group_ids = {market.neg_risk_market_id for market in markets if market.neg_risk_market_id}
    if len(group_ids) != 1:
        return []

    group_id = next(iter(group_ids))
    candidate_ids = {market.market_id for market in markets}
    return sorted(
        market.market_id
        for market in market_texts.values()
        if market.neg_risk_market_id == group_id and market.market_id not in candidate_ids
    )


def _verification_is_tradeable(verification: dict, min_confidence: float) -> bool:
    try:
        confidence = float(verification.get("confidence", 0.0))
    except (TypeError, ValueError):
        return False
    return (
        verification.get("verdict") == "exhaustive_group"
        and verification.get("trade_allowed") is True
        and not verification.get("risk_flags")
        and confidence >= min_confidence
    )


def _rule_row_from_verification(market_ids: List[str], verification: dict) -> dict:
    return {
        "market_ids": market_ids,
        "confidence": float(verification["confidence"]),
        "trade_allowed": True,
        "risk_flags": [],
        "source_relation": "llm_exhaustive_group_verification",
        "reason": str(verification.get("reason") or ""),
    }


def _dedupe_group_rows(rows: List[dict]) -> List[dict]:
    deduped = []
    seen = set()
    for row in rows:
        market_ids = _market_ids_from_group_row(row)
        group_key = frozenset(market_ids)
        if not market_ids or group_key in seen:
            continue
        seen.add(group_key)
        copied = dict(row)
        copied["market_ids"] = market_ids
        deduped.append(copied)
    return deduped
