import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set


@dataclass(frozen=True)
class MarketText:
    market_id: str
    question: str
    description: str
    outcomes: List[str]
    end_date: str
    category: str
    slug: str
    neg_risk: bool = False
    neg_risk_market_id: str = ""
    group_item_title: str = ""
    group_item_threshold: str = ""


@dataclass(frozen=True)
class RelationCandidate:
    relation_type: str
    market_a_id: str
    market_b_id: str
    direction: str
    confidence: float
    trade_allowed: bool
    risk_flags: List[str]
    reason: str


@dataclass(frozen=True)
class DiscoveredImplication:
    antecedent: str
    consequent: str
    confidence: float
    source_relation: str
    reason: str


@dataclass(frozen=True)
class DiscoveredMutualExclusion:
    first: str
    second: str
    confidence: float
    source_relation: str
    reason: str


@dataclass(frozen=True)
class DiscoveredRuleSet:
    generated_at: str
    min_confidence: float
    candidates: List[RelationCandidate]
    implications: List[DiscoveredImplication]
    processed_market_ids: List[str] = field(default_factory=list)
    mutual_exclusions: List[DiscoveredMutualExclusion] = field(default_factory=list)
    equivalents: List[DiscoveredMutualExclusion] = field(default_factory=list)
    collectively_exhaustive: List[DiscoveredMutualExclusion] = field(default_factory=list)
    complements: List[DiscoveredMutualExclusion] = field(default_factory=list)
    discovery_errors: List[dict] = field(default_factory=list)


@dataclass(frozen=True)
class DiscoveryResult:
    markets_read: int
    candidates_found: int
    implications_written: int
    mutual_exclusions_written: int = 0
    equivalents_written: int = 0
    collectively_exhaustive_written: int = 0
    complements_written: int = 0
    failed_batches: int = 0


def read_market_texts(path: Path) -> List[MarketText]:
    markets_by_id = {}
    market_order = []
    with path.open() as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            market = _market_text_from_row(row)
            if market is not None:
                if market.market_id not in markets_by_id:
                    market_order.append(market.market_id)
                markets_by_id[market.market_id] = market
    return [markets_by_id[market_id] for market_id in market_order]


def filter_implications(
    candidates: Iterable[RelationCandidate],
    known_market_ids: Set[str],
    min_confidence: float,
) -> List[DiscoveredImplication]:
    implications = []
    for candidate in candidates:
        implication = _implication_from_candidate(candidate, known_market_ids, min_confidence)
        if implication is not None:
            implications.append(implication)
    return sorted(implications, key=lambda rule: (rule.antecedent, rule.consequent))


def filter_mutual_exclusions(
    candidates: Iterable[RelationCandidate],
    known_market_ids: Set[str],
    min_confidence: float,
) -> List[DiscoveredMutualExclusion]:
    exclusions = []
    seen = set()
    for candidate in candidates:
        exclusion = _mutual_exclusion_from_candidate(candidate, known_market_ids, min_confidence)
        if exclusion is None:
            continue
        key = (exclusion.first, exclusion.second)
        if key in seen:
            continue
        seen.add(key)
        exclusions.append(exclusion)
    return sorted(exclusions, key=lambda rule: (rule.first, rule.second))


def filter_equivalents(
    candidates: Iterable[RelationCandidate],
    known_market_ids: Set[str],
    min_confidence: float,
) -> List[DiscoveredMutualExclusion]:
    return _filter_pair_relation(candidates, "equivalent", known_market_ids, min_confidence)


def filter_collectively_exhaustive(
    candidates: Iterable[RelationCandidate],
    known_market_ids: Set[str],
    min_confidence: float,
) -> List[DiscoveredMutualExclusion]:
    return _filter_pair_relation(candidates, "collectively_exhaustive", known_market_ids, min_confidence)


def filter_complements(
    candidates: Iterable[RelationCandidate],
    known_market_ids: Set[str],
    min_confidence: float,
) -> List[DiscoveredMutualExclusion]:
    return _filter_pair_relation(candidates, "complement", known_market_ids, min_confidence)


def write_discovered_rules(path: Path, ruleset: DiscoveredRuleSet) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    implications = sorted(ruleset.implications, key=lambda rule: (rule.antecedent, rule.consequent))
    mutual_exclusions = sorted(ruleset.mutual_exclusions, key=lambda rule: (rule.first, rule.second))
    equivalents = sorted(ruleset.equivalents, key=lambda rule: (rule.first, rule.second))
    collectively_exhaustive = sorted(ruleset.collectively_exhaustive, key=lambda rule: (rule.first, rule.second))
    complements = sorted(ruleset.complements, key=lambda rule: (rule.first, rule.second))
    row = {
        "version": 1,
        "source": "llm_discovery",
        "generated_at": ruleset.generated_at,
        "min_confidence": ruleset.min_confidence,
        "processed_market_ids": sorted({str(market_id) for market_id in ruleset.processed_market_ids}),
        "implications": [_implication_to_row(rule) for rule in implications],
        "equivalent": [_mutual_exclusion_to_row(rule) for rule in equivalents],
        "mutually_exclusive": [_mutual_exclusion_to_row(rule) for rule in mutual_exclusions],
        "collectively_exhaustive": [_mutual_exclusion_to_row(rule) for rule in collectively_exhaustive],
        "complement": [_mutual_exclusion_to_row(rule) for rule in complements],
        "discovery_errors": list(ruleset.discovery_errors),
        "candidates": [_candidate_to_row(candidate) for candidate in ruleset.candidates],
    }
    path.write_text(json.dumps(row, indent=2, sort_keys=True) + "\n")
    return len(implications)


def discover_rules(
    raw_path: Path,
    out_path: Path,
    client,
    batch_size: int,
    min_confidence: float,
    max_markets: Optional[int] = None,
    cache_path: Optional[Path] = None,
    context_market_limit: int = 40,
    generated_at: Optional[str] = None,
    continue_on_client_error: bool = False,
    client_workers: int = 1,
    retry_failed_batches: int = 0,
    retry_failed_batch_size: int = 1,
) -> DiscoveryResult:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    if max_markets is not None and max_markets < 1:
        raise ValueError("max_markets must be at least 1")
    if context_market_limit < 0:
        raise ValueError("context_market_limit must be non-negative")
    if client_workers < 1:
        raise ValueError("client_workers must be at least 1")
    if retry_failed_batches < 0:
        raise ValueError("retry_failed_batches must be non-negative")
    if retry_failed_batch_size < 1:
        raise ValueError("retry_failed_batch_size must be at least 1")

    markets = read_market_texts(raw_path)
    if max_markets is not None:
        markets = markets[:max_markets]

    cache_row = _load_json(cache_path) if cache_path and cache_path.exists() else None
    cached_market_ids = _processed_market_ids_from_cache(cache_row)
    new_markets = [market for market in markets if market.market_id not in cached_market_ids]
    if new_markets and client is None:
        raise RuntimeError("client is required when uncached markets need LLM discovery")

    deterministic_candidates = deterministic_relation_candidates(markets)
    market_map = {market.market_id: market for market in markets}
    completed_market_ids: Set[str] = set()
    discovery_errors: List[dict] = []
    batch_results: dict[tuple[int, int], List[RelationCandidate]] = {}
    generated = generated_at or _utc_now()

    def discover_batch(batch_index: int, batch_markets: Sequence[MarketText]) -> List[RelationCandidate]:
        discovery_batch = _batch_with_context(batch_markets, markets, context_market_limit)
        return secondary_verify_candidates(client.discover_relations(discovery_batch), market_map)

    def checkpoint() -> None:
        _write_rules_checkpoint(
            out_path,
            deterministic_candidates,
            _ordered_batch_candidates(batch_results),
            cache_row,
            markets,
            cached_market_ids | completed_market_ids,
            min_confidence,
            generated,
            _unresolved_discovery_errors(discovery_errors, completed_market_ids),
        )

    def record_success(attempt: int, batch_index: int, batch: Sequence[MarketText], candidates: List[RelationCandidate]) -> None:
        batch_results[(attempt, batch_index)] = candidates
        completed_market_ids.update(market.market_id for market in batch)
        checkpoint()

    def record_failure(attempt: int, batch_index: int, batch: Sequence[MarketText], exc: Exception) -> None:
        discovery_errors.append(
            {
                "attempt": attempt,
                "batch_index": batch_index,
                "market_ids": [market.market_id for market in batch],
                "error": str(exc),
            }
        )
        checkpoint()

    def run_batches(batches_to_run: List[List[MarketText]], attempt: int) -> None:
        if not batches_to_run:
            return
        if client_workers == 1:
            for batch_index, batch in enumerate(batches_to_run):
                try:
                    candidates = discover_batch(batch_index, batch)
                except Exception as exc:
                    record_failure(attempt, batch_index, batch, exc)
                    if continue_on_client_error:
                        continue
                    raise
                record_success(attempt, batch_index, batch, candidates)
            return

        with ThreadPoolExecutor(max_workers=min(client_workers, len(batches_to_run))) as executor:
            future_map = {
                executor.submit(discover_batch, index, batch): (index, batch)
                for index, batch in enumerate(batches_to_run)
            }
            for future in as_completed(future_map):
                batch_index, batch = future_map[future]
                try:
                    candidates = future.result()
                except Exception as exc:
                    record_failure(attempt, batch_index, batch, exc)
                    if continue_on_client_error:
                        continue
                    for pending in future_map:
                        if pending is not future:
                            pending.cancel()
                    raise
                record_success(attempt, batch_index, batch, candidates)

    run_batches(list(_batches(new_markets, batch_size)), attempt=0)
    if continue_on_client_error:
        for retry_attempt in range(1, retry_failed_batches + 1):
            pending_markets = [market for market in new_markets if market.market_id not in completed_market_ids]
            if not pending_markets:
                break
            run_batches(list(_batches(pending_markets, retry_failed_batch_size)), attempt=retry_attempt)

    known_market_ids = {market.market_id for market in markets}
    llm_candidates = _ordered_batch_candidates(batch_results)
    unresolved_errors = _unresolved_discovery_errors(discovery_errors, completed_market_ids)
    candidates = _merge_candidates(deterministic_candidates + llm_candidates, cache_row.get("candidates", []) if cache_row else [])
    implications = filter_implications(candidates, known_market_ids, min_confidence)
    mutual_exclusions = filter_mutual_exclusions(candidates, known_market_ids, min_confidence)
    equivalents = filter_equivalents(candidates, known_market_ids, min_confidence)
    collectively_exhaustive = filter_collectively_exhaustive(candidates, known_market_ids, min_confidence)
    complements = filter_complements(candidates, known_market_ids, min_confidence)
    ruleset = DiscoveredRuleSet(
        generated_at=generated,
        min_confidence=min_confidence,
        candidates=candidates,
        implications=implications,
        processed_market_ids=sorted(cached_market_ids | completed_market_ids),
        mutual_exclusions=mutual_exclusions,
        equivalents=equivalents,
        collectively_exhaustive=collectively_exhaustive,
        complements=complements,
        discovery_errors=unresolved_errors,
    )
    implications_written = write_discovered_rules(out_path, ruleset)
    return DiscoveryResult(
        markets_read=len(markets),
        candidates_found=len(candidates),
        implications_written=implications_written,
        mutual_exclusions_written=len(mutual_exclusions),
        equivalents_written=len(equivalents),
        collectively_exhaustive_written=len(collectively_exhaustive),
        complements_written=len(complements),
        failed_batches=len(unresolved_errors),
    )


def _write_rules_checkpoint(
    out_path: Path,
    deterministic_candidates: List[RelationCandidate],
    llm_candidates: List[RelationCandidate],
    cache_row: Optional[dict],
    markets: Sequence[MarketText],
    processed_market_ids: Set[str],
    min_confidence: float,
    generated_at: str,
    discovery_errors: Optional[List[dict]] = None,
) -> None:
    known_market_ids = {market.market_id for market in markets}
    candidates = _merge_candidates(deterministic_candidates + llm_candidates, cache_row.get("candidates", []) if cache_row else [])
    ruleset = DiscoveredRuleSet(
        generated_at=generated_at,
        min_confidence=min_confidence,
        candidates=candidates,
        implications=filter_implications(candidates, known_market_ids, min_confidence),
        processed_market_ids=sorted(processed_market_ids),
        mutual_exclusions=filter_mutual_exclusions(candidates, known_market_ids, min_confidence),
        equivalents=filter_equivalents(candidates, known_market_ids, min_confidence),
        collectively_exhaustive=filter_collectively_exhaustive(candidates, known_market_ids, min_confidence),
        complements=filter_complements(candidates, known_market_ids, min_confidence),
        discovery_errors=list(discovery_errors or []),
    )
    write_discovered_rules(out_path, ruleset)


def _ordered_batch_candidates(batch_results: dict[tuple[int, int], List[RelationCandidate]]) -> List[RelationCandidate]:
    candidates: List[RelationCandidate] = []
    for batch_key in sorted(batch_results):
        candidates.extend(batch_results[batch_key])
    return candidates


def _unresolved_discovery_errors(discovery_errors: List[dict], completed_market_ids: Set[str]) -> List[dict]:
    latest_by_market_id: dict[str, tuple[int, dict]] = {}
    for row in discovery_errors:
        for market_id in row.get("market_ids", []):
            normalized_market_id = str(market_id)
            if normalized_market_id in completed_market_ids:
                continue
            unresolved_row = dict(row)
            unresolved_row["market_ids"] = [normalized_market_id]
            latest_by_market_id[normalized_market_id] = (len(latest_by_market_id), unresolved_row)
    return [row for _, row in sorted(latest_by_market_id.values(), key=lambda item: item[0])]


def market_texts_to_prompt_rows(markets: Sequence[MarketText]) -> List[dict]:
    return [
        {
            "market_id": market.market_id,
            "question": market.question,
            "description": market.description,
            "outcomes": market.outcomes,
            "end_date": market.end_date,
            "category": market.category,
            "slug": market.slug,
            "neg_risk": market.neg_risk,
            "neg_risk_market_id": market.neg_risk_market_id,
            "group_item_title": market.group_item_title,
            "group_item_threshold": market.group_item_threshold,
        }
        for market in markets
    ]


def deterministic_relation_candidates(markets: Sequence[MarketText]) -> List[RelationCandidate]:
    grouped = defaultdict(list)
    for market in markets:
        if market.neg_risk_market_id:
            grouped[market.neg_risk_market_id].append(market)

    candidates: List[RelationCandidate] = []
    seen = set()
    for group_id, group_markets in grouped.items():
        if len(group_markets) < 2:
            continue
        sorted_markets = sorted(group_markets, key=lambda market: market.market_id)
        for index, first in enumerate(sorted_markets):
            for second in sorted_markets[index + 1 :]:
                key = (first.market_id, second.market_id)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(
                    RelationCandidate(
                        relation_type="mutually_exclusive",
                        market_a_id=first.market_id,
                        market_b_id=second.market_id,
                        direction="none",
                        confidence=0.99,
                        trade_allowed=True,
                        risk_flags=[],
                        reason=f"Deterministic neg-risk group {group_id}",
                    )
                )
    return candidates


def secondary_verify_candidates(
    candidates: Iterable[RelationCandidate],
    market_map: dict,
) -> List[RelationCandidate]:
    verified = []
    for candidate in candidates:
        market_a = market_map.get(candidate.market_a_id)
        market_b = market_map.get(candidate.market_b_id)
        if market_a is None or market_b is None:
            verified.append(candidate)
            continue
        if candidate.relation_type != "mutually_exclusive" and (
            _has_fallback_text(market_a) or _has_fallback_text(market_b)
        ):
            verified.append(
                RelationCandidate(
                    relation_type=candidate.relation_type,
                    market_a_id=candidate.market_a_id,
                    market_b_id=candidate.market_b_id,
                    direction=candidate.direction,
                    confidence=candidate.confidence,
                    trade_allowed=False,
                    risk_flags=_dedupe_flags(list(candidate.risk_flags) + ["conditional_or_fallback_resolution"]),
                    reason=candidate.reason,
                )
            )
            continue
        verified.append(candidate)
    return verified


def _market_text_from_row(row: dict) -> Optional[MarketText]:
    if row.get("type") != "raw_polymarket_gamma_market":
        return None
    raw = row.get("raw")
    if not isinstance(raw, dict):
        return None

    market_id = str(row.get("market_id") or raw.get("id") or raw.get("conditionId") or "").strip()
    question = str(raw.get("question") or "").strip()
    if not market_id or not question:
        return None

    outcomes = _loads_json_list(raw.get("outcomes"))
    description = str(raw.get("description") or raw.get("resolutionSource") or "").strip()
    end_date = str(raw.get("endDate") or raw.get("end_date") or "").strip()
    category = str(raw.get("category") or raw.get("categorySlug") or "").strip()
    slug = str(raw.get("slug") or "").strip() or _slugify(question)
    group_item_threshold = str(raw.get("groupItemThreshold") or "").strip()

    return MarketText(
        market_id=market_id,
        question=question,
        description=description,
        outcomes=outcomes,
        end_date=end_date,
        category=category,
        slug=slug,
        neg_risk=bool(raw.get("negRisk")),
        neg_risk_market_id=str(raw.get("negRiskMarketID") or "").strip(),
        group_item_title=str(raw.get("groupItemTitle") or "").strip(),
        group_item_threshold=group_item_threshold,
    )


def market_ids_from_rule_row(row: Optional[dict]) -> Set[str]:
    if not row:
        return set()
    market_ids: Set[str] = set()
    for rule in row.get("implications", []):
        _add_market_id(market_ids, rule, "antecedent")
        _add_market_id(market_ids, rule, "consequent")
    for section in ["mutually_exclusive", "equivalent", "collectively_exhaustive", "complement"]:
        for rule in row.get(section, []):
            _add_market_id(market_ids, rule, "first")
            _add_market_id(market_ids, rule, "second")
    for rule in row.get("exhaustive_groups", []):
        for market_id in _market_ids_from_group_rule(rule):
            market_ids.add(market_id)
    for candidate in row.get("candidates", []):
        _add_market_id(market_ids, candidate, "market_a_id")
        _add_market_id(market_ids, candidate, "market_b_id")
    return market_ids


def _processed_market_ids_from_cache(row: Optional[dict]) -> Set[str]:
    if not row:
        return set()
    processed = row.get("processed_market_ids")
    if isinstance(processed, list):
        return {str(market_id) for market_id in processed if market_id}
    # Backward-compatible fallback for rule files generated before explicit
    # processed_market_ids existed: only related markets can be considered cached.
    return market_ids_from_rule_row(row)


def _implication_from_candidate(
    candidate: RelationCandidate,
    known_market_ids: Set[str],
    min_confidence: float,
) -> Optional[DiscoveredImplication]:
    if candidate.relation_type != "implies":
        return None
    if not candidate.trade_allowed:
        return None
    if candidate.confidence < min_confidence:
        return None
    if candidate.risk_flags:
        return None
    if candidate.market_a_id not in known_market_ids or candidate.market_b_id not in known_market_ids:
        return None
    if candidate.market_a_id == candidate.market_b_id:
        return None

    if candidate.direction == "a_implies_b":
        antecedent = candidate.market_a_id
        consequent = candidate.market_b_id
    elif candidate.direction == "b_implies_a":
        antecedent = candidate.market_b_id
        consequent = candidate.market_a_id
    else:
        return None

    return DiscoveredImplication(
        antecedent=antecedent,
        consequent=consequent,
        confidence=candidate.confidence,
        source_relation=candidate.relation_type,
        reason=candidate.reason,
    )


def _mutual_exclusion_from_candidate(
    candidate: RelationCandidate,
    known_market_ids: Set[str],
    min_confidence: float,
) -> Optional[DiscoveredMutualExclusion]:
    if candidate.relation_type != "mutually_exclusive":
        return None
    if not candidate.trade_allowed:
        return None
    if candidate.confidence < min_confidence:
        return None
    if candidate.risk_flags:
        return None
    if candidate.market_a_id not in known_market_ids or candidate.market_b_id not in known_market_ids:
        return None
    if candidate.market_a_id == candidate.market_b_id:
        return None

    first, second = sorted([candidate.market_a_id, candidate.market_b_id])
    return DiscoveredMutualExclusion(
        first=first,
        second=second,
        confidence=candidate.confidence,
        source_relation=candidate.relation_type,
        reason=candidate.reason,
    )


def _filter_pair_relation(
    candidates: Iterable[RelationCandidate],
    relation_type: str,
    known_market_ids: Set[str],
    min_confidence: float,
) -> List[DiscoveredMutualExclusion]:
    rules = []
    seen = set()
    for candidate in candidates:
        rule = _pair_relation_from_candidate(candidate, relation_type, known_market_ids, min_confidence)
        if rule is None:
            continue
        key = (rule.first, rule.second)
        if key in seen:
            continue
        seen.add(key)
        rules.append(rule)
    return sorted(rules, key=lambda rule: (rule.first, rule.second))


def _pair_relation_from_candidate(
    candidate: RelationCandidate,
    relation_type: str,
    known_market_ids: Set[str],
    min_confidence: float,
) -> Optional[DiscoveredMutualExclusion]:
    if candidate.relation_type != relation_type:
        return None
    if not candidate.trade_allowed:
        return None
    if candidate.confidence < min_confidence:
        return None
    if candidate.risk_flags:
        return None
    if candidate.market_a_id not in known_market_ids or candidate.market_b_id not in known_market_ids:
        return None
    if candidate.market_a_id == candidate.market_b_id:
        return None

    first, second = sorted([candidate.market_a_id, candidate.market_b_id])
    return DiscoveredMutualExclusion(
        first=first,
        second=second,
        confidence=candidate.confidence,
        source_relation=candidate.relation_type,
        reason=candidate.reason,
    )


def _candidate_to_row(candidate: RelationCandidate) -> dict:
    return {
        "relation_type": candidate.relation_type,
        "market_a_id": candidate.market_a_id,
        "market_b_id": candidate.market_b_id,
        "direction": candidate.direction,
        "confidence": candidate.confidence,
        "trade_allowed": candidate.trade_allowed,
        "risk_flags": list(candidate.risk_flags),
        "reason": candidate.reason,
    }


def _merge_candidates(primary: List[RelationCandidate], secondary_rows: List[dict]) -> List[RelationCandidate]:
    merged: List[RelationCandidate] = []
    seen = set()
    for candidate in primary:
        key = _candidate_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        merged.append(candidate)
    for row in secondary_rows:
        candidate = _candidate_from_row(row)
        key = _candidate_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        merged.append(candidate)
    return merged


def _candidate_key(candidate: RelationCandidate) -> tuple:
    return (
        candidate.relation_type,
        candidate.market_a_id,
        candidate.market_b_id,
        candidate.direction,
        round(candidate.confidence, 6),
        candidate.trade_allowed,
        tuple(candidate.risk_flags),
        candidate.reason,
    )


def _candidate_from_row(row: dict) -> RelationCandidate:
    return RelationCandidate(
        relation_type=str(row.get("relation_type") or ""),
        market_a_id=str(row.get("market_a_id") or ""),
        market_b_id=str(row.get("market_b_id") or ""),
        direction=str(row.get("direction") or ""),
        confidence=float(row.get("confidence") or 0.0),
        trade_allowed=bool(row.get("trade_allowed")) if "trade_allowed" in row else True,
        risk_flags=[str(flag) for flag in row.get("risk_flags", []) or []],
        reason=str(row.get("reason") or ""),
    )


def _add_market_id(target: Set[str], row: dict, key: str) -> None:
    value = row.get(key)
    if value:
        target.add(str(value))


def _market_ids_from_group_rule(rule: dict) -> List[str]:
    raw_market_ids = rule.get("market_ids")
    if raw_market_ids is None:
        raw_market_ids = rule.get("markets")
    if not isinstance(raw_market_ids, list):
        return []
    return [str(market_id) for market_id in raw_market_ids if market_id]


def _load_json(path: Optional[Path]) -> Optional[dict]:
    if path is None:
        return None
    return json.loads(path.read_text())


def _has_fallback_text(market: MarketText) -> bool:
    text = f"{market.question} {market.description}".lower()
    return any(phrase in text for phrase in ["50-50", "50/50", "neither occurs", "fallback"])


def _dedupe_flags(flags: List[str]) -> List[str]:
    seen = set()
    ordered = []
    for flag in flags:
        if flag in seen:
            continue
        seen.add(flag)
        ordered.append(flag)
    return ordered


def _implication_to_row(rule: DiscoveredImplication) -> dict:
    return {
        "antecedent": rule.antecedent,
        "consequent": rule.consequent,
        "confidence": rule.confidence,
        "source_relation": rule.source_relation,
        "reason": rule.reason,
    }


def _mutual_exclusion_to_row(rule: DiscoveredMutualExclusion) -> dict:
    return {
        "first": rule.first,
        "second": rule.second,
        "confidence": rule.confidence,
        "source_relation": rule.source_relation,
        "reason": rule.reason,
    }


def _loads_json_list(value) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if not value:
        return []
    try:
        loaded = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(loaded, list):
        return []
    return [str(item) for item in loaded]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug


def _batches(markets: Sequence[MarketText], batch_size: int) -> Iterable[List[MarketText]]:
    for index in range(0, len(markets), batch_size):
        yield list(markets[index : index + batch_size])


def _batch_with_context(
    batch: Sequence[MarketText],
    all_markets: Sequence[MarketText],
    context_market_limit: int,
) -> List[MarketText]:
    if context_market_limit == 0:
        return list(batch)

    batch_ids = {market.market_id for market in batch}
    context = [market for market in all_markets if market.market_id not in batch_ids]
    ranked_context = sorted(context, key=lambda market: _context_rank(batch, market))
    return list(batch) + ranked_context[:context_market_limit]


def _context_rank(batch: Sequence[MarketText], market: MarketText) -> tuple:
    batch_neg_risk_ids = {item.neg_risk_market_id for item in batch if item.neg_risk_market_id}
    batch_categories = {item.category for item in batch if item.category}
    same_neg_risk = market.neg_risk_market_id in batch_neg_risk_ids if market.neg_risk_market_id else False
    same_category = market.category in batch_categories if market.category else False
    return (not same_neg_risk, not same_category, market.market_id)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
