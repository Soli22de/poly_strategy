import unittest

from poly_strategy.execution import ExecutionConfigError, PolymarketClobExecutor, build_execution_plan, plan_to_row
from poly_strategy.models import Leg, Opportunity
from poly_strategy.paper import PaperTrade


class ExecutionTests(unittest.TestCase):
    def test_build_execution_plan_requires_token_ids_and_rounds_buy_price_up(self):
        opportunity = Opportunity(
            kind="yes_no_bundle",
            quantity=10,
            cost_per_share=0.80,
            net_edge_per_share=0.10,
            legs=[
                Leg("polymarket", "a", "YES", "buy", 0.401, 10, "yes-token", 0.45),
                Leg("polymarket", "a", "NO", "buy", 0.399, 10, "no-token", 0.40),
            ],
            ts="2026-05-09T00:00:00Z",
        )
        trade = PaperTrade(opportunity=opportunity, quantity=5, capital_used=4, edge=0.5)

        plan = build_execution_plan(trade, slippage_bps=50, tick_size="0.01")
        row = plan_to_row(plan)

        self.assertTrue(row["dry_run"])
        self.assertEqual(len(row["orders"]), 2)
        self.assertEqual(row["orders"][0]["token_id"], "yes-token")
        self.assertEqual(row["orders"][0]["price"], 0.46)
        self.assertEqual(row["orders"][0]["size"], 5)
        self.assertEqual(row["orders"][0]["order_type"], "FOK")

    def test_build_execution_plan_rejects_missing_token_id(self):
        opportunity = Opportunity(
            kind="yes_no_bundle",
            quantity=10,
            cost_per_share=0.80,
            net_edge_per_share=0.10,
            legs=[Leg("polymarket", "a", "YES", "buy", 0.40, 10)],
        )
        trade = PaperTrade(opportunity=opportunity, quantity=5, capital_used=4, edge=0.5)

        with self.assertRaises(ExecutionConfigError):
            build_execution_plan(trade)

    def test_executor_returns_dry_run_rows_without_sdk_or_private_key(self):
        plan = build_execution_plan(
            PaperTrade(
                opportunity=Opportunity(
                    kind="yes_no_bundle",
                    quantity=10,
                    cost_per_share=0.80,
                    net_edge_per_share=0.10,
                    legs=[Leg("polymarket", "a", "YES", "buy", 0.40, 10, "yes-token")],
                ),
                quantity=5,
                capital_used=4,
                edge=0.5,
            )
        )

        executor = PolymarketClobExecutor(private_key="test-key")
        responses = executor.post_plan(plan, allow_live=False)

        self.assertEqual(responses[0]["dry_run"], True)
        self.assertEqual(responses[0]["order"]["token_id"], "yes-token")

    def test_executor_blocks_nonatomic_multi_leg_live_without_acknowledgement(self):
        plan = build_execution_plan(
            PaperTrade(
                opportunity=Opportunity(
                    kind="yes_no_bundle",
                    quantity=10,
                    cost_per_share=0.80,
                    net_edge_per_share=0.10,
                    legs=[
                        Leg("polymarket", "a", "YES", "buy", 0.40, 10, "yes-token"),
                        Leg("polymarket", "a", "NO", "buy", 0.40, 10, "no-token"),
                    ],
                ),
                quantity=5,
                capital_used=4,
                edge=0.5,
            ),
            dry_run=False,
        )

        executor = PolymarketClobExecutor(private_key="test-key")
        with self.assertRaises(ExecutionConfigError):
            executor.post_plan(plan, allow_live=True)


if __name__ == "__main__":
    unittest.main()
