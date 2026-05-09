import unittest

from poly_strategy.models import BinaryMarketSnapshot, Leg, Opportunity, OrderBook
from poly_strategy.orderbook import Level
from poly_strategy.paper import select_paper_trades
from poly_strategy.scanner import find_yes_no_bundle_arbs


class PaperTests(unittest.TestCase):
    def test_select_paper_trades_reserves_overlapping_liquidity(self):
        shared_leg = Leg("polymarket", "a", "NO", "buy", 0.30, 100, "a-no")
        better = Opportunity(
            kind="mutually_exclusive",
            quantity=100,
            cost_per_share=0.80,
            net_edge_per_share=0.20,
            legs=[shared_leg, Leg("polymarket", "b", "NO", "buy", 0.50, 100, "b-no")],
            ts="2026-05-09T00:00:00Z",
        )
        worse = Opportunity(
            kind="mutually_exclusive",
            quantity=100,
            cost_per_share=0.95,
            net_edge_per_share=0.05,
            legs=[shared_leg, Leg("polymarket", "c", "NO", "buy", 0.65, 100, "c-no")],
            ts="2026-05-09T00:00:00Z",
        )

        selection = select_paper_trades([worse, better])

        self.assertEqual(len(selection.trades), 1)
        self.assertEqual(selection.trades[0].opportunity, better)
        self.assertEqual(len(selection.rejections), 1)
        self.assertEqual(selection.rejections[0].reason, "overlapping_liquidity_reserved")

    def test_select_paper_trades_caps_by_bankroll_and_per_trade_cap(self):
        opportunity = Opportunity(
            kind="yes_no_bundle",
            quantity=100,
            cost_per_share=0.80,
            net_edge_per_share=0.10,
            legs=[
                Leg("polymarket", "a", "YES", "buy", 0.40, 100, "a-yes"),
                Leg("polymarket", "a", "NO", "buy", 0.40, 100, "a-no"),
            ],
        )

        selection = select_paper_trades([opportunity], max_capital_per_trade=20, bankroll=12)

        self.assertEqual(len(selection.trades), 1)
        self.assertAlmostEqual(selection.trades[0].quantity, 15)
        self.assertAlmostEqual(selection.trades[0].capital_used, 12)
        self.assertAlmostEqual(selection.trades[0].edge, 1.5)

    def test_select_paper_trades_reprices_reduced_quantity_from_orderbook_levels(self):
        snapshot = BinaryMarketSnapshot(
            market_id="sample",
            venue="polymarket",
            yes=OrderBook(asks=[Level(0.40, 5), Level(0.70, 100)], bids=[]),
            no=OrderBook(asks=[Level(0.40, 5), Level(0.70, 100)], bids=[]),
            fee_rate=0.0,
        )
        opportunity = find_yes_no_bundle_arbs(snapshot, min_net_edge=0.0)[0]

        selection = select_paper_trades([opportunity], max_capital_per_trade=4)

        self.assertEqual(len(selection.trades), 1)
        trade = selection.trades[0]
        self.assertAlmostEqual(trade.quantity, 5)
        self.assertAlmostEqual(trade.capital_used, 4)
        self.assertAlmostEqual(trade.edge, 1)
        self.assertAlmostEqual(trade.opportunity.cost_per_share, 0.80)
        self.assertAlmostEqual(trade.opportunity.net_edge_per_share, 0.20)
        self.assertEqual([leg.worst_price for leg in trade.opportunity.legs], [0.40, 0.40])


if __name__ == "__main__":
    unittest.main()
