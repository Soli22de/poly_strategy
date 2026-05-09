import unittest

from poly_strategy.orderbook import Level, insufficient_liquidity, take_levels


class OrderBookTests(unittest.TestCase):
    def test_take_levels_consumes_depth_until_quantity_is_filled(self):
        fill = take_levels([Level(0.10, 5), Level(0.12, 10)], quantity=12)

        self.assertEqual(fill.quantity, 12)
        self.assertAlmostEqual(fill.notional, 0.10 * 5 + 0.12 * 7)
        self.assertAlmostEqual(fill.average_price, fill.notional / 12)
        self.assertAlmostEqual(fill.worst_price, 0.12)

    def test_take_levels_reports_insufficient_liquidity(self):
        with self.assertRaisesRegex(ValueError, "insufficient liquidity"):
            take_levels([Level(0.10, 5)], quantity=6)

    def test_insufficient_liquidity_identifies_missing_depth(self):
        self.assertTrue(insufficient_liquidity([Level(0.10, 5)], quantity=6))
        self.assertFalse(insufficient_liquidity([Level(0.10, 5), Level(0.12, 1)], quantity=6))


if __name__ == "__main__":
    unittest.main()
