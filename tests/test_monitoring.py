import unittest

from poly_strategy.backtest import RuleSet, snapshot_from_row
from poly_strategy.monitoring import IncrementalReplayState, stable_current_opportunities


class MonitoringTests(unittest.TestCase):
    def test_incremental_replay_tracks_current_runs_without_full_replay(self):
        state = IncrementalReplayState()
        rule_set = RuleSet()

        first = state.apply_snapshots(
            [_snapshot("2026-05-09T00:00:00Z", 0.45, 0.53)],
            rule_set,
            min_net_edge=0.0,
            max_capital_per_trade=9.8,
        )
        second = state.apply_snapshots(
            [_snapshot("2026-05-09T00:00:05Z", 0.45, 0.53)],
            rule_set,
            min_net_edge=0.0,
            max_capital_per_trade=9.8,
        )
        stable = stable_current_opportunities(second.current_opportunities, second.current_runs, min_run_observations=2)
        third = state.apply_snapshots(
            [_snapshot("2026-05-09T00:00:10Z", 0.51, 0.51)],
            rule_set,
            min_net_edge=0.0,
            max_capital_per_trade=9.8,
        )

        self.assertEqual(len(first.current_opportunities), 1)
        self.assertEqual(first.current_runs[0].observation_count, 1)
        self.assertEqual(len(stable), 1)
        self.assertEqual(second.current_runs[0].observation_count, 2)
        self.assertEqual(second.current_runs[0].duration_seconds, 5.0)
        self.assertEqual(len(third.current_opportunities), 0)
        self.assertEqual(len(state.closed_runs), 1)
        self.assertEqual(state.closed_runs[0].observation_count, 2)
        self.assertEqual(state.snapshot_count, 3)
        self.assertEqual(state.paper_trade_count, 2)
        self.assertAlmostEqual(state.paper_capital_used, 19.6)
        self.assertAlmostEqual(state.paper_edge, 0.4)


def _snapshot(ts: str, yes_price: float, no_price: float):
    return snapshot_from_row(
        {
            "ts": ts,
            "type": "binary_snapshot",
            "venue": "polymarket",
            "market_id": "sample",
            "fee_rate": 0.0,
            "yes": {"token_id": "yes-token", "asks": [[yes_price, 100]], "bids": []},
            "no": {"token_id": "no-token", "asks": [[no_price, 100]], "bids": []},
        }
    )


if __name__ == "__main__":
    unittest.main()
