import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from poly_strategy.collectors import raw_gamma_markets_from_ndjson
from poly_strategy.models import (
    BinaryMarketSnapshot,
    CollectivelyExhaustiveRule,
    ComplementRule,
    EquivalenceRule,
    ExhaustiveGroupRule,
    ImplicationRule,
    MutualExclusionRule,
    NegRiskGroupRule,
    OrderBook,
    Opportunity,
)
from poly_strategy.orderbook import Level
from poly_strategy.paper import PaperRejection, PaperSelection, PaperTrade, select_paper_trades
from poly_strategy.scanner import (
    find_collectively_exhaustive_arbs,
    find_complement_arbs,
    find_equivalent_arbs,
    find_exhaustive_group_arbs,
    find_implication_arbs,
    find_mutual_exclusion_basket_arbs,
    find_mutually_exclusive_arbs,
    find_neg_risk_group_arbs,
    find_yes_no_bundle_arbs,
)


@dataclass(frozen=True)
class OpportunityRun:
    key: str
    market_id: str
    start_ts: Optional[str]
    end_ts: Optional[str]
    observation_count: int
    max_edge_per_share: float

    @property
    def duration_seconds(self) -> float:
        if not self.start_ts or not self.end_ts:
            return 0.0
        return max(0.0, (_parse_ts(self.end_ts) - _parse_ts(self.start_ts)).total_seconds())


@dataclass(frozen=True)
class ReplayResult:
    snapshot_count: int
    opportunities: List[Opportunity]
    paper_trades: List[PaperTrade]
    paper_rejections: List[PaperRejection]
    runs: List[OpportunityRun]
    last_snapshot_ts: Optional[str] = None

    @property
    def opportunity_count(self) -> int:
        return len(self.opportunities)

    @property
    def total_edge(self) -> float:
        return sum(opportunity.total_edge for opportunity in self.opportunities)

    @property
    def paper_trade_count(self) -> int:
        return len(self.paper_trades)

    @property
    def paper_capital_used(self) -> float:
        return sum(trade.capital_used for trade in self.paper_trades)

    @property
    def paper_edge(self) -> float:
        return sum(trade.edge for trade in self.paper_trades)


@dataclass(frozen=True)
class RuleSet:
    implications: List[ImplicationRule] = field(default_factory=list)
    mutual_exclusions: List[MutualExclusionRule] = field(default_factory=list)
    equivalences: List[EquivalenceRule] = field(default_factory=list)
    collectively_exhaustive: List[CollectivelyExhaustiveRule] = field(default_factory=list)
    exhaustive_groups: List[ExhaustiveGroupRule] = field(default_factory=list)
    neg_risk_groups: List[NegRiskGroupRule] = field(default_factory=list)
    complements: List[ComplementRule] = field(default_factory=list)


def replay_ndjson(
    path: Path,
    min_net_edge: float = 0.0,
    max_capital_per_trade: Optional[float] = None,
    bankroll: Optional[float] = None,
    rules_path: Optional[Path] = None,
    gamma_path: Optional[Path] = None,
) -> ReplayResult:
    snapshots = list(_read_binary_snapshots(path))
    rule_set = load_rule_set(rules_path, gamma_path=gamma_path)
    opportunities: List[Opportunity] = []
    opportunities_by_snapshot: List[List[Opportunity]] = []
    for batch in _batches_by_ts(snapshots):
        batch_opportunities = scan_snapshot_batch(batch, rule_set, min_net_edge=min_net_edge)
        opportunities_by_snapshot.append(batch_opportunities)
        opportunities.extend(batch_opportunities)
    paper_selection = _paper_selection_by_batch(opportunities_by_snapshot, max_capital_per_trade, bankroll)
    return ReplayResult(
        snapshot_count=len(snapshots),
        opportunities=opportunities,
        paper_trades=paper_selection.trades,
        paper_rejections=paper_selection.rejections,
        runs=_opportunity_runs(opportunities_by_snapshot),
        last_snapshot_ts=snapshots[-1].ts if snapshots else None,
    )


def load_rule_set(
    path: Optional[Path] = None,
    min_confidence: float = 0.95,
    gamma_path: Optional[Path] = None,
) -> RuleSet:
    return RuleSet(
        implications=load_rules(path, min_confidence=min_confidence) if path else [],
        mutual_exclusions=load_mutually_exclusive_rules(path, min_confidence=min_confidence) if path else [],
        equivalences=load_equivalence_rules(path, min_confidence=min_confidence) if path else [],
        collectively_exhaustive=load_collectively_exhaustive_rules(path, min_confidence=min_confidence) if path else [],
        exhaustive_groups=load_exhaustive_group_rules(path, min_confidence=min_confidence) if path else [],
        neg_risk_groups=load_neg_risk_group_rules(gamma_path) if gamma_path else [],
        complements=load_complement_rules(path, min_confidence=min_confidence) if path else [],
    )


def scan_snapshot_batch(
    snapshots: List[BinaryMarketSnapshot],
    rule_set: Optional[RuleSet] = None,
    min_net_edge: float = 0.0,
) -> List[Opportunity]:
    rules = rule_set or RuleSet()
    opportunities: List[Opportunity] = []
    for snapshot in snapshots:
        opportunities.extend(find_yes_no_bundle_arbs(snapshot, min_net_edge=min_net_edge))
    opportunities.extend(find_implication_arbs(snapshots, rules.implications, min_net_edge=min_net_edge))
    opportunities.extend(find_mutually_exclusive_arbs(snapshots, rules.mutual_exclusions, min_net_edge=min_net_edge))
    opportunities.extend(
        find_mutual_exclusion_basket_arbs(snapshots, rules.mutual_exclusions, min_net_edge=min_net_edge)
    )
    opportunities.extend(find_equivalent_arbs(snapshots, rules.equivalences, min_net_edge=min_net_edge))
    opportunities.extend(
        find_collectively_exhaustive_arbs(snapshots, rules.collectively_exhaustive, min_net_edge=min_net_edge)
    )
    opportunities.extend(find_exhaustive_group_arbs(snapshots, rules.exhaustive_groups, min_net_edge=min_net_edge))
    opportunities.extend(find_neg_risk_group_arbs(snapshots, rules.neg_risk_groups, min_net_edge=min_net_edge))
    opportunities.extend(find_complement_arbs(snapshots, rules.complements, min_net_edge=min_net_edge))
    return opportunities


def load_rules(path: Path, min_confidence: float = 0.95) -> List[ImplicationRule]:
    row = json.loads(path.read_text())
    rules = []
    for rule in row.get("implications", []):
        if not _rule_is_tradeable(rule, "antecedent", "consequent", min_confidence):
            continue
        rules.append(
            ImplicationRule(
                antecedent_market_id=rule["antecedent"],
                consequent_market_id=rule["consequent"],
            )
        )
    return rules


def load_mutually_exclusive_rules(path: Path, min_confidence: float = 0.95) -> List[MutualExclusionRule]:
    return _load_pair_rules(path, "mutually_exclusive", MutualExclusionRule, min_confidence)


def load_equivalence_rules(path: Path, min_confidence: float = 0.95) -> List[EquivalenceRule]:
    return _load_pair_rules(path, "equivalent", EquivalenceRule, min_confidence)


def load_collectively_exhaustive_rules(path: Path, min_confidence: float = 0.95) -> List[CollectivelyExhaustiveRule]:
    return _load_pair_rules(path, "collectively_exhaustive", CollectivelyExhaustiveRule, min_confidence)


def load_exhaustive_group_rules(path: Path, min_confidence: float = 0.95) -> List[ExhaustiveGroupRule]:
    row = json.loads(path.read_text())
    rules = []
    for rule in row.get("exhaustive_groups", []):
        if not _group_rule_is_tradeable(rule, min_confidence):
            continue
        rules.append(ExhaustiveGroupRule(market_ids=_market_ids_from_group_rule(rule)))
    return rules


def load_complement_rules(path: Path, min_confidence: float = 0.95) -> List[ComplementRule]:
    return _load_pair_rules(path, "complement", ComplementRule, min_confidence)


def load_neg_risk_group_rules(path: Path) -> List[NegRiskGroupRule]:
    grouped = defaultdict(list)
    for market in raw_gamma_markets_from_ndjson(path):
        if not _is_tradeable_binary_gamma_market(market):
            continue
        group_id = str(market.get("negRiskMarketID") or "").strip()
        market_id = str(market.get("id") or market.get("conditionId") or "").strip()
        if not group_id or not market_id:
            continue
        grouped[group_id].append(market)

    rules = []
    for group_id, markets in sorted(grouped.items()):
        market_ids = []
        seen = set()
        for market in sorted(markets, key=_neg_risk_market_sort_key):
            market_id = str(market.get("id") or market.get("conditionId") or "").strip()
            if market_id in seen:
                continue
            seen.add(market_id)
            market_ids.append(market_id)
        if len(market_ids) >= 2:
            rules.append(NegRiskGroupRule(market_ids=market_ids, neg_risk_market_id=group_id))
    return rules


def _load_pair_rules(path: Path, section: str, rule_cls, min_confidence: float):
    row = json.loads(path.read_text())
    source_rules = row.get(section)
    if source_rules is None:
        source_rules = _pair_rows_from_candidates(row.get("candidates", []), section)

    rules = []
    for rule in source_rules:
        if not _rule_is_tradeable(rule, "first", "second", min_confidence):
            continue
        rules.append(rule_cls(first_market_id=rule["first"], second_market_id=rule["second"]))
    return rules


def _pair_rows_from_candidates(candidates: List[dict], relation_type: str) -> List[dict]:
    rows = []
    for candidate in candidates:
        if candidate.get("relation_type") != relation_type:
            continue
        rows.append(
            {
                "first": candidate.get("market_a_id"),
                "second": candidate.get("market_b_id"),
                "confidence": candidate.get("confidence"),
                "trade_allowed": candidate.get("trade_allowed"),
                "risk_flags": candidate.get("risk_flags"),
            }
        )
    return rows


def _rule_is_tradeable(rule: dict, first_key: str, second_key: str, min_confidence: float) -> bool:
    if first_key not in rule or second_key not in rule:
        return False
    if not rule[first_key] or not rule[second_key]:
        return False
    if rule.get("trade_allowed") is False:
        return False
    if rule.get("risk_flags"):
        return False
    if "confidence" in rule and float(rule["confidence"]) < min_confidence:
        return False
    return True


def _group_rule_is_tradeable(rule: dict, min_confidence: float) -> bool:
    if len(_market_ids_from_group_rule(rule)) < 2:
        return False
    if rule.get("trade_allowed") is False:
        return False
    if rule.get("risk_flags"):
        return False
    if "confidence" in rule and float(rule["confidence"]) < min_confidence:
        return False
    return True


def _market_ids_from_group_rule(rule: dict) -> List[str]:
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


def _is_tradeable_binary_gamma_market(market: dict) -> bool:
    if market.get("closed") is True:
        return False
    if market.get("enableOrderBook") is False:
        return False
    if market.get("acceptingOrders") is False:
        return False
    outcomes = _loads_json_list(market.get("outcomes"))
    if [str(outcome).lower() for outcome in outcomes] != ["yes", "no"]:
        return False
    return len(_loads_json_list(market.get("clobTokenIds"))) == 2


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


def _neg_risk_market_sort_key(market: dict) -> tuple:
    threshold = str(market.get("groupItemThreshold") or "").strip()
    try:
        return (0, float(threshold), str(market.get("id") or market.get("conditionId") or ""))
    except ValueError:
        return (
            1,
            str(market.get("groupItemTitle") or ""),
            str(market.get("id") or market.get("conditionId") or ""),
        )


def _read_binary_snapshots(path: Path) -> Iterable[BinaryMarketSnapshot]:
    with path.open() as handle:
        yield from snapshots_from_ndjson_lines(handle)


def snapshots_from_ndjson_lines(lines: Iterable[str]) -> Iterable[BinaryMarketSnapshot]:
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        row = json.loads(line)
        if row.get("type") != "binary_snapshot":
            continue
        yield snapshot_from_row(row)


def snapshot_from_row(row: dict) -> BinaryMarketSnapshot:
    return BinaryMarketSnapshot(
        market_id=row["market_id"],
        venue=row["venue"],
        yes=_book_from_row(row["yes"]),
        no=_book_from_row(row["no"]),
        fee_rate=float(row.get("fee_rate", 0.0)),
        ts=row.get("ts"),
    )


def _book_from_row(row: dict) -> OrderBook:
    return OrderBook(
        asks=[Level(float(price), float(size)) for price, size in row.get("asks", [])],
        bids=[Level(float(price), float(size)) for price, size in row.get("bids", [])],
        token_id=str(row.get("token_id")) if row.get("token_id") else None,
    )


def _batches_by_ts(snapshots: Iterable[BinaryMarketSnapshot]) -> Iterable[List[BinaryMarketSnapshot]]:
    batch: List[BinaryMarketSnapshot] = []
    current_ts = object()
    for snapshot in snapshots:
        if snapshot.ts != current_ts and batch:
            yield batch
            batch = []
        current_ts = snapshot.ts
        batch.append(snapshot)
    if batch:
        yield batch


def _paper_selection_by_batch(
    opportunities_by_snapshot: Iterable[List[Opportunity]],
    max_capital_per_trade: Optional[float],
    bankroll: Optional[float],
) -> PaperSelection:
    trades = []
    rejections = []
    for opportunities in opportunities_by_snapshot:
        selection = select_paper_trades(opportunities, max_capital_per_trade=max_capital_per_trade, bankroll=bankroll)
        trades.extend(selection.trades)
        rejections.extend(selection.rejections)
    return PaperSelection(trades=trades, rejections=rejections)


def _opportunity_runs(opportunities_by_snapshot: Iterable[List[Opportunity]]) -> List[OpportunityRun]:
    active: Dict[str, Tuple[str, Optional[str], Optional[str], int, float]] = {}
    closed: List[OpportunityRun] = []

    for opportunities in opportunities_by_snapshot:
        seen = set()
        for opportunity in opportunities:
            key = _opportunity_key(opportunity)
            seen.add(key)
            market_id = _opportunity_market_id(opportunity)
            if key in active:
                _, start_ts, _, count, max_edge = active[key]
                active[key] = (market_id, start_ts, opportunity.ts, count + 1, max(max_edge, opportunity.net_edge_per_share))
            else:
                active[key] = (market_id, opportunity.ts, opportunity.ts, 1, opportunity.net_edge_per_share)

        for key in list(active):
            if key not in seen:
                closed.append(_run_from_active(key, active.pop(key)))

    for key, value in active.items():
        closed.append(_run_from_active(key, value))
    return closed


def _run_from_active(key: str, value: Tuple[str, Optional[str], Optional[str], int, float]) -> OpportunityRun:
    market_id, start_ts, end_ts, count, max_edge = value
    return OpportunityRun(
        key=key,
        market_id=market_id,
        start_ts=start_ts,
        end_ts=end_ts,
        observation_count=count,
        max_edge_per_share=max_edge,
    )


def _opportunity_key(opportunity: Opportunity) -> str:
    legs = "|".join(sorted(f"{leg.venue}:{leg.market_id}:{leg.token}:{leg.side}" for leg in opportunity.legs))
    return f"{opportunity.kind}:{legs}"


def _opportunity_market_id(opportunity: Opportunity) -> str:
    if not opportunity.legs:
        return ""
    return opportunity.legs[0].market_id


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
