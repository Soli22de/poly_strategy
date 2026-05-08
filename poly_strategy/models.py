from dataclasses import dataclass
from typing import List, Optional

from poly_strategy.orderbook import Level


@dataclass(frozen=True)
class OrderBook:
    asks: List[Level]
    bids: List[Level]


@dataclass(frozen=True)
class BinaryMarketSnapshot:
    market_id: str
    venue: str
    yes: OrderBook
    no: OrderBook
    fee_rate: float
    ts: Optional[str] = None


VenueBinarySnapshot = BinaryMarketSnapshot


@dataclass(frozen=True)
class ImplicationRule:
    antecedent_market_id: str
    consequent_market_id: str


@dataclass(frozen=True)
class MutualExclusionRule:
    first_market_id: str
    second_market_id: str


@dataclass(frozen=True)
class EquivalenceRule:
    first_market_id: str
    second_market_id: str


@dataclass(frozen=True)
class CollectivelyExhaustiveRule:
    first_market_id: str
    second_market_id: str


@dataclass(frozen=True)
class ComplementRule:
    first_market_id: str
    second_market_id: str


@dataclass(frozen=True)
class Leg:
    venue: str
    market_id: str
    token: str
    side: str
    average_price: float
    quantity: float


@dataclass(frozen=True)
class Opportunity:
    kind: str
    quantity: float
    cost_per_share: float
    net_edge_per_share: float
    legs: List[Leg]
    ts: Optional[str] = None

    @property
    def total_edge(self) -> float:
        return self.net_edge_per_share * self.quantity
