import json
import tempfile
import unittest
from pathlib import Path

from poly_strategy.near_miss import near_miss_report


class NearMissTests(unittest.TestCase):
    def test_near_miss_report_shows_fee_blocked_candidates(self):
        rows = [
            {
                "ts": "2026-05-09T00:00:00Z",
                "type": "binary_snapshot",
                "venue": "polymarket",
                "market_id": "sample",
                "fee_rate": 0.03,
                "yes": {"token_id": "yes-token", "asks": [[0.003, 100]], "bids": []},
                "no": {"token_id": "no-token", "asks": [[0.997, 100]], "bids": []},
            }
        ]

        with tempfile.TemporaryDirectory() as tmp:
            snapshots = Path(tmp) / "snapshots.ndjson"
            rules = Path(tmp) / "rules.json"
            snapshots.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            rules.write_text("{}")

            report = near_miss_report(snapshots, rules, top_n=3, min_net_edge=-0.0001)

        self.assertEqual(report["candidate_count"], 1)
        self.assertEqual(report["top"][0]["kind"], "yes_no_bundle")
        self.assertAlmostEqual(report["top"][0]["gross_edge_per_share"], 0.0)
        self.assertLess(report["top"][0]["net_edge_per_share"], 0.0)
        self.assertEqual(report["by_kind"][0]["kind"], "yes_no_bundle")

    def test_near_miss_report_includes_diagnostic_exhaustive_cliques(self):
        snapshots = [
            _row("a", 0.30, 0.72),
            _row("b", 0.31, 0.71),
            _row("c", 0.32, 0.70),
        ]
        rules_row = {
            "mutually_exclusive": [
                {"first": "a", "second": "b", "confidence": 0.99},
                {"first": "a", "second": "c", "confidence": 0.99},
                {"first": "b", "second": "c", "confidence": 0.99},
            ]
        }

        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshots.ndjson"
            rule_path = Path(tmp) / "rules.json"
            snapshot_path.write_text("\n".join(json.dumps(row) for row in snapshots) + "\n")
            rule_path.write_text(json.dumps(rules_row))

            report = near_miss_report(snapshot_path, rule_path, top_n=10)

        kinds = {row["kind"] for row in report["top"]}
        self.assertIn("mutual_exclusion_basket", kinds)
        self.assertIn("potential_exhaustive_yes_basket", kinds)
        diagnostic = [row for row in report["top"] if row["kind"] == "potential_exhaustive_yes_basket"][0]
        self.assertTrue(diagnostic["diagnostic_only"])
        self.assertIn("complete collectively exhaustive", diagnostic["risk_note"])

    def test_near_miss_report_includes_verified_exhaustive_groups(self):
        snapshots = [
            _row("a", 0.20, 0.82),
            _row("b", 0.30, 0.72),
            _row("c", 0.40, 0.62),
        ]
        rules_row = {"exhaustive_groups": [{"market_ids": ["a", "b", "c"], "confidence": 0.99}]}

        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshots.ndjson"
            rule_path = Path(tmp) / "rules.json"
            snapshot_path.write_text("\n".join(json.dumps(row) for row in snapshots) + "\n")
            rule_path.write_text(json.dumps(rules_row))

            report = near_miss_report(snapshot_path, rule_path, top_n=10)

        rows = [row for row in report["top"] if row["kind"] == "exhaustive_group_yes_basket"]
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["net_edge_per_share"], 0.10)
        self.assertNotIn("diagnostic_only", rows[0])

    def test_near_miss_report_rejects_incomplete_known_neg_risk_groups(self):
        snapshots = [
            _row("a", 0.20, 0.82),
            _row("b", 0.30, 0.72),
            _row("c", 0.40, 0.62),
        ]
        rules_row = {
            "mutually_exclusive": [
                {"first": "a", "second": "b", "confidence": 0.99},
                {"first": "a", "second": "c", "confidence": 0.99},
                {"first": "b", "second": "c", "confidence": 0.99},
            ]
        }

        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshots.ndjson"
            rule_path = Path(tmp) / "rules.json"
            gamma_path = Path(tmp) / "gamma.ndjson"
            snapshot_path.write_text("\n".join(json.dumps(row) for row in snapshots) + "\n")
            rule_path.write_text(json.dumps(rules_row))
            gamma_path.write_text(
                "\n".join(json.dumps(_gamma_row(market_id, index)) for index, market_id in enumerate(["a", "b", "c", "d"]))
                + "\n"
            )

            report = near_miss_report(snapshot_path, rule_path, gamma_path=gamma_path, top_n=10)

        candidate = [row for row in report["top"] if row["kind"] == "potential_exhaustive_yes_basket"][0]
        self.assertEqual(candidate["trade_status"], "rejected")
        self.assertEqual(candidate["neg_risk_status"], "incomplete_known_neg_risk_group")
        self.assertEqual(candidate["extra_known_market_ids"], ["d"])
        diagnostic = report["neg_risk_expanded_groups"][0]
        self.assertEqual(diagnostic["status"], "incomplete_known_neg_risk_group")
        self.assertEqual(diagnostic["missing_snapshot_market_ids"], ["d"])

    def test_near_miss_report_computes_full_known_neg_risk_group_when_snapshots_exist(self):
        snapshots = [
            _row("a", 0.20, 0.82),
            _row("b", 0.30, 0.72),
            _row("c", 0.40, 0.62),
            _row("d", 0.30, 0.72),
        ]
        rules_row = {
            "mutually_exclusive": [
                {"first": "a", "second": "b", "confidence": 0.99},
                {"first": "a", "second": "c", "confidence": 0.99},
                {"first": "b", "second": "c", "confidence": 0.99},
            ]
        }

        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshots.ndjson"
            rule_path = Path(tmp) / "rules.json"
            gamma_path = Path(tmp) / "gamma.ndjson"
            snapshot_path.write_text("\n".join(json.dumps(row) for row in snapshots) + "\n")
            rule_path.write_text(json.dumps(rules_row))
            gamma_path.write_text(
                "\n".join(json.dumps(_gamma_row(market_id, index)) for index, market_id in enumerate(["a", "b", "c", "d"]))
                + "\n"
            )

            report = near_miss_report(snapshot_path, rule_path, gamma_path=gamma_path, top_n=10)

        expanded = report["neg_risk_expanded_groups"][0]["expanded_candidate"]
        self.assertEqual(expanded["kind"], "known_neg_risk_full_yes_basket")
        self.assertTrue(expanded["diagnostic_only"])
        self.assertAlmostEqual(expanded["net_edge_per_share"], -0.20)
        self.assertEqual([leg["market_id"] for leg in expanded["legs"]], ["a", "b", "c", "d"])

    def test_near_miss_report_requires_all_markets_to_share_neg_risk_group(self):
        snapshots = [_row("a", 0.20, 0.82), _row("b", 0.30, 0.72), _row("c", 0.40, 0.62)]
        rules_row = {
            "mutually_exclusive": [
                {"first": "a", "second": "b", "confidence": 0.99},
                {"first": "a", "second": "c", "confidence": 0.99},
                {"first": "b", "second": "c", "confidence": 0.99},
            ]
        }

        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "snapshots.ndjson"
            rule_path = Path(tmp) / "rules.json"
            gamma_path = Path(tmp) / "gamma.ndjson"
            snapshot_path.write_text("\n".join(json.dumps(row) for row in snapshots) + "\n")
            rule_path.write_text(json.dumps(rules_row))
            gamma_path.write_text(
                "\n".join(
                    [
                        json.dumps(_gamma_row("a", 0)),
                        json.dumps(_gamma_row("b", 1)),
                        json.dumps(_gamma_row("c", 2, group_id="")),
                    ]
                )
                + "\n"
            )

            report = near_miss_report(snapshot_path, rule_path, gamma_path=gamma_path, top_n=10)

        diagnostic = report["neg_risk_expanded_groups"][0]
        self.assertEqual(diagnostic["status"], "not_single_neg_risk_group")
        self.assertEqual(diagnostic["trade_status"], "needs_verification")


def _row(market_id: str, yes_price: float, no_price: float):
    return {
        "ts": "2026-05-09T00:00:00Z",
        "type": "binary_snapshot",
        "venue": "polymarket",
        "market_id": market_id,
        "fee_rate": 0.0,
        "yes": {"token_id": f"{market_id}-yes", "asks": [[yes_price, 100]], "bids": []},
        "no": {"token_id": f"{market_id}-no", "asks": [[no_price, 100]], "bids": []},
    }


def _gamma_row(market_id: str, threshold: int, group_id: str = "group-1"):
    return {
        "ts": "2026-05-09T00:00:00Z",
        "type": "raw_polymarket_gamma_market",
        "market_id": market_id,
        "raw": {
            "id": market_id,
            "question": f"Will {market_id.upper()} win?",
            "description": "Same event.",
            "outcomes": json.dumps(["Yes", "No"]),
            "endDate": "2026-06-01T00:00:00Z",
            "slug": f"{market_id}-wins",
            "negRisk": True,
            "negRiskMarketID": group_id,
            "groupItemTitle": market_id.upper(),
            "groupItemThreshold": str(threshold),
        },
    }


if __name__ == "__main__":
    unittest.main()
