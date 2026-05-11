import json
import tempfile
import unittest
from pathlib import Path

from poly_strategy.exhaustive_groups import (
    potential_exhaustive_group_candidates,
    promote_exhaustive_groups,
    promotion_candidate_count,
    result_to_row,
)


class ExhaustiveGroupTests(unittest.TestCase):
    def test_potential_exhaustive_group_candidates_from_near_miss(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshots_path, rules_path, _ = _write_candidate_fixture(Path(tmp))

            candidates = potential_exhaustive_group_candidates(snapshots_path, rules_path, min_net_edge=0.0, top_n=5)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["market_ids"], ["a", "b", "c"])
        self.assertAlmostEqual(candidates[0]["net_edge_per_share"], 0.10)

    def test_promote_exhaustive_groups_adds_verified_group(self):
        client = FakeVerifier(
            {
                "verdict": "exhaustive_group",
                "confidence": 0.99,
                "trade_allowed": True,
                "risk_flags": [],
                "reason": "same event and full candidate set",
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            snapshots_path, rules_path, gamma_path = _write_candidate_fixture(Path(tmp))
            out_path = Path(tmp) / "rules-with-groups.json"

            result = promote_exhaustive_groups(
                gamma_path,
                rules_path,
                out_path,
                snapshots_path,
                client,
                min_net_edge=0.0,
                top_n=5,
                min_confidence=0.95,
            )
            row = json.loads(out_path.read_text())

        self.assertEqual(client.market_ids_seen, [["a", "b", "c"]])
        self.assertEqual(result.added_count, 1)
        self.assertEqual(result.rejected_count, 0)
        self.assertEqual(row["exhaustive_groups"][0]["market_ids"], ["a", "b", "c"])
        self.assertEqual(row["exhaustive_groups"][0]["source_relation"], "llm_exhaustive_group_verification")
        self.assertEqual(result_to_row(result)["type"], "exhaustive_group_promotion")

    def test_promote_exhaustive_groups_rejects_risky_verification(self):
        client = FakeVerifier(
            {
                "verdict": "uncertain",
                "confidence": 0.80,
                "trade_allowed": False,
                "risk_flags": ["incomplete_outcome_set"],
                "reason": "could be missing a candidate",
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            snapshots_path, rules_path, gamma_path = _write_candidate_fixture(Path(tmp))
            out_path = Path(tmp) / "rules-with-groups.json"

            result = promote_exhaustive_groups(
                gamma_path,
                rules_path,
                out_path,
                snapshots_path,
                client,
                min_net_edge=0.0,
                top_n=5,
                min_confidence=0.95,
            )
            row = json.loads(out_path.read_text())

        self.assertEqual(result.added_count, 0)
        self.assertEqual(result.rejected_count, 1)
        self.assertEqual(row["exhaustive_groups"], [])

    def test_promote_exhaustive_groups_rejects_incomplete_known_neg_risk_group(self):
        client = FakeVerifier(
            {
                "verdict": "exhaustive_group",
                "confidence": 0.99,
                "trade_allowed": True,
                "risk_flags": [],
                "reason": "same event and full candidate set",
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            snapshots_path, rules_path, gamma_path = _write_candidate_fixture(Path(tmp))
            with gamma_path.open("a") as handle:
                handle.write(json.dumps(_gamma_row("d")) + "\n")
            out_path = Path(tmp) / "rules-with-groups.json"

            result = promote_exhaustive_groups(
                gamma_path,
                rules_path,
                out_path,
                snapshots_path,
                client,
                min_net_edge=0.0,
                top_n=5,
                min_confidence=0.95,
            )

        self.assertEqual(client.market_ids_seen, [])
        self.assertEqual(result.added_count, 0)
        self.assertEqual(result.rejected_count, 1)
        self.assertEqual(result.rows[0]["status"], "incomplete_known_neg_risk_group")
        self.assertEqual(result.rows[0]["extra_known_market_ids"], ["d"])

    def test_promote_exhaustive_groups_uses_state_to_skip_recent_rejections(self):
        client = FakeVerifier(
            {
                "verdict": "uncertain",
                "confidence": 0.80,
                "trade_allowed": False,
                "risk_flags": ["incomplete_outcome_set"],
                "reason": "could be missing a candidate",
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            snapshots_path, rules_path, gamma_path = _write_candidate_fixture(Path(tmp))
            out_path = Path(tmp) / "rules-with-groups.json"
            state_path = Path(tmp) / "promotion-state.json"

            first = promote_exhaustive_groups(
                gamma_path,
                rules_path,
                out_path,
                snapshots_path,
                client,
                min_net_edge=0.0,
                top_n=5,
                min_confidence=0.95,
                state_path=state_path,
            )
            second = promote_exhaustive_groups(
                gamma_path,
                rules_path,
                out_path,
                snapshots_path,
                client,
                min_net_edge=0.0,
                top_n=5,
                min_confidence=0.95,
                state_path=state_path,
            )

        self.assertEqual(first.rejected_count, 1)
        self.assertEqual(second.rejected_count, 0)
        self.assertEqual(second.skipped_existing_count, 1)
        self.assertEqual(second.rows[0]["status"], "skipped_cached")
        self.assertEqual(client.market_ids_seen, [["a", "b", "c"]])

    def test_promote_exhaustive_groups_does_not_cache_added_as_active_rule(self):
        client = FakeVerifier(
            {
                "verdict": "exhaustive_group",
                "confidence": 0.99,
                "trade_allowed": True,
                "risk_flags": [],
                "reason": "same event and full candidate set",
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            snapshots_path, rules_path, gamma_path = _write_candidate_fixture(Path(tmp))
            out_path = Path(tmp) / "rules-with-groups.json"
            state_path = Path(tmp) / "promotion-state.json"

            first = promote_exhaustive_groups(
                gamma_path,
                rules_path,
                out_path,
                snapshots_path,
                client,
                min_net_edge=0.0,
                top_n=5,
                min_confidence=0.95,
                state_path=state_path,
            )
            second = promote_exhaustive_groups(
                gamma_path,
                rules_path,
                out_path,
                snapshots_path,
                client,
                min_net_edge=0.0,
                top_n=5,
                min_confidence=0.95,
                state_path=state_path,
            )

        self.assertEqual(first.added_count, 1)
        self.assertEqual(second.added_count, 1)
        self.assertEqual(client.market_ids_seen, [["a", "b", "c"], ["a", "b", "c"]])

    def test_promotion_candidate_count_counts_near_miss_groups(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshots_path, rules_path, _ = _write_candidate_fixture(Path(tmp))

            count = promotion_candidate_count(snapshots_path, rules_path, min_net_edge=0.0, top_n=5)

        self.assertEqual(count, 1)

    def test_promotion_candidate_count_can_use_gamma_neg_risk_groups(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshots_path = root / "snapshots.ndjson"
            rules_path = root / "rules.json"
            gamma_path = root / "gamma.ndjson"
            snapshots_path.write_text(
                "\n".join(json.dumps(row) for row in [_snapshot("a", 0.20), _snapshot("b", 0.30), _snapshot("c", 0.40)])
                + "\n"
            )
            rules_path.write_text("{}")
            gamma_path.write_text("\n".join(json.dumps(_gamma_row(market_id)) for market_id in ["a", "b", "c"]) + "\n")

            count = promotion_candidate_count(
                snapshots_path,
                rules_path,
                min_net_edge=0.0,
                top_n=5,
                gamma_path=gamma_path,
            )

        self.assertEqual(count, 1)

    def test_promotion_candidate_count_skips_ordered_range_group_missing_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshots_path = root / "snapshots.ndjson"
            rules_path = root / "rules.json"
            gamma_path = root / "gamma.ndjson"
            out_path = root / "rules-with-groups.json"
            snapshots_path.write_text(
                "\n".join(json.dumps(row) for row in [_snapshot("a", 0.01), _snapshot("b", 0.01), _snapshot("c", 0.01)])
                + "\n"
            )
            rules_path.write_text(
                json.dumps(
                    {
                        "mutually_exclusive": [
                            {"first": "a", "second": "b", "confidence": 0.99},
                            {"first": "a", "second": "c", "confidence": 0.99},
                            {"first": "b", "second": "c", "confidence": 0.99},
                        ]
                    }
                )
            )
            gamma_path.write_text(
                "\n".join(
                    json.dumps(row)
                    for row in [
                        _range_gamma_row("a", "65°F or below", "0"),
                        _range_gamma_row("b", "66-67°F", "1"),
                        _range_gamma_row("c", "68-69°F", "2"),
                    ]
                )
                + "\n"
            )
            client = FakeVerifier({"trade_allowed": True})

            count = promotion_candidate_count(
                snapshots_path,
                rules_path,
                min_net_edge=0.0,
                top_n=5,
                gamma_path=gamma_path,
            )
            result = promote_exhaustive_groups(
                gamma_path,
                rules_path,
                out_path,
                snapshots_path,
                client,
                min_net_edge=0.0,
                top_n=5,
            )

        self.assertEqual(count, 0)
        self.assertEqual(result.candidates_found, 0)
        self.assertEqual(client.market_ids_seen, [])


class FakeVerifier:
    def __init__(self, response):
        self.response = response
        self.market_ids_seen = []

    def verify_group(self, markets):
        self.market_ids_seen.append([market.market_id for market in markets])
        return dict(self.response)


def _write_candidate_fixture(root: Path):
    snapshots_path = root / "snapshots.ndjson"
    rules_path = root / "rules.json"
    gamma_path = root / "gamma.ndjson"

    snapshots_path.write_text("\n".join(json.dumps(row) for row in [_snapshot("a", 0.20), _snapshot("b", 0.30), _snapshot("c", 0.40)]) + "\n")
    rules_path.write_text(
        json.dumps(
            {
                "mutually_exclusive": [
                    {"first": "a", "second": "b", "confidence": 0.99},
                    {"first": "a", "second": "c", "confidence": 0.99},
                    {"first": "b", "second": "c", "confidence": 0.99},
                ]
            }
        )
    )
    gamma_path.write_text("\n".join(json.dumps(_gamma_row(market_id)) for market_id in ["a", "b", "c"]) + "\n")
    return snapshots_path, rules_path, gamma_path


def _snapshot(market_id: str, yes_price: float):
    return {
        "ts": "2026-05-09T00:00:00Z",
        "type": "binary_snapshot",
        "venue": "polymarket",
        "market_id": market_id,
        "fee_rate": 0.0,
        "yes": {"token_id": f"{market_id}-yes", "asks": [[yes_price, 100]], "bids": []},
        "no": {"token_id": f"{market_id}-no", "asks": [[1.0 - yes_price, 100]], "bids": []},
    }


def _gamma_row(market_id: str):
    return {
        "ts": "2026-05-09T00:00:00Z",
        "type": "raw_polymarket_gamma_market",
        "market_id": market_id,
        "raw": {
            "id": market_id,
            "question": f"Will candidate {market_id.upper()} win the final?",
            "description": "Resolves based on the final winner.",
            "outcomes": json.dumps(["Yes", "No"]),
            "clobTokenIds": json.dumps([f"{market_id}-yes", f"{market_id}-no"]),
            "endDate": "2026-06-01T00:00:00Z",
            "category": "sports",
            "slug": f"candidate-{market_id}-wins",
            "negRisk": True,
            "negRiskMarketID": "final-winner",
            "groupItemTitle": market_id.upper(),
            "groupItemThreshold": "",
        },
    }


def _range_gamma_row(market_id: str, group_item_title: str, group_item_threshold: str):
    row = _gamma_row(market_id)
    raw = row["raw"]
    raw["question"] = f"Will the highest temperature be {group_item_title}?"
    raw["description"] = "Resolves based on the daily high temperature."
    raw["groupItemTitle"] = group_item_title
    raw["groupItemThreshold"] = group_item_threshold
    raw["slug"] = f"temperature-{market_id}"
    return row


if __name__ == "__main__":
    unittest.main()
