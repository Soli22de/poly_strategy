import unittest

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
    VenueBinarySnapshot,
)
from poly_strategy.orderbook import Level
from poly_strategy.scanner import (
    find_collectively_exhaustive_arbs,
    find_complement_arbs,
    find_cross_venue_same_binary,
    find_equivalent_arbs,
    find_exhaustive_group_arbs,
    find_implication_arbs,
    find_mutually_exclusive_arbs,
    find_neg_risk_group_arbs,
    find_yes_no_bundle_arbs,
)


class ScannerTests(unittest.TestCase):
    def test_yes_no_bundle_finds_fee_adjusted_arbitrage(self):
        snapshot = BinaryMarketSnapshot(
            market_id="btc-close-above-100k",
            venue="polymarket",
            yes=OrderBook(asks=[Level(0.45, 100)], bids=[]),
            no=OrderBook(asks=[Level(0.53, 80)], bids=[]),
            fee_rate=0.0,
        )

        opportunities = find_yes_no_bundle_arbs(snapshot, min_net_edge=0.0)

        self.assertEqual(len(opportunities), 1)
        opportunity = opportunities[0]
        self.assertEqual(opportunity.kind, "yes_no_bundle")
        self.assertEqual(opportunity.quantity, 80)
        self.assertAlmostEqual(opportunity.cost_per_share, 0.98)
        self.assertAlmostEqual(opportunity.net_edge_per_share, 0.02)

    def test_yes_no_bundle_rejects_fee_adjusted_negative_edge(self):
        snapshot = BinaryMarketSnapshot(
            market_id="btc-close-above-100k",
            venue="polymarket",
            yes=OrderBook(asks=[Level(0.49, 100)], bids=[]),
            no=OrderBook(asks=[Level(0.50, 100)], bids=[]),
            fee_rate=0.03,
        )

        self.assertEqual(find_yes_no_bundle_arbs(snapshot, min_net_edge=0.0), [])

    def test_yes_no_bundle_uses_profitable_prefix_depth(self):
        snapshot = BinaryMarketSnapshot(
            market_id="prefix-only",
            venue="polymarket",
            yes=OrderBook(asks=[Level(0.45, 10), Level(0.95, 90)], bids=[]),
            no=OrderBook(asks=[Level(0.53, 10), Level(0.95, 90)], bids=[]),
            fee_rate=0.0,
        )

        opportunities = find_yes_no_bundle_arbs(snapshot, min_net_edge=0.01)

        self.assertEqual(len(opportunities), 1)
        self.assertGreater(opportunities[0].quantity, 10)
        self.assertLess(opportunities[0].quantity, 11)
        self.assertGreater(opportunities[0].net_edge_per_share, 0.01)

    def test_cross_venue_same_binary_buys_cheap_yes_and_expensive_no(self):
        polymarket = VenueBinarySnapshot(
            market_id="france-world-cup",
            venue="polymarket",
            yes=OrderBook(asks=[Level(0.16, 100)], bids=[]),
            no=OrderBook(asks=[Level(0.86, 100)], bids=[]),
            fee_rate=0.0,
        )
        kalshi = VenueBinarySnapshot(
            market_id="france-world-cup",
            venue="kalshi",
            yes=OrderBook(asks=[Level(0.20, 100)], bids=[Level(0.19, 90)]),
            no=OrderBook(asks=[Level(0.81, 90)], bids=[]),
            fee_rate=0.0,
        )

        opportunities = find_cross_venue_same_binary(polymarket, kalshi, min_net_edge=0.0)

        self.assertEqual(len(opportunities), 1)
        self.assertEqual(opportunities[0].kind, "cross_venue_same_binary")
        self.assertEqual(opportunities[0].quantity, 90)
        self.assertAlmostEqual(opportunities[0].cost_per_share, 0.97)
        self.assertAlmostEqual(opportunities[0].net_edge_per_share, 0.03)

    def test_implication_arb_buys_consequent_yes_and_antecedent_no(self):
        antecedent = BinaryMarketSnapshot(
            market_id="france-wins-world-cup",
            venue="polymarket",
            yes=OrderBook(asks=[Level(0.16, 100)], bids=[]),
            no=OrderBook(asks=[Level(0.82, 100)], bids=[]),
            fee_rate=0.0,
        )
        consequent = BinaryMarketSnapshot(
            market_id="france-reaches-final",
            venue="polymarket",
            yes=OrderBook(asks=[Level(0.15, 50)], bids=[]),
            no=OrderBook(asks=[Level(0.87, 100)], bids=[]),
            fee_rate=0.0,
        )
        rule = ImplicationRule(
            antecedent_market_id="france-wins-world-cup",
            consequent_market_id="france-reaches-final",
        )

        opportunities = find_implication_arbs([antecedent, consequent], [rule], min_net_edge=0.0)

        self.assertEqual(len(opportunities), 1)
        opportunity = opportunities[0]
        self.assertEqual(opportunity.kind, "implication")
        self.assertEqual(opportunity.quantity, 50)
        self.assertAlmostEqual(opportunity.cost_per_share, 0.97)
        self.assertAlmostEqual(opportunity.net_edge_per_share, 0.03)
        self.assertEqual(opportunity.legs[0].market_id, "france-reaches-final")
        self.assertEqual(opportunity.legs[0].token, "YES")
        self.assertEqual(opportunity.legs[1].market_id, "france-wins-world-cup")
        self.assertEqual(opportunity.legs[1].token, "NO")

    def test_mutually_exclusive_arb_buys_both_no_tokens(self):
        first = BinaryMarketSnapshot(
            market_id="canes-win-stanley-cup",
            venue="polymarket",
            yes=OrderBook(asks=[Level(0.58, 100)], bids=[]),
            no=OrderBook(asks=[Level(0.42, 50)], bids=[]),
            fee_rate=0.0,
        )
        second = BinaryMarketSnapshot(
            market_id="avs-win-stanley-cup",
            venue="polymarket",
            yes=OrderBook(asks=[Level(0.50, 100)], bids=[]),
            no=OrderBook(asks=[Level(0.50, 80)], bids=[]),
            fee_rate=0.0,
        )
        rule = MutualExclusionRule(
            first_market_id="canes-win-stanley-cup",
            second_market_id="avs-win-stanley-cup",
        )

        opportunities = find_mutually_exclusive_arbs([first, second], [rule], min_net_edge=0.0)

        self.assertEqual(len(opportunities), 1)
        opportunity = opportunities[0]
        self.assertEqual(opportunity.kind, "mutually_exclusive")
        self.assertEqual(opportunity.quantity, 50)
        self.assertAlmostEqual(opportunity.cost_per_share, 0.92)
        self.assertAlmostEqual(opportunity.net_edge_per_share, 0.08)
        self.assertEqual(opportunity.legs[0].token, "NO")
        self.assertEqual(opportunity.legs[1].token, "NO")

    def test_mutual_exclusion_basket_arb_buys_all_no_tokens(self):
        first = BinaryMarketSnapshot(
            market_id="a",
            venue="polymarket",
            yes=OrderBook(asks=[Level(0.60, 100)], bids=[]),
            no=OrderBook(asks=[Level(0.30, 50)], bids=[]),
            fee_rate=0.0,
        )
        second = BinaryMarketSnapshot(
            market_id="b",
            venue="polymarket",
            yes=OrderBook(asks=[Level(0.61, 100)], bids=[]),
            no=OrderBook(asks=[Level(0.31, 50)], bids=[]),
            fee_rate=0.0,
        )
        third = BinaryMarketSnapshot(
            market_id="c",
            venue="polymarket",
            yes=OrderBook(asks=[Level(0.62, 100)], bids=[]),
            no=OrderBook(asks=[Level(0.32, 50)], bids=[]),
            fee_rate=0.0,
        )
        rules = [
            MutualExclusionRule("a", "b"),
            MutualExclusionRule("a", "c"),
            MutualExclusionRule("b", "c"),
        ]

        from poly_strategy.scanner import find_mutual_exclusion_basket_arbs

        opportunities = find_mutual_exclusion_basket_arbs([first, second, third], rules, min_net_edge=0.0)

        self.assertEqual(len(opportunities), 1)
        opportunity = opportunities[0]
        self.assertEqual(opportunity.kind, "mutual_exclusion_basket")
        self.assertEqual(opportunity.quantity, 50)
        self.assertAlmostEqual(opportunity.cost_per_share, 0.93)
        self.assertAlmostEqual(opportunity.net_edge_per_share, 1.07)
        self.assertEqual([leg.token for leg in opportunity.legs], ["NO", "NO", "NO"])

    def test_mutual_exclusion_basket_uses_profitable_prefix_depth(self):
        first = BinaryMarketSnapshot(
            market_id="a",
            venue="polymarket",
            yes=OrderBook(asks=[], bids=[]),
            no=OrderBook(asks=[Level(0.40, 5), Level(0.99, 95)], bids=[]),
            fee_rate=0.0,
        )
        second = BinaryMarketSnapshot(
            market_id="b",
            venue="polymarket",
            yes=OrderBook(asks=[], bids=[]),
            no=OrderBook(asks=[Level(0.40, 5), Level(0.99, 95)], bids=[]),
            fee_rate=0.0,
        )
        third = BinaryMarketSnapshot(
            market_id="c",
            venue="polymarket",
            yes=OrderBook(asks=[], bids=[]),
            no=OrderBook(asks=[Level(0.40, 5), Level(0.99, 95)], bids=[]),
            fee_rate=0.0,
        )
        rules = [
            MutualExclusionRule("a", "b"),
            MutualExclusionRule("a", "c"),
            MutualExclusionRule("b", "c"),
        ]

        from poly_strategy.scanner import find_mutual_exclusion_basket_arbs

        opportunities = find_mutual_exclusion_basket_arbs([first, second, third], rules, min_net_edge=0.01)

        self.assertEqual(len(opportunities), 1)
        self.assertGreater(opportunities[0].quantity, 5)
        self.assertLess(opportunities[0].quantity, 10)
        self.assertGreater(opportunities[0].net_edge_per_share, 0.01)

    def test_equivalent_arb_buys_yes_on_one_market_and_no_on_the_other(self):
        first = BinaryMarketSnapshot(
            market_id="candidate-wins-election",
            venue="polymarket",
            yes=OrderBook(asks=[Level(0.45, 100)], bids=[]),
            no=OrderBook(asks=[Level(0.57, 100)], bids=[]),
            fee_rate=0.0,
        )
        second = BinaryMarketSnapshot(
            market_id="candidate-elected-president",
            venue="polymarket",
            yes=OrderBook(asks=[Level(0.55, 100)], bids=[]),
            no=OrderBook(asks=[Level(0.48, 80)], bids=[]),
            fee_rate=0.0,
        )
        rule = EquivalenceRule("candidate-wins-election", "candidate-elected-president")

        opportunities = find_equivalent_arbs([first, second], [rule], min_net_edge=0.0)

        self.assertEqual(len(opportunities), 1)
        self.assertEqual(opportunities[0].kind, "equivalent")
        self.assertEqual(opportunities[0].quantity, 80)
        self.assertAlmostEqual(opportunities[0].cost_per_share, 0.93)
        self.assertAlmostEqual(opportunities[0].net_edge_per_share, 0.07)
        self.assertEqual(opportunities[0].legs[0].token, "YES")
        self.assertEqual(opportunities[0].legs[1].token, "NO")

    def test_collectively_exhaustive_arb_buys_both_yes_tokens(self):
        first = BinaryMarketSnapshot(
            market_id="team-a-or-team-b-final",
            venue="polymarket",
            yes=OrderBook(asks=[Level(0.40, 60)], bids=[]),
            no=OrderBook(asks=[Level(0.62, 100)], bids=[]),
            fee_rate=0.0,
        )
        second = BinaryMarketSnapshot(
            market_id="team-c-or-team-d-final",
            venue="polymarket",
            yes=OrderBook(asks=[Level(0.55, 80)], bids=[]),
            no=OrderBook(asks=[Level(0.47, 100)], bids=[]),
            fee_rate=0.0,
        )
        rule = CollectivelyExhaustiveRule("team-a-or-team-b-final", "team-c-or-team-d-final")

        opportunities = find_collectively_exhaustive_arbs([first, second], [rule], min_net_edge=0.0)

        self.assertEqual(len(opportunities), 1)
        self.assertEqual(opportunities[0].kind, "collectively_exhaustive")
        self.assertEqual(opportunities[0].quantity, 60)
        self.assertAlmostEqual(opportunities[0].cost_per_share, 0.95)
        self.assertAlmostEqual(opportunities[0].net_edge_per_share, 0.05)
        self.assertEqual(opportunities[0].legs[0].token, "YES")
        self.assertEqual(opportunities[0].legs[1].token, "YES")

    def test_exhaustive_group_arb_buys_all_yes_tokens(self):
        first = BinaryMarketSnapshot(
            market_id="a",
            venue="polymarket",
            yes=OrderBook(asks=[Level(0.20, 100)], bids=[]),
            no=OrderBook(asks=[], bids=[]),
            fee_rate=0.0,
        )
        second = BinaryMarketSnapshot(
            market_id="b",
            venue="polymarket",
            yes=OrderBook(asks=[Level(0.30, 70)], bids=[]),
            no=OrderBook(asks=[], bids=[]),
            fee_rate=0.0,
        )
        third = BinaryMarketSnapshot(
            market_id="c",
            venue="polymarket",
            yes=OrderBook(asks=[Level(0.40, 80)], bids=[]),
            no=OrderBook(asks=[], bids=[]),
            fee_rate=0.0,
        )
        rule = ExhaustiveGroupRule(["a", "b", "c"])

        opportunities = find_exhaustive_group_arbs([first, second, third], [rule], min_net_edge=0.0)

        self.assertEqual(len(opportunities), 1)
        opportunity = opportunities[0]
        self.assertEqual(opportunity.kind, "exhaustive_group_yes_basket")
        self.assertEqual(opportunity.quantity, 70)
        self.assertAlmostEqual(opportunity.cost_per_share, 0.90)
        self.assertAlmostEqual(opportunity.net_edge_per_share, 0.10)
        self.assertEqual([leg.token for leg in opportunity.legs], ["YES", "YES", "YES"])

    def test_exhaustive_group_arb_rejects_invalid_groups(self):
        snapshot = BinaryMarketSnapshot(
            market_id="a",
            venue="polymarket",
            yes=OrderBook(asks=[Level(0.20, 100)], bids=[]),
            no=OrderBook(asks=[], bids=[]),
            fee_rate=0.0,
        )

        self.assertEqual(find_exhaustive_group_arbs([snapshot], [ExhaustiveGroupRule([])]), [])
        self.assertEqual(find_exhaustive_group_arbs([snapshot], [ExhaustiveGroupRule(["a", "a"])]), [])

    def test_neg_risk_group_arbs_scan_yes_and_no_baskets(self):
        first = BinaryMarketSnapshot(
            market_id="a",
            venue="polymarket",
            yes=OrderBook(asks=[Level(0.20, 100)], bids=[]),
            no=OrderBook(asks=[Level(0.60, 100)], bids=[]),
            fee_rate=0.0,
        )
        second = BinaryMarketSnapshot(
            market_id="b",
            venue="polymarket",
            yes=OrderBook(asks=[Level(0.30, 70)], bids=[]),
            no=OrderBook(asks=[Level(0.65, 70)], bids=[]),
            fee_rate=0.0,
        )
        third = BinaryMarketSnapshot(
            market_id="c",
            venue="polymarket",
            yes=OrderBook(asks=[Level(0.40, 80)], bids=[]),
            no=OrderBook(asks=[Level(0.70, 80)], bids=[]),
            fee_rate=0.0,
        )
        rule = NegRiskGroupRule(["a", "b", "c"], neg_risk_market_id="group-1")

        opportunities = find_neg_risk_group_arbs([first, second, third], [rule], min_net_edge=0.0)

        self.assertEqual([opportunity.kind for opportunity in opportunities], ["neg_risk_group_yes_basket", "neg_risk_group_no_basket"])
        self.assertAlmostEqual(opportunities[0].cost_per_share, 0.90)
        self.assertAlmostEqual(opportunities[0].net_edge_per_share, 0.10)
        self.assertAlmostEqual(opportunities[1].cost_per_share, 1.95)
        self.assertAlmostEqual(opportunities[1].net_edge_per_share, 0.05)

    def test_complement_arb_checks_yes_bundle_and_no_bundle(self):
        first = BinaryMarketSnapshot(
            market_id="candidate-wins",
            venue="polymarket",
            yes=OrderBook(asks=[Level(0.45, 100)], bids=[]),
            no=OrderBook(asks=[Level(0.49, 100)], bids=[]),
            fee_rate=0.0,
        )
        second = BinaryMarketSnapshot(
            market_id="candidate-does-not-win",
            venue="polymarket",
            yes=OrderBook(asks=[Level(0.50, 80)], bids=[]),
            no=OrderBook(asks=[Level(0.48, 70)], bids=[]),
            fee_rate=0.0,
        )
        rule = ComplementRule("candidate-wins", "candidate-does-not-win")

        opportunities = find_complement_arbs([first, second], [rule], min_net_edge=0.0)

        self.assertEqual([opportunity.kind for opportunity in opportunities], ["complement_yes_bundle", "complement_no_bundle"])
        self.assertAlmostEqual(opportunities[0].cost_per_share, 0.95)
        self.assertAlmostEqual(opportunities[1].cost_per_share, 0.97)


if __name__ == "__main__":
    unittest.main()
