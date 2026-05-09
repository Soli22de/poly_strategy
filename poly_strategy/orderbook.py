from dataclasses import dataclass
from typing import Iterable, List


@dataclass(frozen=True)
class Level:
    price: float
    size: float


@dataclass(frozen=True)
class Fill:
    quantity: float
    notional: float
    worst_price: float = 0.0

    @property
    def average_price(self) -> float:
        if self.quantity == 0:
            return 0.0
        return self.notional / self.quantity


def insufficient_liquidity(levels: Iterable[Level], quantity: float) -> bool:
    return sum(level.size for level in levels) + 1e-12 < quantity


def take_levels(levels: List[Level], quantity: float) -> Fill:
    if quantity < 0:
        raise ValueError("quantity must be non-negative")
    if insufficient_liquidity(levels, quantity):
        raise ValueError("insufficient liquidity")

    remaining = quantity
    notional = 0.0
    worst_price = 0.0
    for level in levels:
        if remaining <= 0:
            break
        used = min(remaining, level.size)
        notional += used * level.price
        worst_price = level.price
        remaining -= used

    return Fill(quantity=quantity, notional=notional, worst_price=worst_price)
