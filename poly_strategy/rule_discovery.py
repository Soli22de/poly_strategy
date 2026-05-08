import json
import re
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
    mutual_exclusions: List[DiscoveredMutualExclusion] = field(default_factory=list)
    equivalents: List[DiscoveredMutualExclusion] = field(default_factory=list)
    collectively_exhaustive: List[DiscoveredMutualExclusion] = field(default_factory=list)
    complements: List[DiscoveredMutualExclusion] = field(default_factory=list)


@dataclass(frozen=True)
class DiscoveryResult:
    markets_read: int
    candidates_found: int
    implications_written: int
    mutual_exclusions_written: int = 0
    equivalents_written: int = 0
    collectively_exhaustive_written: int = 0
    complements_written: int = 0


def read_market_texts(path: Path) -> List[MarketText]:
    markets = []
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
                markets.append(market)
    return markets


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
        "implications": [_implication_to_row(rule) for rule in implications],
        "equivalent": [_mutual_exclusion_to_row(rule) for rule in equivalents],
        "mutually_exclusive": [_mutual_exclusion_to_row(rule) for rule in mutual_exclusions],
        "collectively_exhaustive": [_mutual_exclusion_to_row(rule) for rule in collectively_exhaustive],
        "complement": [_mutual_exclusion_to_row(rule) for rule in complements],
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
    generated_at: Optional[str] = None,
) -> DiscoveryResult:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    if max_markets is not None and max_markets < 1:
        raise ValueError("max_markets must be at least 1")

    markets = read_market_texts(raw_path)
    if max_markets is not None:
        markets = markets[:max_markets]

    candidates: List[RelationCandidate] = []
    for batch in _batches(markets, batch_size):
        candidates.extend(client.discover_relations(batch))

    known_market_ids = {market.market_id for market in markets}
    implications = filter_implications(candidates, known_market_ids, min_confidence)
    mutual_exclusions = filter_mutual_exclusions(candidates, known_market_ids, min_confidence)
    equivalents = filter_equivalents(candidates, known_market_ids, min_confidence)
    collectively_exhaustive = filter_collectively_exhaustive(candidates, known_market_ids, min_confidence)
    complements = filter_complements(candidates, known_market_ids, min_confidence)
    ruleset = DiscoveredRuleSet(
        generated_at=generated_at or _utc_now(),
        min_confidence=min_confidence,
        candidates=candidates,
        implications=implications,
        mutual_exclusions=mutual_exclusions,
        equivalents=equivalents,
        collectively_exhaustive=collectively_exhaustive,
        complements=complements,
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
    )


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
        }
        for market in markets
    ]


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

    return MarketText(
        market_id=market_id,
        question=question,
        description=description,
        outcomes=outcomes,
        end_date=end_date,
        category=category,
        slug=slug,
    )


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


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
