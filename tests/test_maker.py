import json
import tempfile
import unittest
from pathlib import Path

from poly_strategy.maker import (
    maker_adaptive_quote_report,
    maker_fill_sim_report,
    maker_hedge_scan_report,
    maker_hedge_sim_report,
    maker_hybrid_scan_report,
    maker_hybrid_sim_report,
    maker_hybrid_tape_sim_report,
    maker_scan_report,
)


class MakerTests(unittest.TestCase):
    def test_maker_scan_finds_neg_risk_no_basket_candidate(self):
        snapshots = [
            _snapshot("a", no_bid=0.60, no_ask=0.64),
            _snapshot("b", no_bid=0.63, no_ask=0.68),
            _snapshot("c", no_bid=0.66, no_ask=0.70),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshots.ndjson"
            gamma_path = Path(tmp) / "gamma.ndjson"
            snapshot_path.write_text("\n".join(json.dumps(row) for row in snapshots) + "\n")
            gamma_path.write_text(
                "\n".join(json.dumps(_gamma_row(market_id, index)) for index, market_id in enumerate(["a", "b", "c"]))
                + "\n"
            )

            report = maker_scan_report(
                snapshot_path,
                gamma_path=gamma_path,
                tick_size=0.01,
                min_edge=0.005,
                min_roi=0.001,
                max_capital=100,
            )

        self.assertEqual(report["candidate_count"], 1)
        row = report["top"][0]
        self.assertEqual(row["kind"], "maker_neg_risk_no_basket")
        self.assertAlmostEqual(row["passive_cost_per_share"], 1.99)
        self.assertAlmostEqual(row["maker_edge_per_share"], 0.01)
        self.assertGreater(row["expected_edge_at_cap"], 0.4)
        self.assertIn("partial_fill_directional_exposure", row["risk_flags"])

    def test_maker_scan_filters_large_baskets(self):
        snapshots = [_snapshot("a", 0.60, 0.64), _snapshot("b", 0.63, 0.68), _snapshot("c", 0.66, 0.70)]
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshots.ndjson"
            gamma_path = Path(tmp) / "gamma.ndjson"
            snapshot_path.write_text("\n".join(json.dumps(row) for row in snapshots) + "\n")
            gamma_path.write_text(
                "\n".join(json.dumps(_gamma_row(market_id, index)) for index, market_id in enumerate(["a", "b", "c"]))
                + "\n"
            )

            report = maker_scan_report(snapshot_path, gamma_path=gamma_path, tick_size=0.01, max_leg_count=2)

        self.assertEqual(report["candidate_count"], 0)

    def test_maker_scan_applies_quote_offset_ticks(self):
        snapshots = [
            _snapshot("a", no_bid=0.60, no_ask=0.64),
            _snapshot("b", no_bid=0.63, no_ask=0.68),
            _snapshot("c", no_bid=0.66, no_ask=0.70),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshots.ndjson"
            gamma_path = Path(tmp) / "gamma.ndjson"
            snapshot_path.write_text("\n".join(json.dumps(row) for row in snapshots) + "\n")
            gamma_path.write_text(
                "\n".join(json.dumps(_gamma_row(market_id, index)) for index, market_id in enumerate(["a", "b", "c"]))
                + "\n"
            )

            report = maker_scan_report(
                snapshot_path,
                gamma_path=gamma_path,
                tick_size=0.01,
                min_edge=0.005,
                max_capital=100,
                quote_offset_ticks=2,
            )

        row = report["top"][0]
        self.assertEqual(report["quote_offset_ticks"], 2)
        self.assertAlmostEqual(row["passive_cost_per_share"], 1.96)
        self.assertAlmostEqual(row["maker_edge_per_share"], 0.04)
        self.assertEqual(row["legs"][0]["quote_offset_ticks"], 2)

    def test_maker_fill_sim_counts_completed_candidates(self):
        rows = [
            _snapshot("a", 0.60, 0.64, ts="2026-05-10T00:00:00Z"),
            _snapshot("b", 0.63, 0.68, ts="2026-05-10T00:00:00Z"),
            _snapshot("c", 0.66, 0.70, ts="2026-05-10T00:00:00Z"),
            _snapshot("a", 0.60, 0.63, ts="2026-05-10T00:01:00Z"),
            _snapshot("b", 0.63, 0.67, ts="2026-05-10T00:01:00Z"),
            _snapshot("c", 0.66, 0.69, ts="2026-05-10T00:01:00Z"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshots.ndjson"
            gamma_path = Path(tmp) / "gamma.ndjson"
            snapshot_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            gamma_path.write_text(
                "\n".join(json.dumps(_gamma_row(market_id, index)) for index, market_id in enumerate(["a", "b", "c"]))
                + "\n"
            )

            report = maker_fill_sim_report(
                snapshot_path,
                gamma_path=gamma_path,
                tick_size=0.01,
                min_edge=0.005,
                min_roi=0.001,
                max_capital=100,
                horizon_seconds=120,
            )

        self.assertEqual(report["candidate_observation_count"], 1)
        self.assertEqual(report["completed_count"], 1)
        self.assertEqual(report["partial_count"], 0)
        self.assertEqual(report["top_completed"][0]["filled_leg_count"], 3)
        self.assertEqual(report["top_completed"][0]["completion_ts"], "2026-05-10T00:01:00Z")

    def test_maker_fill_sim_counts_partial_candidates(self):
        rows = [
            _snapshot("a", 0.60, 0.64, ts="2026-05-10T00:00:00Z"),
            _snapshot("b", 0.63, 0.68, ts="2026-05-10T00:00:00Z"),
            _snapshot("c", 0.66, 0.70, ts="2026-05-10T00:00:00Z"),
            _snapshot("a", 0.60, 0.63, ts="2026-05-10T00:01:00Z"),
            _snapshot("b", 0.63, 0.80, ts="2026-05-10T00:01:00Z"),
            _snapshot("c", 0.66, 0.80, ts="2026-05-10T00:01:00Z"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshots.ndjson"
            gamma_path = Path(tmp) / "gamma.ndjson"
            snapshot_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            gamma_path.write_text(
                "\n".join(json.dumps(_gamma_row(market_id, index)) for index, market_id in enumerate(["a", "b", "c"]))
                + "\n"
            )

            report = maker_fill_sim_report(
                snapshot_path,
                gamma_path=gamma_path,
                tick_size=0.01,
                min_edge=0.005,
                min_roi=0.001,
                max_capital=100,
                horizon_seconds=120,
            )

        self.assertEqual(report["completed_count"], 0)
        self.assertEqual(report["partial_count"], 1)
        self.assertEqual(report["top_partial"][0]["filled_leg_count"], 1)

    def test_maker_adaptive_quote_report_recommends_positive_ev_config(self):
        rows = [
            _snapshot("a", 0.60, 0.64, ts="2026-05-10T00:00:00Z"),
            _snapshot("b", 0.63, 0.68, ts="2026-05-10T00:00:00Z"),
            _snapshot("c", 0.66, 0.70, ts="2026-05-10T00:00:00Z"),
            _snapshot("a", 0.60, 0.63, ts="2026-05-10T00:01:00Z"),
            _snapshot("b", 0.63, 0.67, ts="2026-05-10T00:01:00Z"),
            _snapshot("c", 0.66, 0.69, ts="2026-05-10T00:01:00Z"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshots.ndjson"
            gamma_path = Path(tmp) / "gamma.ndjson"
            snapshot_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            gamma_path.write_text(
                "\n".join(json.dumps(_gamma_row(market_id, index)) for index, market_id in enumerate(["a", "b", "c"]))
                + "\n"
            )

            report = maker_adaptive_quote_report(
                snapshot_path,
                gamma_path=gamma_path,
                tick_size=0.01,
                min_edge=0.005,
                min_roi=0.001,
                max_capital=100,
                quote_offset_ticks_options=[1, 2],
                include_improve_bid=False,
                horizon_seconds=120,
                min_observations=1,
            )

        self.assertEqual(report["status"], "positive_ev_config_found")
        self.assertEqual(report["recommended_config"]["quote_mode"], "near_ask")
        self.assertEqual(report["recommended_config"]["quote_offset_ticks"], 1)
        self.assertGreater(report["recommended_config"]["risk_adjusted_total_ev_at_cap"], 0)

    def test_maker_hedge_scan_finds_single_maker_leg_candidate(self):
        snapshots = [
            _snapshot("a", no_bid=0.66, no_ask=0.68),
            _snapshot("b", no_bid=0.64, no_ask=0.66),
            _snapshot("c", no_bid=0.62, no_ask=0.64),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshots.ndjson"
            gamma_path = Path(tmp) / "gamma.ndjson"
            snapshot_path.write_text("\n".join(json.dumps(row) for row in snapshots) + "\n")
            gamma_path.write_text(
                "\n".join(json.dumps(_gamma_row(market_id, index)) for index, market_id in enumerate(["a", "b", "c"]))
                + "\n"
            )

            report = maker_hedge_scan_report(
                snapshot_path,
                gamma_path=gamma_path,
                tick_size=0.01,
                min_edge=0.005,
                min_roi=0.001,
                max_capital=100,
            )

        self.assertGreaterEqual(report["candidate_count"], 3)
        row = report["top"][0]
        self.assertEqual(row["kind"], "maker_hedge_neg_risk_no_basket")
        self.assertGreater(row["maker_edge_per_share"], 0.005)
        self.assertIn("requires_fast_hedge_after_fill", row["risk_flags"])

    def test_maker_hedge_scan_ignores_crossed_single_token_books(self):
        snapshots = [
            _snapshot("a", no_bid=0.66, no_ask=0.68),
            _snapshot("b", no_bid=0.70, no_ask=0.60),
            _snapshot("c", no_bid=0.62, no_ask=0.64),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshots.ndjson"
            gamma_path = Path(tmp) / "gamma.ndjson"
            snapshot_path.write_text("\n".join(json.dumps(row) for row in snapshots) + "\n")
            gamma_path.write_text(
                "\n".join(json.dumps(_gamma_row(market_id, index)) for index, market_id in enumerate(["a", "b", "c"]))
                + "\n"
            )

            report = maker_hedge_scan_report(snapshot_path, gamma_path=gamma_path, tick_size=0.01)

        self.assertEqual(report["candidate_count"], 0)

    def test_maker_hedge_sim_counts_completed_hedge(self):
        rows = [
            _snapshot("a", no_bid=0.66, no_ask=0.68, ts="2026-05-10T00:00:00Z"),
            _snapshot("b", no_bid=0.64, no_ask=0.66, ts="2026-05-10T00:00:00Z"),
            _snapshot("c", no_bid=0.62, no_ask=0.64, ts="2026-05-10T00:00:00Z"),
            _snapshot("a", no_bid=0.65, no_ask=0.67, ts="2026-05-10T00:01:00Z"),
            _snapshot("b", no_bid=0.64, no_ask=0.66, ts="2026-05-10T00:01:00Z"),
            _snapshot("c", no_bid=0.62, no_ask=0.64, ts="2026-05-10T00:01:00Z"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshots.ndjson"
            gamma_path = Path(tmp) / "gamma.ndjson"
            snapshot_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            gamma_path.write_text(
                "\n".join(json.dumps(_gamma_row(market_id, index)) for index, market_id in enumerate(["a", "b", "c"]))
                + "\n"
            )

            report = maker_hedge_sim_report(
                snapshot_path,
                gamma_path=gamma_path,
                tick_size=0.01,
                min_edge=0.005,
                min_roi=0.001,
                max_capital=100,
                horizon_seconds=120,
            )

        self.assertEqual(report["candidate_observation_count"], 3)
        self.assertEqual(report["completed_count"], 1)
        self.assertEqual(report["unsafe_fill_count"], 0)
        self.assertEqual(report["status"], "positive_ev_hedge_found")
        self.assertEqual(report["top_completed"][0]["maker_fill_ts"], "2026-05-10T00:01:00Z")

    def test_maker_hedge_sim_counts_unsafe_fill_when_hedge_turns_negative(self):
        rows = [
            _snapshot("a", no_bid=0.66, no_ask=0.68, ts="2026-05-10T00:00:00Z"),
            _snapshot("b", no_bid=0.64, no_ask=0.66, ts="2026-05-10T00:00:00Z"),
            _snapshot("c", no_bid=0.62, no_ask=0.64, ts="2026-05-10T00:00:00Z"),
            _snapshot("a", no_bid=0.65, no_ask=0.67, ts="2026-05-10T00:01:00Z"),
            _snapshot("b", no_bid=0.80, no_ask=0.82, ts="2026-05-10T00:01:00Z"),
            _snapshot("c", no_bid=0.80, no_ask=0.82, ts="2026-05-10T00:01:00Z"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshots.ndjson"
            gamma_path = Path(tmp) / "gamma.ndjson"
            snapshot_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            gamma_path.write_text(
                "\n".join(json.dumps(_gamma_row(market_id, index)) for index, market_id in enumerate(["a", "b", "c"]))
                + "\n"
            )

            report = maker_hedge_sim_report(
                snapshot_path,
                gamma_path=gamma_path,
                tick_size=0.01,
                min_edge=0.005,
                min_roi=0.001,
                max_capital=100,
                horizon_seconds=120,
            )

        self.assertEqual(report["candidate_observation_count"], 3)
        self.assertEqual(report["completed_count"], 0)
        self.assertEqual(report["unsafe_fill_count"], 1)
        self.assertEqual(report["top_unsafe"][0]["rejection_reason"], "hedge_edge_below_min_edge")

    def test_maker_hybrid_scan_finds_multi_maker_leg_candidate(self):
        snapshots = [
            _snapshot("a", no_bid=0.63, no_ask=0.67),
            _snapshot("b", no_bid=0.63, no_ask=0.67),
            _snapshot("c", no_bid=0.62, no_ask=0.66),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshots.ndjson"
            gamma_path = Path(tmp) / "gamma.ndjson"
            snapshot_path.write_text("\n".join(json.dumps(row) for row in snapshots) + "\n")
            gamma_path.write_text(
                "\n".join(json.dumps(_gamma_row(market_id, index)) for index, market_id in enumerate(["a", "b", "c"]))
                + "\n"
            )

            report = maker_hybrid_scan_report(
                snapshot_path,
                gamma_path=gamma_path,
                tick_size=0.01,
                min_edge=0.005,
                min_roi=0.001,
                max_capital=100,
                min_maker_legs=2,
                max_maker_legs=2,
            )

        self.assertEqual(report["candidate_count"], 3)
        row = report["top"][0]
        self.assertEqual(row["kind"], "maker_hybrid_neg_risk_no_basket")
        self.assertEqual(row["maker_leg_count"], 2)
        self.assertGreater(row["maker_edge_per_share"], 0.005)
        self.assertIn("partial_maker_fill_directional_exposure", row["risk_flags"])

    def test_maker_hybrid_sim_counts_completed_after_all_maker_legs_fill(self):
        rows = [
            _snapshot("a", no_bid=0.63, no_ask=0.67, ts="2026-05-10T00:00:00Z"),
            _snapshot("b", no_bid=0.63, no_ask=0.67, ts="2026-05-10T00:00:00Z"),
            _snapshot("c", no_bid=0.62, no_ask=0.66, ts="2026-05-10T00:00:00Z"),
            _snapshot("a", no_bid=0.63, no_ask=0.66, ts="2026-05-10T00:01:00Z"),
            _snapshot("b", no_bid=0.63, no_ask=0.66, ts="2026-05-10T00:01:00Z"),
            _snapshot("c", no_bid=0.62, no_ask=0.65, ts="2026-05-10T00:01:00Z"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshots.ndjson"
            gamma_path = Path(tmp) / "gamma.ndjson"
            snapshot_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            gamma_path.write_text(
                "\n".join(json.dumps(_gamma_row(market_id, index)) for index, market_id in enumerate(["a", "b", "c"]))
                + "\n"
            )

            report = maker_hybrid_sim_report(
                snapshot_path,
                gamma_path=gamma_path,
                tick_size=0.01,
                min_edge=0.005,
                min_roi=0.001,
                max_capital=100,
                min_maker_legs=2,
                max_maker_legs=2,
                horizon_seconds=120,
            )

        self.assertEqual(report["candidate_observation_count"], 3)
        self.assertEqual(report["completed_count"], 3)
        self.assertEqual(report["partial_maker_fill_count"], 0)
        self.assertEqual(report["status"], "positive_ev_hybrid_found")
        self.assertEqual(report["top_completed"][0]["maker_fill_ts"], "2026-05-10T00:01:00Z")

    def test_maker_hybrid_sim_counts_partial_maker_fill(self):
        rows = [
            _snapshot("a", no_bid=0.63, no_ask=0.67, ts="2026-05-10T00:00:00Z"),
            _snapshot("b", no_bid=0.63, no_ask=0.67, ts="2026-05-10T00:00:00Z"),
            _snapshot("c", no_bid=0.62, no_ask=0.66, ts="2026-05-10T00:00:00Z"),
            _snapshot("a", no_bid=0.63, no_ask=0.66, ts="2026-05-10T00:01:00Z"),
            _snapshot("b", no_bid=0.80, no_ask=0.82, ts="2026-05-10T00:01:00Z"),
            _snapshot("c", no_bid=0.62, no_ask=0.66, ts="2026-05-10T00:01:00Z"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshots.ndjson"
            gamma_path = Path(tmp) / "gamma.ndjson"
            snapshot_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            gamma_path.write_text(
                "\n".join(json.dumps(_gamma_row(market_id, index)) for index, market_id in enumerate(["a", "b", "c"]))
                + "\n"
            )

            report = maker_hybrid_sim_report(
                snapshot_path,
                gamma_path=gamma_path,
                tick_size=0.01,
                min_edge=0.005,
                min_roi=0.001,
                max_capital=100,
                min_maker_legs=2,
                max_maker_legs=2,
                horizon_seconds=120,
            )

        self.assertEqual(report["completed_count"], 0)
        self.assertEqual(report["partial_maker_fill_count"], 2)
        self.assertEqual(report["top_partial"][0]["filled_maker_leg_count"], 1)

    def test_maker_hybrid_touch_bid_fill_model_is_diagnostic(self):
        rows = [
            _snapshot("a", no_bid=0.63, no_ask=0.67, ts="2026-05-10T00:00:00Z"),
            _snapshot("b", no_bid=0.63, no_ask=0.67, ts="2026-05-10T00:00:00Z"),
            _snapshot("c", no_bid=0.62, no_ask=0.66, ts="2026-05-10T00:00:00Z"),
            _snapshot("a", no_bid=0.66, no_ask=0.67, ts="2026-05-10T00:01:00Z"),
            _snapshot("b", no_bid=0.63, no_ask=0.67, ts="2026-05-10T00:01:00Z"),
            _snapshot("c", no_bid=0.65, no_ask=0.66, ts="2026-05-10T00:01:00Z"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshots.ndjson"
            gamma_path = Path(tmp) / "gamma.ndjson"
            snapshot_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            gamma_path.write_text(
                "\n".join(json.dumps(_gamma_row(market_id, index)) for index, market_id in enumerate(["a", "b", "c"]))
                + "\n"
            )

            strict = maker_hybrid_sim_report(
                snapshot_path,
                gamma_path=gamma_path,
                tick_size=0.01,
                min_edge=0.005,
                min_roi=0.001,
                max_capital=100,
                min_maker_legs=2,
                max_maker_legs=2,
                max_maker_combinations=1,
                horizon_seconds=120,
            )
            touch = maker_hybrid_sim_report(
                snapshot_path,
                gamma_path=gamma_path,
                tick_size=0.01,
                min_edge=0.005,
                min_roi=0.001,
                max_capital=100,
                min_maker_legs=2,
                max_maker_legs=2,
                max_maker_combinations=1,
                fill_model="touch_bid",
                horizon_seconds=120,
            )

        self.assertEqual(strict["completed_count"], 0)
        self.assertEqual(touch["fill_model"], "touch_bid")
        self.assertEqual(touch["completed_count"], 1)
        self.assertTrue(touch["top_completed"][0]["maker_fills"][0]["diagnostic_only"])

    def test_maker_hybrid_tape_sim_requires_sell_trade_prints(self):
        rows = [
            _snapshot("a", no_bid=0.63, no_ask=0.67, ts="2026-05-10T00:00:00Z"),
            _snapshot("b", no_bid=0.63, no_ask=0.67, ts="2026-05-10T00:00:00Z"),
            _snapshot("c", no_bid=0.62, no_ask=0.66, ts="2026-05-10T00:00:00Z"),
            _snapshot("a", no_bid=0.63, no_ask=0.66, ts="2026-05-10T00:01:00Z"),
            _snapshot("b", no_bid=0.63, no_ask=0.66, ts="2026-05-10T00:01:00Z"),
            _snapshot("c", no_bid=0.62, no_ask=0.65, ts="2026-05-10T00:01:00Z"),
        ]
        trades = [
            _trade("a-no", "SELL", 0.66, 10, "2026-05-10T00:00:30Z"),
            _trade("c-no", "SELL", 0.65, 10, "2026-05-10T00:00:35Z"),
            _trade("b-no", "BUY", 0.66, 10, "2026-05-10T00:00:40Z"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshots.ndjson"
            gamma_path = Path(tmp) / "gamma.ndjson"
            trades_path = Path(tmp) / "trades.ndjson"
            snapshot_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            gamma_path.write_text(
                "\n".join(json.dumps(_gamma_row(market_id, index)) for index, market_id in enumerate(["a", "b", "c"]))
                + "\n"
            )
            trades_path.write_text("\n".join(json.dumps(row) for row in trades) + "\n")

            report = maker_hybrid_tape_sim_report(
                snapshot_path,
                trades_path,
                gamma_path=gamma_path,
                tick_size=0.01,
                min_edge=0.005,
                min_roi=0.001,
                max_capital=100,
                min_maker_legs=2,
                max_maker_legs=2,
                max_maker_combinations=1,
                horizon_seconds=120,
            )

        self.assertEqual(report["status"], "tape_positive_ev_candidate_found")
        self.assertEqual(report["trade_count"], 3)
        self.assertEqual(report["completed_count"], 1)
        self.assertEqual(report["unique_completed_count"], 1)
        self.assertEqual(len(report["top_unique_completed"]), 1)
        self.assertEqual(report["rejection_by_reason"][0]["reason"], "completed")
        self.assertEqual(report["maker_fill_progress_distribution"][0]["filled_maker_leg_count"], 2)
        completed = report["top_completed"][0]
        self.assertEqual(completed["fill_model"], "trade_tape_sell_through")
        self.assertEqual(completed["simulated_quantity"], 10)
        self.assertTrue(completed["diagnostic_only"])

    def test_maker_hybrid_tape_sim_reports_unfilled_maker_legs(self):
        rows = [
            _snapshot("a", no_bid=0.63, no_ask=0.67, ts="2026-05-10T00:00:00Z"),
            _snapshot("b", no_bid=0.63, no_ask=0.67, ts="2026-05-10T00:00:00Z"),
            _snapshot("c", no_bid=0.62, no_ask=0.66, ts="2026-05-10T00:00:00Z"),
            _snapshot("a", no_bid=0.63, no_ask=0.66, ts="2026-05-10T00:01:00Z"),
            _snapshot("b", no_bid=0.63, no_ask=0.66, ts="2026-05-10T00:01:00Z"),
            _snapshot("c", no_bid=0.62, no_ask=0.65, ts="2026-05-10T00:01:00Z"),
        ]
        trades = [
            _trade("a-no", "BUY", 0.66, 10, "2026-05-10T00:00:30Z"),
            _trade("b-no", "SELL", 0.67, 10, "2026-05-10T00:00:35Z"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshots.ndjson"
            gamma_path = Path(tmp) / "gamma.ndjson"
            trades_path = Path(tmp) / "trades.ndjson"
            snapshot_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            gamma_path.write_text(
                "\n".join(json.dumps(_gamma_row(market_id, index)) for index, market_id in enumerate(["a", "b", "c"]))
                + "\n"
            )
            trades_path.write_text("\n".join(json.dumps(row) for row in trades) + "\n")

            report = maker_hybrid_tape_sim_report(
                snapshot_path,
                trades_path,
                gamma_path=gamma_path,
                tick_size=0.01,
                min_edge=0.005,
                min_roi=0.001,
                max_capital=100,
                min_maker_legs=2,
                max_maker_legs=2,
                max_maker_combinations=1,
                horizon_seconds=120,
            )

        self.assertEqual(report["completed_count"], 0)
        self.assertGreater(report["no_fill_count"], 0)
        self.assertEqual(report["rejection_by_reason"][0]["reason"], "maker_not_filled")
        self.assertEqual(report["maker_fill_progress_distribution"][0]["filled_maker_leg_count"], 0)
        self.assertGreater(report["top_unfilled_maker_legs"][0]["unfilled_count"], 0)
        self.assertIn("min_distance_to_best_ask", report["top_unfilled_maker_legs"][0])


def _snapshot(market_id: str, no_bid: float, no_ask: float, ts: str = "2026-05-10T00:00:00Z"):
    yes_bid = max(0.0, 1.0 - no_ask - 0.02)
    yes_ask = min(1.0, 1.0 - no_bid + 0.02)
    return {
        "type": "binary_snapshot",
        "ts": ts,
        "venue": "polymarket",
        "market_id": market_id,
        "fee_rate": 0.05,
        "yes": {"token_id": f"{market_id}-yes", "asks": [[yes_ask, 100]], "bids": [[yes_bid, 100]]},
        "no": {"token_id": f"{market_id}-no", "asks": [[no_ask, 100]], "bids": [[no_bid, 100]]},
    }


def _trade(asset_id: str, side: str, price: float, size: float, ts: str):
    return {
        "type": "raw_polymarket_data_trade",
        "market_id": "m",
        "condition_id": "0xcondition",
        "asset_id": asset_id,
        "side": side,
        "price": price,
        "size": size,
        "trade_ts": ts,
        "raw": {
            "asset": asset_id,
            "side": side,
            "price": price,
            "size": size,
            "timestamp": ts,
        },
    }


def _gamma_row(market_id: str, threshold: int):
    return {
        "type": "raw_polymarket_gamma_market",
        "market_id": market_id,
        "raw": {
            "id": market_id,
            "question": f"Will {market_id} happen?",
            "description": "Same neg-risk group.",
            "closed": False,
            "enableOrderBook": True,
            "acceptingOrders": True,
            "outcomes": json.dumps(["Yes", "No"]),
            "clobTokenIds": json.dumps([f"{market_id}-yes", f"{market_id}-no"]),
            "negRisk": True,
            "negRiskMarketID": "group-1",
            "groupItemThreshold": str(threshold),
            "groupItemTitle": market_id,
        },
    }


if __name__ == "__main__":
    unittest.main()
