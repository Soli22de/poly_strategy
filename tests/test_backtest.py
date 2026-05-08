import json
import tempfile
import unittest
from pathlib import Path

from poly_strategy.backtest import (
    load_collectively_exhaustive_rules,
    load_complement_rules,
    load_equivalence_rules,
    load_mutually_exclusive_rules,
    load_rules,
    replay_ndjson,
)


class BacktestTests(unittest.TestCase):
    def test_replay_ndjson_returns_opportunities_from_binary_snapshots(self):
        rows = [
            {
                "ts": "2026-05-08T00:00:00Z",
                "type": "binary_snapshot",
                "venue": "polymarket",
                "market_id": "sample",
                "fee_rate": 0.0,
                "yes": {"asks": [[0.45, 10]], "bids": []},
                "no": {"asks": [[0.53, 7]], "bids": []},
            }
        ]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshots.ndjson"
            path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

            result = replay_ndjson(path)

        self.assertEqual(result.snapshot_count, 1)
        self.assertEqual(result.opportunity_count, 1)
        self.assertAlmostEqual(result.total_edge, 0.14)

    def test_replay_ndjson_caps_quantity_by_capital_per_trade(self):
        rows = [
            {
                "ts": "2026-05-08T00:00:00Z",
                "type": "binary_snapshot",
                "venue": "polymarket",
                "market_id": "sample",
                "fee_rate": 0.0,
                "yes": {"asks": [[0.45, 100]], "bids": []},
                "no": {"asks": [[0.53, 100]], "bids": []},
            }
        ]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshots.ndjson"
            path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

            result = replay_ndjson(path, max_capital_per_trade=9.80)

        self.assertEqual(result.opportunity_count, 1)
        self.assertAlmostEqual(result.paper_trade_count, 1)
        self.assertAlmostEqual(result.paper_capital_used, 9.80)
        self.assertAlmostEqual(result.paper_edge, 0.20)

    def test_replay_ndjson_tracks_opportunity_runs_across_snapshots(self):
        rows = [
            {
                "ts": "2026-05-08T00:00:00Z",
                "type": "binary_snapshot",
                "venue": "polymarket",
                "market_id": "sample",
                "fee_rate": 0.0,
                "yes": {"asks": [[0.45, 10]], "bids": []},
                "no": {"asks": [[0.53, 10]], "bids": []},
            },
            {
                "ts": "2026-05-08T00:00:05Z",
                "type": "binary_snapshot",
                "venue": "polymarket",
                "market_id": "sample",
                "fee_rate": 0.0,
                "yes": {"asks": [[0.45, 10]], "bids": []},
                "no": {"asks": [[0.53, 10]], "bids": []},
            },
            {
                "ts": "2026-05-08T00:00:10Z",
                "type": "binary_snapshot",
                "venue": "polymarket",
                "market_id": "sample",
                "fee_rate": 0.0,
                "yes": {"asks": [[0.50, 10]], "bids": []},
                "no": {"asks": [[0.51, 10]], "bids": []},
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshots.ndjson"
            path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

            result = replay_ndjson(path)

        self.assertEqual(len(result.runs), 1)
        run = result.runs[0]
        self.assertEqual(run.market_id, "sample")
        self.assertEqual(run.observation_count, 2)
        self.assertAlmostEqual(run.duration_seconds, 5.0)

    def test_replay_ndjson_does_not_merge_distinct_opportunities_with_same_first_market(self):
        rows = [
            {
                "ts": "2026-05-08T00:00:00Z",
                "type": "binary_snapshot",
                "venue": "polymarket",
                "market_id": "a",
                "fee_rate": 0.0,
                "yes": {"asks": [[0.90, 100]], "bids": []},
                "no": {"asks": [[0.30, 100]], "bids": []},
            },
            {
                "ts": "2026-05-08T00:00:00Z",
                "type": "binary_snapshot",
                "venue": "polymarket",
                "market_id": "b",
                "fee_rate": 0.0,
                "yes": {"asks": [[0.90, 100]], "bids": []},
                "no": {"asks": [[0.30, 100]], "bids": []},
            },
            {
                "ts": "2026-05-08T00:00:00Z",
                "type": "binary_snapshot",
                "venue": "polymarket",
                "market_id": "c",
                "fee_rate": 0.0,
                "yes": {"asks": [[0.90, 100]], "bids": []},
                "no": {"asks": [[0.30, 100]], "bids": []},
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            snapshots_path = Path(tmp) / "snapshots.ndjson"
            rules_path = Path(tmp) / "rules.json"
            snapshots_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            rules_path.write_text(
                json.dumps(
                    {
                        "mutually_exclusive": [
                            {"first": "a", "second": "b"},
                            {"first": "a", "second": "c"},
                        ]
                    }
                )
            )

            result = replay_ndjson(snapshots_path, rules_path=rules_path)

        pair_runs = [run for run in result.runs if run.key.startswith("mutually_exclusive:")]
        self.assertEqual(len(pair_runs), 2)

    def test_load_rules_reads_implication_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rules.json"
            path.write_text(
                json.dumps(
                    {
                        "implications": [
                            {
                                "antecedent": "france-wins-world-cup",
                                "consequent": "france-reaches-final",
                            }
                        ]
                    }
                )
            )

            rules = load_rules(path)

        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].antecedent_market_id, "france-wins-world-cup")
        self.assertEqual(rules[0].consequent_market_id, "france-reaches-final")

    def test_load_rules_filters_extended_llm_rules_conservatively(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rules.json"
            path.write_text(
                json.dumps(
                    {
                        "implications": [
                            {
                                "antecedent": "a",
                                "consequent": "b",
                                "confidence": 0.99,
                                "trade_allowed": True,
                                "risk_flags": [],
                            },
                            {
                                "antecedent": "low",
                                "consequent": "b",
                                "confidence": 0.50,
                                "trade_allowed": True,
                                "risk_flags": [],
                            },
                            {
                                "antecedent": "risky",
                                "consequent": "b",
                                "confidence": 0.99,
                                "trade_allowed": True,
                                "risk_flags": ["ambiguous_wording"],
                            },
                            {
                                "antecedent": "blocked",
                                "consequent": "b",
                                "confidence": 0.99,
                                "trade_allowed": False,
                                "risk_flags": [],
                            },
                        ]
                    }
                )
            )

            rules = load_rules(path, min_confidence=0.95)

        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].antecedent_market_id, "a")
        self.assertEqual(rules[0].consequent_market_id, "b")

    def test_load_mutually_exclusive_rules_filters_extended_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rules.json"
            path.write_text(
                json.dumps(
                    {
                        "mutually_exclusive": [
                            {
                                "first": "a",
                                "second": "b",
                                "confidence": 0.99,
                                "trade_allowed": True,
                                "risk_flags": [],
                            },
                            {
                                "first": "low",
                                "second": "b",
                                "confidence": 0.70,
                                "trade_allowed": True,
                                "risk_flags": [],
                            },
                            {
                                "first": "risky",
                                "second": "b",
                                "confidence": 0.99,
                                "trade_allowed": True,
                                "risk_flags": ["ambiguous_wording"],
                            },
                        ]
                    }
                )
            )

            rules = load_mutually_exclusive_rules(path, min_confidence=0.95)

        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].first_market_id, "a")
        self.assertEqual(rules[0].second_market_id, "b")

    def test_load_pair_relation_rules_from_top_level_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rules.json"
            path.write_text(
                json.dumps(
                    {
                        "equivalent": [{"first": "a", "second": "b", "confidence": 0.99}],
                        "collectively_exhaustive": [{"first": "c", "second": "d", "confidence": 0.99}],
                        "complement": [{"first": "e", "second": "f", "confidence": 0.99}],
                    }
                )
            )

            equivalents = load_equivalence_rules(path)
            exhaustive = load_collectively_exhaustive_rules(path)
            complements = load_complement_rules(path)

        self.assertEqual((equivalents[0].first_market_id, equivalents[0].second_market_id), ("a", "b"))
        self.assertEqual((exhaustive[0].first_market_id, exhaustive[0].second_market_id), ("c", "d"))
        self.assertEqual((complements[0].first_market_id, complements[0].second_market_id), ("e", "f"))

    def test_replay_ndjson_scans_implication_rules_per_timestamp_batch(self):
        rows = [
            {
                "ts": "2026-05-08T00:00:00Z",
                "type": "binary_snapshot",
                "venue": "polymarket",
                "market_id": "france-wins-world-cup",
                "fee_rate": 0.0,
                "yes": {"asks": [[0.16, 100]], "bids": []},
                "no": {"asks": [[0.82, 100]], "bids": []},
            },
            {
                "ts": "2026-05-08T00:00:00Z",
                "type": "binary_snapshot",
                "venue": "polymarket",
                "market_id": "france-reaches-final",
                "fee_rate": 0.0,
                "yes": {"asks": [[0.15, 50]], "bids": []},
                "no": {"asks": [[0.87, 100]], "bids": []},
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            snapshots_path = Path(tmp) / "snapshots.ndjson"
            rules_path = Path(tmp) / "rules.json"
            snapshots_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            rules_path.write_text(
                json.dumps(
                    {
                        "implications": [
                            {
                                "antecedent": "france-wins-world-cup",
                                "consequent": "france-reaches-final",
                            }
                        ]
                    }
                )
            )

            result = replay_ndjson(snapshots_path, rules_path=rules_path)

        implication_opportunities = [opportunity for opportunity in result.opportunities if opportunity.kind == "implication"]
        self.assertEqual(len(implication_opportunities), 1)
        self.assertAlmostEqual(implication_opportunities[0].net_edge_per_share, 0.03)

    def test_replay_ndjson_scans_mutually_exclusive_rules_per_timestamp_batch(self):
        rows = [
            {
                "ts": "2026-05-08T00:00:00Z",
                "type": "binary_snapshot",
                "venue": "polymarket",
                "market_id": "canes-win-stanley-cup",
                "fee_rate": 0.0,
                "yes": {"asks": [[0.58, 100]], "bids": []},
                "no": {"asks": [[0.42, 50]], "bids": []},
            },
            {
                "ts": "2026-05-08T00:00:00Z",
                "type": "binary_snapshot",
                "venue": "polymarket",
                "market_id": "avs-win-stanley-cup",
                "fee_rate": 0.0,
                "yes": {"asks": [[0.50, 100]], "bids": []},
                "no": {"asks": [[0.50, 80]], "bids": []},
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            snapshots_path = Path(tmp) / "snapshots.ndjson"
            rules_path = Path(tmp) / "rules.json"
            snapshots_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            rules_path.write_text(
                json.dumps(
                    {
                        "mutually_exclusive": [
                            {
                                "first": "canes-win-stanley-cup",
                                "second": "avs-win-stanley-cup",
                            }
                        ]
                    }
                )
            )

            result = replay_ndjson(snapshots_path, rules_path=rules_path)

        exclusion_opportunities = [
            opportunity for opportunity in result.opportunities if opportunity.kind == "mutually_exclusive"
        ]
        self.assertEqual(len(exclusion_opportunities), 1)
        self.assertAlmostEqual(exclusion_opportunities[0].net_edge_per_share, 0.08)

    def test_replay_ndjson_scans_mutual_exclusion_basket_rules_per_timestamp_batch(self):
        rows = [
            {
                "ts": "2026-05-08T00:00:00Z",
                "type": "binary_snapshot",
                "venue": "polymarket",
                "market_id": "a",
                "fee_rate": 0.0,
                "yes": {"asks": [[0.60, 100]], "bids": []},
                "no": {"asks": [[0.30, 50]], "bids": []},
            },
            {
                "ts": "2026-05-08T00:00:00Z",
                "type": "binary_snapshot",
                "venue": "polymarket",
                "market_id": "b",
                "fee_rate": 0.0,
                "yes": {"asks": [[0.61, 100]], "bids": []},
                "no": {"asks": [[0.31, 50]], "bids": []},
            },
            {
                "ts": "2026-05-08T00:00:00Z",
                "type": "binary_snapshot",
                "venue": "polymarket",
                "market_id": "c",
                "fee_rate": 0.0,
                "yes": {"asks": [[0.62, 100]], "bids": []},
                "no": {"asks": [[0.32, 50]], "bids": []},
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            snapshots_path = Path(tmp) / "snapshots.ndjson"
            rules_path = Path(tmp) / "rules.json"
            snapshots_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            rules_path.write_text(
                json.dumps(
                    {
                        "mutually_exclusive": [
                            {"first": "a", "second": "b"},
                            {"first": "a", "second": "c"},
                            {"first": "b", "second": "c"},
                        ]
                    }
                )
            )

            result = replay_ndjson(snapshots_path, rules_path=rules_path)

        basket_opportunities = [opportunity for opportunity in result.opportunities if opportunity.kind == "mutual_exclusion_basket"]
        self.assertEqual(len(basket_opportunities), 1)
        self.assertAlmostEqual(basket_opportunities[0].net_edge_per_share, 1.07)

    def test_replay_ndjson_scans_all_pair_relation_rules_per_timestamp_batch(self):
        rows = [
            {
                "ts": "2026-05-08T00:00:00Z",
                "type": "binary_snapshot",
                "venue": "polymarket",
                "market_id": "a",
                "fee_rate": 0.0,
                "yes": {"asks": [[0.45, 100]], "bids": []},
                "no": {"asks": [[0.49, 100]], "bids": []},
            },
            {
                "ts": "2026-05-08T00:00:00Z",
                "type": "binary_snapshot",
                "venue": "polymarket",
                "market_id": "b",
                "fee_rate": 0.0,
                "yes": {"asks": [[0.50, 100]], "bids": []},
                "no": {"asks": [[0.48, 80]], "bids": []},
            },
            {
                "ts": "2026-05-08T00:00:00Z",
                "type": "binary_snapshot",
                "venue": "polymarket",
                "market_id": "c",
                "fee_rate": 0.0,
                "yes": {"asks": [[0.40, 100]], "bids": []},
                "no": {"asks": [[0.65, 100]], "bids": []},
            },
            {
                "ts": "2026-05-08T00:00:00Z",
                "type": "binary_snapshot",
                "venue": "polymarket",
                "market_id": "d",
                "fee_rate": 0.0,
                "yes": {"asks": [[0.55, 100]], "bids": []},
                "no": {"asks": [[0.47, 100]], "bids": []},
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            snapshots_path = Path(tmp) / "snapshots.ndjson"
            rules_path = Path(tmp) / "rules.json"
            snapshots_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            rules_path.write_text(
                json.dumps(
                    {
                        "equivalent": [{"first": "a", "second": "b"}],
                        "collectively_exhaustive": [{"first": "c", "second": "d"}],
                        "complement": [{"first": "a", "second": "b"}],
                    }
                )
            )

            result = replay_ndjson(snapshots_path, rules_path=rules_path)

        kinds = sorted(opportunity.kind for opportunity in result.opportunities)
        self.assertIn("equivalent", kinds)
        self.assertIn("collectively_exhaustive", kinds)
        self.assertIn("complement_yes_bundle", kinds)
        self.assertIn("complement_no_bundle", kinds)


if __name__ == "__main__":
    unittest.main()
