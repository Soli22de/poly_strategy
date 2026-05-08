import unittest

from poly_strategy.fees import fee_adjusted_buy_cost, polymarket_taker_fee_per_share


class FeeTests(unittest.TestCase):
    def test_polymarket_taker_fee_per_share_uses_price_times_one_minus_price(self):
        self.assertAlmostEqual(polymarket_taker_fee_per_share(0.50, 0.03), 0.0075)
        self.assertAlmostEqual(polymarket_taker_fee_per_share(0.20, 0.072), 0.01152)

    def test_fee_adjusted_buy_cost_adds_per_share_fee_to_notional(self):
        total = fee_adjusted_buy_cost(price=0.50, quantity=20, fee_rate=0.03)
        self.assertAlmostEqual(total, 10.15)


if __name__ == "__main__":
    unittest.main()

