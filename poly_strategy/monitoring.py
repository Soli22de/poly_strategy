from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from poly_strategy.backtest import OpportunityRun, RuleSet, scan_snapshot_batch
from poly_strategy.models import BinaryMarketSnapshot, Opportunity
from poly_strategy.paper import PaperRejection, PaperSelection, PaperTrade, opportunity_key, select_paper_trades


@dataclass(frozen=True)
class IncrementalBatchResult:
    snapshot_count: int
    opportunities: List[Opportunity]
    current_opportunities: List[Opportunity]
    paper_selection: PaperSelection
    current_runs: List[OpportunityRun]
    last_snapshot_ts: Optional[str]


@dataclass
class IncrementalReplayState:
    snapshot_count: int = 0
    opportunities: List[Opportunity] = field(default_factory=list)
    paper_trades: List[PaperTrade] = field(default_factory=list)
    paper_rejections: List[PaperRejection] = field(default_factory=list)
    last_snapshot_ts: Optional[str] = None
    closed_runs: List[OpportunityRun] = field(default_factory=list)
    _active_runs: Dict[str, Tuple[str, Optional[str], Optional[str], int, float]] = field(default_factory=dict)

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

    @property
    def runs(self) -> List[OpportunityRun]:
        active_runs = [_run_from_active(key, value) for key, value in self._active_runs.items()]
        return self.closed_runs + active_runs

    def apply_snapshots(
        self,
        snapshots: Iterable[BinaryMarketSnapshot],
        rule_set: RuleSet,
        min_net_edge: float = 0.0,
        max_capital_per_trade: Optional[float] = None,
        bankroll: Optional[float] = None,
        min_paper_roi: Optional[float] = None,
        min_paper_edge: Optional[float] = None,
        min_paper_quantity: float = 1e-9,
    ) -> IncrementalBatchResult:
        new_snapshots = list(snapshots)
        self.snapshot_count += len(new_snapshots)

        all_opportunities: List[Opportunity] = []
        current_opportunities: List[Opportunity] = []
        current_runs: List[OpportunityRun] = []
        trades: List[PaperTrade] = []
        rejections: List[PaperRejection] = []

        for batch in _batches_by_ts(new_snapshots):
            current_opportunities = scan_snapshot_batch(batch, rule_set, min_net_edge=min_net_edge)
            selection = select_paper_trades(
                current_opportunities,
                max_capital_per_trade=max_capital_per_trade,
                bankroll=bankroll,
                min_quantity=min_paper_quantity,
                min_roi=min_paper_roi,
                min_edge=min_paper_edge,
            )
            current_runs = self._update_runs(current_opportunities)
            self.last_snapshot_ts = batch[-1].ts if batch else self.last_snapshot_ts
            all_opportunities.extend(current_opportunities)
            trades.extend(selection.trades)
            rejections.extend(selection.rejections)

        self.opportunities.extend(all_opportunities)
        self.paper_trades.extend(trades)
        self.paper_rejections.extend(rejections)

        return IncrementalBatchResult(
            snapshot_count=len(new_snapshots),
            opportunities=all_opportunities,
            current_opportunities=current_opportunities,
            paper_selection=PaperSelection(trades=trades, rejections=rejections),
            current_runs=current_runs,
            last_snapshot_ts=self.last_snapshot_ts,
        )

    def _update_runs(self, opportunities: List[Opportunity]) -> List[OpportunityRun]:
        seen = set()
        for opportunity in opportunities:
            key = opportunity_key(opportunity)
            seen.add(key)
            market_id = _opportunity_market_id(opportunity)
            if key in self._active_runs:
                _, start_ts, _, count, max_edge = self._active_runs[key]
                self._active_runs[key] = (
                    market_id,
                    start_ts,
                    opportunity.ts,
                    count + 1,
                    max(max_edge, opportunity.net_edge_per_share),
                )
            else:
                self._active_runs[key] = (
                    market_id,
                    opportunity.ts,
                    opportunity.ts,
                    1,
                    opportunity.net_edge_per_share,
                )

        for key in list(self._active_runs):
            if key not in seen:
                self.closed_runs.append(_run_from_active(key, self._active_runs.pop(key)))

        return [_run_from_active(key, self._active_runs[key]) for key in seen if key in self._active_runs]


def stable_current_opportunities(
    opportunities: List[Opportunity],
    runs: List[OpportunityRun],
    min_run_observations: int = 1,
    min_run_seconds: float = 0.0,
) -> List[Opportunity]:
    if min_run_observations <= 1 and min_run_seconds <= 0:
        return opportunities

    stable_keys = {
        run.key
        for run in runs
        if run.observation_count >= min_run_observations and run.duration_seconds >= min_run_seconds
    }
    return [opportunity for opportunity in opportunities if opportunity_key(opportunity) in stable_keys]


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


def _opportunity_market_id(opportunity: Opportunity) -> str:
    if not opportunity.legs:
        return ""
    return opportunity.legs[0].market_id
