def polymarket_taker_fee_per_share(price: float, fee_rate: float) -> float:
    if price < 0 or price > 1:
        raise ValueError("price must be between 0 and 1")
    if fee_rate < 0:
        raise ValueError("fee_rate must be non-negative")
    return fee_rate * price * (1 - price)


def fee_adjusted_buy_cost(price: float, quantity: float, fee_rate: float) -> float:
    if quantity < 0:
        raise ValueError("quantity must be non-negative")
    return quantity * (price + polymarket_taker_fee_per_share(price, fee_rate))

