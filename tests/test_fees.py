import unittest

from poly_strategy.fees import (
    fee_adjusted_buy_cost,
    kalshi_taker_fee_per_share,
    polymarket_taker_fee_per_share,
    taker_fee_per_share,
)


class FeeTests(unittest.TestCase):
    def test_polymarket_taker_fee_per_share_uses_price_times_one_minus_price(self):
        self.assertAlmostEqual(polymarket_taker_fee_per_share(0.50, 0.03), 0.0075)
        self.assertAlmostEqual(polymarket_taker_fee_per_share(0.20, 0.072), 0.01152)

    def test_fee_adjusted_buy_cost_adds_per_share_fee_to_notional(self):
        total = fee_adjusted_buy_cost(price=0.50, quantity=20, fee_rate=0.03)
        self.assertAlmostEqual(total, 10.15)

    def test_kalshi_taker_fee_uses_expected_earnings_formula(self):
        self.assertAlmostEqual(kalshi_taker_fee_per_share(0.50), 0.0175)
        self.assertAlmostEqual(taker_fee_per_share("kalshi", 0.20, 0.07), 0.0112)
        self.assertAlmostEqual(taker_fee_per_share("polymarket", 0.20, 0.03), 0.0048)


if __name__ == "__main__":
    unittest.main()
