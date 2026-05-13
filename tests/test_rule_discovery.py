import json
import tempfile
import unittest
from pathlib import Path

from poly_strategy.rule_discovery import (
    DiscoveredRuleSet,
    MarketText,
    RelationCandidate,
    cluster_markets_by_topic,
    deterministic_relation_candidates,
    discover_rules,
    filter_collectively_exhaustive,
    filter_complements,
    filter_equivalents,
    filter_implications,
    filter_mutual_exclusions,
    read_market_texts,
    write_discovered_rules,
)


class RuleDiscoveryTests(unittest.TestCase):
    def test_read_market_texts_extracts_gamma_rows(self):
        rows = [
            {
                "type": "raw_polymarket_gamma_market",
                "market_id": "a",
                "raw": {
                    "question": "Will A happen?",
                    "description": "A resolution text",
                    "outcomes": json.dumps(["Yes", "No"]),
                    "endDate": "2026-12-31T00:00:00Z",
                    "category": "Politics",
                    "slug": "will-a-happen",
                },
            },
            {
                "type": "binary_snapshot",
                "market_id": "ignored",
            },
            {
                "type": "raw_polymarket_gamma_market",
                "market_id": "b",
                "raw": {
                    "question": "Will B happen?",
                    "description": "",
                    "outcomes": ["Yes", "No"],
                    "endDate": "2026-12-30T00:00:00Z",
                },
            },
            {
                "type": "raw_polymarket_gamma_market",
                "market_id": "bad",
                "raw": {},
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gamma.ndjson"
            path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

            markets = read_market_texts(path)

        self.assertEqual([market.market_id for market in markets], ["a", "b"])
        self.assertEqual(markets[0].outcomes, ["Yes", "No"])
        self.assertEqual(markets[0].slug, "will-a-happen")
        self.assertEqual(markets[1].slug, "will-b-happen")

    def test_read_market_texts_dedupes_repeated_gamma_collections(self):
        rows = [
            {
                "type": "raw_polymarket_gamma_market",
                "market_id": "a",
                "raw": {"question": "Will old A happen?", "outcomes": ["Yes", "No"]},
            },
            {
                "type": "raw_polymarket_gamma_market",
                "market_id": "b",
                "raw": {"question": "Will B happen?", "outcomes": ["Yes", "No"]},
            },
            {
                "type": "raw_polymarket_gamma_market",
                "market_id": "a",
                "raw": {"question": "Will new A happen?", "outcomes": ["Yes", "No"]},
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gamma.ndjson"
            path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

            markets = read_market_texts(path)

        self.assertEqual([market.market_id for market in markets], ["a", "b"])
        self.assertEqual(markets[0].question, "Will new A happen?")

    def test_deterministic_relation_candidates_adds_neg_risk_mutual_exclusions(self):
        markets = [
            MarketText("a", "A?", "", ["Yes", "No"], "", "", "", neg_risk=True, neg_risk_market_id="group"),
            MarketText("b", "B?", "", ["Yes", "No"], "", "", "", neg_risk=True, neg_risk_market_id="group"),
            MarketText("c", "C?", "", ["Yes", "No"], "", "", "", neg_risk=True, neg_risk_market_id="other"),
        ]

        candidates = deterministic_relation_candidates(markets)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].relation_type, "mutually_exclusive")
        self.assertEqual((candidates[0].market_a_id, candidates[0].market_b_id), ("a", "b"))

    def test_deterministic_relation_candidates_adds_exact_duplicate_equivalent(self):
        markets = [
            MarketText("a", "Will Bitcoin hit 100k in 2026?", "", ["Yes", "No"], "2026-12-31", "Crypto", ""),
            MarketText("b", "Will Bitcoin hit 100k in 2026?", "", ["Yes", "No"], "2026-12-31", "Crypto", ""),
            MarketText("c", "Will Ethereum hit 10k in 2026?", "", ["Yes", "No"], "2026-12-31", "Crypto", ""),
        ]

        candidates = deterministic_relation_candidates(markets)
        equivalents = [candidate for candidate in candidates if candidate.relation_type == "equivalent"]

        self.assertEqual(len(equivalents), 1)
        self.assertEqual((equivalents[0].market_a_id, equivalents[0].market_b_id), ("a", "b"))
        self.assertTrue(equivalents[0].trade_allowed)

    def test_deterministic_duplicate_equivalent_blocks_fallback_wording(self):
        markets = [
            MarketText("a", "Will A happen?", "If neither occurs, this market will resolve to 50-50.", ["Yes", "No"], "", "", ""),
            MarketText("b", "Will A happen?", "", ["Yes", "No"], "", "", ""),
        ]

        candidates = deterministic_relation_candidates(markets)
        equivalent = next(candidate for candidate in candidates if candidate.relation_type == "equivalent")

        self.assertFalse(equivalent.trade_allowed)
        self.assertIn("conditional_or_fallback_resolution", equivalent.risk_flags)

    def test_cluster_markets_by_topic_groups_related_markets(self):
        markets = [
            MarketText("z", "Will the Fed cut rates in June?", "", ["Yes", "No"], "", "Macro", "fed-cut-june"),
            MarketText("a", "Will Bitcoin hit 100k in 2026?", "", ["Yes", "No"], "", "Crypto", "bitcoin-100k"),
            MarketText("b", "Will Bitcoin hit 120k in 2026?", "", ["Yes", "No"], "", "Crypto", "bitcoin-120k"),
        ]

        clustered = cluster_markets_by_topic(markets)

        btc_positions = [index for index, market in enumerate(clustered) if market.market_id in {"a", "b"}]
        self.assertEqual(btc_positions, list(range(min(btc_positions), max(btc_positions) + 1)))

    def test_secondary_verify_candidates_blocks_fallback_based_non_mutual_relations(self):
        from poly_strategy.rule_discovery import secondary_verify_candidates

        markets = {
            "a": MarketText("a", "Will A happen?", "If neither occurs, this market will resolve to 50-50.", ["Yes", "No"], "", "", ""),
            "b": MarketText("b", "Will B happen?", "", ["Yes", "No"], "", "", ""),
        }
        candidates = [
            RelationCandidate("implies", "a", "b", "a_implies_b", 0.99, True, [], "a implies b"),
            RelationCandidate("mutually_exclusive", "a", "b", "none", 0.99, True, [], "a excludes b"),
        ]

        verified = secondary_verify_candidates(candidates, markets)

        self.assertFalse(verified[0].trade_allowed)
        self.assertIn("conditional_or_fallback_resolution", verified[0].risk_flags)
        self.assertTrue(verified[1].trade_allowed)

    def test_filter_implications_is_conservative(self):
        candidates = [
            RelationCandidate("implies", "a", "b", "a_implies_b", 0.97, True, [], "a implies b"),
            RelationCandidate("implies", "c", "d", "b_implies_a", 0.98, True, [], "d implies c"),
            RelationCandidate("implies", "a", "c", "a_implies_b", 0.40, True, [], "too low"),
            RelationCandidate("implies", "a", "d", "a_implies_b", 0.99, True, ["ambiguous_wording"], "risky"),
            RelationCandidate("implies", "a", "missing", "a_implies_b", 0.99, True, [], "unknown"),
            RelationCandidate("implies", "a", "a", "a_implies_b", 0.99, True, [], "self"),
            RelationCandidate("equivalent", "a", "b", "bidirectional", 0.99, True, [], "not traded in mvp"),
            RelationCandidate("implies", "b", "c", "none", 0.99, True, [], "bad direction"),
            RelationCandidate("implies", "b", "d", "a_implies_b", 0.99, False, [], "blocked"),
        ]

        implications = filter_implications(candidates, {"a", "b", "c", "d"}, min_confidence=0.95)

        self.assertEqual([(rule.antecedent, rule.consequent) for rule in implications], [("a", "b"), ("d", "c")])

    def test_filter_implications_rejects_distinct_neg_risk_group_items(self):
        candidates = [
            RelationCandidate(
                "implies",
                "a",
                "b",
                "a_implies_b",
                0.99,
                True,
                [],
                "A winning implies B does not win",
            )
        ]
        markets = {
            "a": MarketText(
                "a",
                "Will A win?",
                "",
                ["Yes", "No"],
                "",
                "",
                "",
                neg_risk=True,
                neg_risk_market_id="group",
                group_item_title="A",
            ),
            "b": MarketText(
                "b",
                "Will B win?",
                "",
                ["Yes", "No"],
                "",
                "",
                "",
                neg_risk=True,
                neg_risk_market_id="group",
                group_item_title="B",
            ),
        }

        implications = filter_implications(candidates, {"a", "b"}, min_confidence=0.95, markets_by_id=markets)

        self.assertEqual(implications, [])

    def test_filter_mutual_exclusions_accepts_only_clean_candidates(self):
        candidates = [
            RelationCandidate("mutually_exclusive", "a", "b", "none", 0.99, True, [], "a and b cannot both win"),
            RelationCandidate("mutually_exclusive", "a", "c", "none", 0.70, True, [], "too low"),
            RelationCandidate("mutually_exclusive", "a", "d", "none", 0.99, True, ["ambiguous_wording"], "risky"),
            RelationCandidate("mutually_exclusive", "a", "missing", "none", 0.99, True, [], "unknown"),
            RelationCandidate("implies", "a", "b", "a_implies_b", 0.99, True, [], "different type"),
        ]

        exclusions = filter_mutual_exclusions(candidates, {"a", "b", "c", "d"}, min_confidence=0.95)

        self.assertEqual([(rule.first, rule.second) for rule in exclusions], [("a", "b")])

    def test_filter_other_pair_relations_accepts_only_clean_candidates(self):
        candidates = [
            RelationCandidate("equivalent", "b", "a", "bidirectional", 0.99, True, [], "same event"),
            RelationCandidate("collectively_exhaustive", "a", "c", "none", 0.99, True, [], "at least one yes"),
            RelationCandidate("complement", "a", "d", "bidirectional", 0.99, True, [], "exactly one yes"),
            RelationCandidate("equivalent", "a", "missing", "bidirectional", 0.99, True, [], "unknown"),
            RelationCandidate("complement", "a", "c", "bidirectional", 0.80, True, [], "low"),
        ]

        equivalents = filter_equivalents(candidates, {"a", "b", "c", "d"}, min_confidence=0.95)
        exhaustive = filter_collectively_exhaustive(candidates, {"a", "b", "c", "d"}, min_confidence=0.95)
        complements = filter_complements(candidates, {"a", "b", "c", "d"}, min_confidence=0.95)

        self.assertEqual([(rule.first, rule.second) for rule in equivalents], [("a", "b")])
        self.assertEqual([(rule.first, rule.second) for rule in exhaustive], [("a", "c")])
        self.assertEqual([(rule.first, rule.second) for rule in complements], [("a", "d")])

    def test_write_discovered_rules_keeps_backtest_compatible_implications(self):
        candidate = RelationCandidate("implies", "a", "b", "a_implies_b", 0.97, True, [], "a implies b")
        exclusion = RelationCandidate("mutually_exclusive", "a", "c", "none", 0.99, True, [], "exclusive")
        equivalent = RelationCandidate("equivalent", "a", "d", "bidirectional", 0.99, True, [], "same")
        exhaustive = RelationCandidate("collectively_exhaustive", "a", "e", "none", 0.99, True, [], "at least one")
        complement = RelationCandidate("complement", "a", "f", "bidirectional", 0.99, True, [], "exactly one")
        ruleset = DiscoveredRuleSet(
            generated_at="2026-05-08T00:00:00Z",
            min_confidence=0.95,
            candidates=[candidate, exclusion, equivalent, exhaustive, complement],
            implications=filter_implications([candidate], {"a", "b"}, min_confidence=0.95),
            processed_market_ids=["a", "b", "c", "d", "e", "f"],
            mutual_exclusions=filter_mutual_exclusions([exclusion], {"a", "c"}, min_confidence=0.95),
            equivalents=filter_equivalents([equivalent], {"a", "d"}, min_confidence=0.95),
            collectively_exhaustive=filter_collectively_exhaustive([exhaustive], {"a", "e"}, min_confidence=0.95),
            complements=filter_complements([complement], {"a", "f"}, min_confidence=0.95),
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rules.json"
            count = write_discovered_rules(path, ruleset)
            row = json.loads(path.read_text())

        self.assertEqual(count, 1)
        self.assertEqual(row["version"], 1)
        self.assertEqual(row["source"], "llm_discovery")
        self.assertEqual(row["implications"][0]["antecedent"], "a")
        self.assertEqual(row["implications"][0]["consequent"], "b")
        self.assertEqual(row["mutually_exclusive"][0]["first"], "a")
        self.assertEqual(row["mutually_exclusive"][0]["second"], "c")
        self.assertEqual(row["equivalent"][0]["second"], "d")
        self.assertEqual(row["collectively_exhaustive"][0]["second"], "e")
        self.assertEqual(row["complement"][0]["second"], "f")
        self.assertEqual(row["candidates"][0]["relation_type"], "implies")
        self.assertEqual(row["processed_market_ids"], ["a", "b", "c", "d", "e", "f"])

    def test_discover_rules_batches_markets_and_writes_output(self):
        class FakeClient:
            def __init__(self):
                self.calls = []

            def discover_relations(self, markets):
                ids = [market.market_id for market in markets]
                self.calls.append(ids)
                if ids[:2] == ["a", "b"]:
                    return [
                        RelationCandidate("implies", "a", "b", "a_implies_b", 0.99, True, [], "a implies b"),
                        RelationCandidate("mutually_exclusive", "a", "b", "none", 0.99, True, [], "exclusive"),
                        RelationCandidate("equivalent", "a", "b", "bidirectional", 0.99, True, [], "same"),
                        RelationCandidate("collectively_exhaustive", "a", "b", "none", 0.99, True, [], "at least one"),
                        RelationCandidate("complement", "a", "b", "bidirectional", 0.99, True, [], "exactly one"),
                    ]
                return []

        rows = [
            {
                "type": "raw_polymarket_gamma_market",
                "market_id": market_id,
                "raw": {"question": f"Will {market_id} happen?", "outcomes": ["Yes", "No"]},
            }
            for market_id in ["a", "b", "c"]
        ]

        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "gamma.ndjson"
            out = Path(tmp) / "rules.json"
            raw.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            client = FakeClient()

            result = discover_rules(
                raw,
                out,
                client,
                batch_size=2,
                min_confidence=0.95,
                generated_at="2026-05-08T00:00:00Z",
            )

            written = json.loads(out.read_text())

        self.assertEqual(client.calls, [["a", "b", "c"], ["c", "a", "b"]])
        self.assertEqual(result.markets_read, 3)
        self.assertEqual(result.candidates_found, 5)
        self.assertEqual(result.implications_written, 1)
        self.assertEqual(result.mutual_exclusions_written, 1)
        self.assertEqual(result.equivalents_written, 1)
        self.assertEqual(result.collectively_exhaustive_written, 1)
        self.assertEqual(result.complements_written, 1)
        self.assertEqual(written["implications"][0]["antecedent"], "a")
        self.assertEqual(written["mutually_exclusive"][0]["first"], "a")

    def test_discover_rules_with_cache_only_calls_client_for_new_markets(self):
        class FakeClient:
            def __init__(self):
                self.calls = []

            def discover_relations(self, markets):
                self.calls.append([market.market_id for market in markets])
                return [RelationCandidate("implies", "c", "d", "a_implies_b", 0.99, True, [], "c implies d")]

        rows = [
            {
                "type": "raw_polymarket_gamma_market",
                "market_id": market_id,
                "raw": {"question": f"Will {market_id} happen?", "outcomes": ["Yes", "No"]},
            }
            for market_id in ["a", "b", "c", "d"]
        ]
        cache = {
            "version": 1,
            "source": "llm_discovery",
            "candidates": [
                {
                    "relation_type": "implies",
                    "market_a_id": "a",
                    "market_b_id": "b",
                    "direction": "a_implies_b",
                    "confidence": 0.99,
                    "trade_allowed": True,
                    "risk_flags": [],
                    "reason": "a implies b",
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "gamma.ndjson"
            cache_path = Path(tmp) / "cache.json"
            out = Path(tmp) / "rules.json"
            raw.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            cache_path.write_text(json.dumps(cache))
            client = FakeClient()

            result = discover_rules(
                raw,
                out,
                client,
                batch_size=10,
                min_confidence=0.95,
                cache_path=cache_path,
                generated_at="2026-05-08T00:00:00Z",
            )
            written = json.loads(out.read_text())

        self.assertEqual(client.calls, [["c", "d", "a", "b"]])
        self.assertEqual(result.implications_written, 2)
        self.assertEqual({(row["antecedent"], row["consequent"]) for row in written["implications"]}, {("a", "b"), ("c", "d")})
        self.assertEqual(written["processed_market_ids"], ["a", "b", "c", "d"])

    def test_discover_rules_can_limit_new_markets_per_run(self):
        class FakeClient:
            def __init__(self):
                self.calls = []

            def discover_relations(self, markets):
                self.calls.append([market.market_id for market in markets])
                return []

        rows = [
            {
                "type": "raw_polymarket_gamma_market",
                "market_id": market_id,
                "raw": {"question": f"Will {market_id} happen?", "outcomes": ["Yes", "No"]},
            }
            for market_id in ["a", "b", "c", "d", "e"]
        ]

        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "gamma.ndjson"
            out = Path(tmp) / "rules.json"
            raw.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            client = FakeClient()

            discover_rules(
                raw,
                out,
                client,
                batch_size=2,
                min_confidence=0.95,
                context_market_limit=0,
                max_new_markets=3,
                generated_at="2026-05-08T00:00:00Z",
            )
            written = json.loads(out.read_text())

        self.assertEqual(client.calls, [["a", "b"], ["c"]])
        self.assertEqual(written["processed_market_ids"], ["a", "b", "c"])

    def test_discover_rules_writes_checkpoint_after_each_completed_batch(self):
        class FakeClient:
            def __init__(self):
                self.calls = 0

            def discover_relations(self, markets):
                self.calls += 1
                if self.calls == 1:
                    return [RelationCandidate("implies", "a", "b", "a_implies_b", 0.99, True, [], "a implies b")]
                raise RuntimeError("second batch failed")

        rows = [
            {
                "type": "raw_polymarket_gamma_market",
                "market_id": market_id,
                "raw": {"question": f"Will {market_id} happen?", "outcomes": ["Yes", "No"]},
            }
            for market_id in ["a", "b", "c", "d"]
        ]

        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "gamma.ndjson"
            out = Path(tmp) / "rules.json"
            raw.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            client = FakeClient()

            with self.assertRaises(RuntimeError):
                discover_rules(
                    raw,
                    out,
                    client,
                    batch_size=2,
                    min_confidence=0.95,
                    context_market_limit=0,
                    generated_at="2026-05-08T00:00:00Z",
                )
            written = json.loads(out.read_text())

        self.assertEqual(written["processed_market_ids"], ["a", "b"])
        self.assertEqual(written["implications"][0]["antecedent"], "a")
        self.assertEqual(written["implications"][0]["consequent"], "b")

    def test_discover_rules_can_continue_after_failed_client_batch(self):
        class FakeClient:
            def discover_relations(self, markets):
                ids = [market.market_id for market in markets]
                if ids == ["a", "b"]:
                    raise RuntimeError("bad response")
                return [RelationCandidate("implies", ids[0], ids[1], "a_implies_b", 0.99, True, [], "later batch")]

        rows = [
            {
                "type": "raw_polymarket_gamma_market",
                "market_id": market_id,
                "raw": {"question": f"Will {market_id} happen?", "outcomes": ["Yes", "No"]},
            }
            for market_id in ["a", "b", "c", "d"]
        ]

        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "gamma.ndjson"
            out = Path(tmp) / "rules.json"
            raw.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

            result = discover_rules(
                raw,
                out,
                FakeClient(),
                batch_size=2,
                min_confidence=0.95,
                context_market_limit=0,
                generated_at="2026-05-08T00:00:00Z",
                continue_on_client_error=True,
                client_workers=2,
            )
            written = json.loads(out.read_text())

        self.assertEqual(result.failed_batches, 2)
        self.assertEqual(written["processed_market_ids"], ["c", "d"])
        self.assertEqual(
            {tuple(row["market_ids"]) for row in written["discovery_errors"]},
            {("a",), ("b",)},
        )
        self.assertEqual(written["implications"][0]["antecedent"], "c")
        self.assertEqual(written["implications"][0]["consequent"], "d")

    def test_discover_rules_retries_failed_markets_with_smaller_batches(self):
        class FakeClient:
            def discover_relations(self, markets):
                ids = [market.market_id for market in markets]
                if ids == ["a", "b"]:
                    raise RuntimeError("batch too large")
                if ids == ["a"]:
                    return [RelationCandidate("implies", "a", "c", "a_implies_b", 0.99, True, [], "retry a")]
                return []

        rows = [
            {
                "type": "raw_polymarket_gamma_market",
                "market_id": market_id,
                "raw": {"question": f"Will {market_id} happen?", "outcomes": ["Yes", "No"]},
            }
            for market_id in ["a", "b", "c"]
        ]

        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "gamma.ndjson"
            out = Path(tmp) / "rules.json"
            raw.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

            result = discover_rules(
                raw,
                out,
                FakeClient(),
                batch_size=2,
                min_confidence=0.95,
                context_market_limit=0,
                generated_at="2026-05-08T00:00:00Z",
                continue_on_client_error=True,
                retry_failed_batches=1,
                retry_failed_batch_size=1,
            )
            written = json.loads(out.read_text())

        self.assertEqual(result.failed_batches, 0)
        self.assertEqual(written["processed_market_ids"], ["a", "b", "c"])
        self.assertEqual(written["discovery_errors"], [])
        self.assertEqual(written["implications"][0]["antecedent"], "a")
        self.assertEqual(written["implications"][0]["consequent"], "c")

    def test_discover_rules_keeps_only_latest_unresolved_error_per_market(self):
        class FakeClient:
            def discover_relations(self, markets):
                ids = [market.market_id for market in markets]
                if ids == ["a", "b"]:
                    raise RuntimeError("initial batch failed")
                if ids == ["a"]:
                    raise RuntimeError("retry failed")
                return []

        rows = [
            {
                "type": "raw_polymarket_gamma_market",
                "market_id": market_id,
                "raw": {"question": f"Will {market_id} happen?", "outcomes": ["Yes", "No"]},
            }
            for market_id in ["a", "b"]
        ]

        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "gamma.ndjson"
            out = Path(tmp) / "rules.json"
            raw.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

            result = discover_rules(
                raw,
                out,
                FakeClient(),
                batch_size=2,
                min_confidence=0.95,
                context_market_limit=0,
                generated_at="2026-05-08T00:00:00Z",
                continue_on_client_error=True,
                retry_failed_batches=1,
                retry_failed_batch_size=1,
            )
            written = json.loads(out.read_text())

        self.assertEqual(result.failed_batches, 1)
        self.assertEqual(written["processed_market_ids"], ["b"])
        self.assertEqual(len(written["discovery_errors"]), 1)
        self.assertEqual(written["discovery_errors"][0]["attempt"], 1)
        self.assertEqual(written["discovery_errors"][0]["market_ids"], ["a"])
        self.assertEqual(written["discovery_errors"][0]["error"], "retry failed")

    def test_discover_rules_uses_fallback_client_for_remaining_failures(self):
        class PrimaryClient:
            def discover_relations(self, markets):
                raise RuntimeError("primary failed")

        class FallbackClient:
            def discover_relations(self, markets):
                ids = [market.market_id for market in markets]
                return [RelationCandidate("implies", ids[0], "c", "a_implies_b", 0.99, True, [], "fallback")]

        rows = [
            {
                "type": "raw_polymarket_gamma_market",
                "market_id": market_id,
                "raw": {"question": f"Will {market_id} happen?", "outcomes": ["Yes", "No"]},
            }
            for market_id in ["a", "b", "c"]
        ]

        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "gamma.ndjson"
            out = Path(tmp) / "rules.json"
            raw.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

            result = discover_rules(
                raw,
                out,
                PrimaryClient(),
                batch_size=2,
                min_confidence=0.95,
                context_market_limit=0,
                generated_at="2026-05-08T00:00:00Z",
                continue_on_client_error=True,
                retry_failed_batches=0,
                fallback_client=FallbackClient(),
                fallback_retry_failed_batches=1,
                fallback_retry_failed_batch_size=1,
            )
            written = json.loads(out.read_text())

        self.assertEqual(result.failed_batches, 0)
        self.assertEqual(written["processed_market_ids"], ["a", "b", "c"])
        self.assertEqual(written["discovery_errors"], [])
        self.assertEqual(
            {(row["antecedent"], row["consequent"]) for row in written["implications"]},
            {("a", "c"), ("b", "c")},
        )

    def test_discover_rules_uses_semantic_client_for_empty_important_batch(self):
        class PrimaryClient:
            def __init__(self):
                self.calls = []

            def discover_relations(self, markets):
                self.calls.append([market.market_id for market in markets])
                return []

        class SemanticClient:
            def __init__(self):
                self.calls = []

            def discover_relations(self, markets):
                ids = [market.market_id for market in markets]
                self.calls.append(ids)
                return [RelationCandidate("implies", "a", "b", "a_implies_b", 0.99, True, [], "semantic")]

        rows = [
            {
                "type": "raw_polymarket_gamma_market",
                "market_id": "a",
                "raw": {
                    "question": "Will Bitcoin hit 100k in 2026?",
                    "outcomes": ["Yes", "No"],
                    "liquidityNum": 5000,
                    "volume24hr": 100,
                },
            },
            {
                "type": "raw_polymarket_gamma_market",
                "market_id": "b",
                "raw": {
                    "question": "Will Bitcoin hit 150k in 2026?",
                    "outcomes": ["Yes", "No"],
                    "liquidityNum": 5000,
                    "volume24hr": 100,
                },
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "gamma.ndjson"
            out = Path(tmp) / "rules.json"
            raw.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            primary = PrimaryClient()
            semantic = SemanticClient()

            result = discover_rules(
                raw,
                out,
                primary,
                batch_size=2,
                min_confidence=0.95,
                context_market_limit=0,
                generated_at="2026-05-08T00:00:00Z",
                semantic_client=semantic,
                semantic_retry_empty_batches=True,
                semantic_min_liquidity=1000,
            )
            written = json.loads(out.read_text())

        self.assertEqual(primary.calls, [["a", "b"]])
        self.assertEqual(semantic.calls, [["a", "b"]])
        self.assertEqual(result.implications_written, 1)
        self.assertEqual(written["implications"][0]["antecedent"], "a")

    def test_discover_rules_does_not_semantic_retry_empty_unimportant_batch(self):
        class PrimaryClient:
            def discover_relations(self, markets):
                return []

        class SemanticClient:
            def __init__(self):
                self.calls = []

            def discover_relations(self, markets):
                self.calls.append([market.market_id for market in markets])
                return [RelationCandidate("implies", "a", "b", "a_implies_b", 0.99, True, [], "semantic")]

        rows = [
            {
                "type": "raw_polymarket_gamma_market",
                "market_id": market_id,
                "raw": {"question": f"Will {market_id} happen?", "outcomes": ["Yes", "No"], "liquidityNum": 5},
            }
            for market_id in ["a", "b"]
        ]

        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "gamma.ndjson"
            out = Path(tmp) / "rules.json"
            raw.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            semantic = SemanticClient()

            result = discover_rules(
                raw,
                out,
                PrimaryClient(),
                batch_size=2,
                min_confidence=0.95,
                context_market_limit=0,
                generated_at="2026-05-08T00:00:00Z",
                semantic_client=semantic,
                semantic_retry_empty_batches=True,
                semantic_min_liquidity=1000,
            )

        self.assertEqual(semantic.calls, [])
        self.assertEqual(result.implications_written, 0)

    def test_discover_rules_keeps_important_empty_batch_pending_when_semantic_fails(self):
        class PrimaryClient:
            def discover_relations(self, markets):
                return []

        class SemanticClient:
            def discover_relations(self, markets):
                raise TimeoutError("semantic timeout")

        rows = [
            {
                "type": "raw_polymarket_gamma_market",
                "market_id": market_id,
                "raw": {
                    "question": f"Will Bitcoin hit {market_id} in 2026?",
                    "outcomes": ["Yes", "No"],
                    "liquidityNum": 5000,
                },
            }
            for market_id in ["a", "b"]
        ]

        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "gamma.ndjson"
            out = Path(tmp) / "rules.json"
            raw.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

            result = discover_rules(
                raw,
                out,
                PrimaryClient(),
                batch_size=2,
                min_confidence=0.95,
                context_market_limit=0,
                generated_at="2026-05-08T00:00:00Z",
                continue_on_client_error=True,
                semantic_client=SemanticClient(),
                semantic_retry_empty_batches=True,
                semantic_min_liquidity=1000,
            )
            written = json.loads(out.read_text())

        self.assertEqual(result.failed_batches, 2)
        self.assertEqual(written["processed_market_ids"], [])
        self.assertEqual({tuple(row["market_ids"]) for row in written["discovery_errors"]}, {("a",), ("b",)})
        self.assertEqual(written["discovery_errors"][0]["client"], "primary")
        self.assertIn("semantic timeout", written["discovery_errors"][0]["error"])

    def test_discover_rules_cache_tracks_markets_with_no_relations(self):
        rows = [
            {
                "type": "raw_polymarket_gamma_market",
                "market_id": market_id,
                "raw": {"question": f"Will {market_id} happen?", "outcomes": ["Yes", "No"]},
            }
            for market_id in ["a", "b", "c"]
        ]
        cache = {
            "version": 1,
            "source": "llm_discovery",
            "processed_market_ids": ["a", "b", "c"],
            "candidates": [
                {
                    "relation_type": "implies",
                    "market_a_id": "a",
                    "market_b_id": "b",
                    "direction": "a_implies_b",
                    "confidence": 0.99,
                    "trade_allowed": True,
                    "risk_flags": [],
                    "reason": "a implies b",
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "gamma.ndjson"
            cache_path = Path(tmp) / "cache.json"
            out = Path(tmp) / "rules.json"
            raw.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            cache_path.write_text(json.dumps(cache))

            result = discover_rules(
                raw,
                out,
                None,
                batch_size=10,
                min_confidence=0.95,
                cache_path=cache_path,
                generated_at="2026-05-08T00:00:00Z",
            )
            written = json.loads(out.read_text())

        self.assertEqual(result.implications_written, 1)
        self.assertEqual(written["processed_market_ids"], ["a", "b", "c"])

    def test_discover_rules_requires_client_for_uncached_markets(self):
        rows = [
            {
                "type": "raw_polymarket_gamma_market",
                "market_id": "a",
                "raw": {"question": "Will a happen?", "outcomes": ["Yes", "No"]},
            }
        ]

        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "gamma.ndjson"
            out = Path(tmp) / "rules.json"
            raw.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

            with self.assertRaises(RuntimeError):
                discover_rules(
                    raw,
                    out,
                    None,
                    batch_size=10,
                    min_confidence=0.95,
                    generated_at="2026-05-08T00:00:00Z",
                )

    def test_discover_rules_cache_can_disable_old_market_context(self):
        class FakeClient:
            def __init__(self):
                self.calls = []

            def discover_relations(self, markets):
                self.calls.append([market.market_id for market in markets])
                return []

        rows = [
            {
                "type": "raw_polymarket_gamma_market",
                "market_id": market_id,
                "raw": {"question": f"Will {market_id} happen?", "outcomes": ["Yes", "No"]},
            }
            for market_id in ["a", "b", "c"]
        ]
        cache = {
            "candidates": [
                {
                    "relation_type": "implies",
                    "market_a_id": "a",
                    "market_b_id": "b",
                    "direction": "a_implies_b",
                    "confidence": 0.99,
                    "trade_allowed": True,
                    "risk_flags": [],
                    "reason": "cached",
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "gamma.ndjson"
            cache_path = Path(tmp) / "cache.json"
            out = Path(tmp) / "rules.json"
            raw.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            cache_path.write_text(json.dumps(cache))
            client = FakeClient()

            discover_rules(
                raw,
                out,
                client,
                batch_size=10,
                min_confidence=0.95,
                cache_path=cache_path,
                context_market_limit=0,
                generated_at="2026-05-08T00:00:00Z",
            )

        self.assertEqual(client.calls, [["c"]])

    def test_discover_rules_writes_empty_file_for_empty_input(self):
        class FakeClient:
            def discover_relations(self, markets):
                raise AssertionError("client should not be called for empty input")

        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "empty.ndjson"
            out = Path(tmp) / "rules.json"
            raw.write_text("")

            result = discover_rules(
                raw,
                out,
                FakeClient(),
                batch_size=20,
                min_confidence=0.95,
                generated_at="2026-05-08T00:00:00Z",
            )
            written = json.loads(out.read_text())

        self.assertEqual(result.markets_read, 0)
        self.assertEqual(result.candidates_found, 0)
        self.assertEqual(result.implications_written, 0)
        self.assertEqual(written["implications"], [])


if __name__ == "__main__":
    unittest.main()
