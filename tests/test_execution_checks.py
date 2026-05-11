import unittest

from poly_strategy.execution_checks import pretrade_check_row
from poly_strategy.models import Leg, Opportunity
from poly_strategy.paper import PaperTrade


class ExecutionCheckTests(unittest.TestCase):
    def test_pretrade_check_flags_missing_token_and_leg_count(self):
        opportunity = Opportunity(
            kind="basket",
            quantity=10,
            cost_per_share=0.90,
            net_edge_per_share=0.10,
            legs=[
                Leg("polymarket", "a", "YES", "buy", 0.40, 10, "yes-token"),
                Leg("polymarket", "b", "YES", "buy", 0.50, 10),
            ],
        )
        trade = PaperTrade(opportunity=opportunity, quantity=10, capital_used=9, edge=1)

        row = pretrade_check_row(trade, max_leg_count=1)

        self.assertFalse(row["passed"])
        failed = {check["name"] for check in row["checks"] if not check["passed"]}
        self.assertEqual(failed, {"all_token_ids_present", "max_leg_count"})
        self.assertAlmostEqual(row["quality"]["roi"], 0.10 / 0.90)

    def test_pretrade_check_can_require_limit_price_edge(self):
        opportunity = Opportunity(
            kind="bundle",
            quantity=10,
            cost_per_share=0.90,
            net_edge_per_share=0.10,
            legs=[
                Leg("polymarket", "a", "YES", "buy", 0.40, 10, "yes-token"),
                Leg("polymarket", "a", "NO", "buy", 0.50, 10, "no-token"),
            ],
        )
        trade = PaperTrade(opportunity=opportunity, quantity=10, capital_used=9, edge=1)

        passed = pretrade_check_row(
            trade,
            plan={"orders": [{"price": 0.45}, {"price": 0.50}]},
            min_limit_edge_per_share=0.04,
            min_limit_roi=0.04,
        )
        failed = pretrade_check_row(
            trade,
            plan={"orders": [{"price": 0.50}, {"price": 0.50}]},
            min_limit_edge_per_share=0.01,
        )

        self.assertTrue(passed["passed"])
        self.assertAlmostEqual(passed["limit_price_summary"]["edge_per_share"], 0.05)
        self.assertFalse(failed["passed"])
        self.assertIn("min_limit_edge_per_share", {check["name"] for check in failed["checks"] if not check["passed"]})


if __name__ == "__main__":
    unittest.main()
