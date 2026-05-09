import json
import os
import unittest
from unittest.mock import patch

from poly_strategy.openai_rules import (
    OpenAIConfigError,
    OpenAIExhaustiveGroupVerifierClient,
    OpenAIResponseError,
    OpenAIRuleDiscoveryClient,
)
from poly_strategy.rule_discovery import MarketText


class OpenAIRulesTests(unittest.TestCase):
    def test_build_payload_uses_structured_outputs_and_compact_market_text(self):
        client = OpenAIRuleDiscoveryClient(model="test-model", api_key="test-key")
        market = MarketText(
            market_id="a",
            question="Will A happen?",
            description="Resolution text",
            outcomes=["Yes", "No"],
            end_date="2026-12-31T00:00:00Z",
            category="Politics",
            slug="will-a-happen",
        )

        payload = client.build_payload([market])
        payload_text = json.dumps(payload)

        self.assertEqual(payload["model"], "test-model")
        self.assertEqual(payload["max_output_tokens"], 4000)
        self.assertEqual(payload["reasoning"]["effort"], "medium")
        self.assertEqual(payload["text"]["format"]["type"], "json_schema")
        self.assertTrue(payload["text"]["format"]["strict"])
        self.assertIn("Will A happen?", payload_text)
        self.assertNotIn("asks", payload_text)
        self.assertNotIn("bids", payload_text)

    def test_discover_relations_parses_structured_response(self):
        response = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "relations": [
                                        {
                                            "relation_type": "implies",
                                            "market_a_id": "a",
                                            "market_b_id": "b",
                                            "direction": "a_implies_b",
                                            "confidence": 0.98,
                                            "trade_allowed": True,
                                            "risk_flags": [],
                                            "reason": "a implies b",
                                        }
                                    ]
                                }
                            ),
                        }
                    ],
                }
            ]
        }

        calls = []

        def transport(payload, timeout):
            calls.append((payload, timeout))
            return response

        client = OpenAIRuleDiscoveryClient(model="test-model", api_key="test-key", timeout=12, transport=transport)
        market = MarketText("a", "Will A happen?", "", ["Yes", "No"], "", "", "will-a-happen")

        candidates = client.discover_relations([market])

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].market_a_id, "a")
        self.assertEqual(calls[0][1], 12)

    def test_discover_relations_retries_invalid_structured_response(self):
        responses = [
            {"output_text": json.dumps({"version": "0.1"})},
            {
                "output_text": json.dumps(
                    {
                        "relations": [
                            {
                                "relation_type": "mutually_exclusive",
                                "market_a_id": "a",
                                "market_b_id": "b",
                                "direction": "none",
                                "confidence": 0.97,
                                "trade_allowed": True,
                                "risk_flags": [],
                                "reason": "both cannot happen",
                            }
                        ]
                    }
                )
            },
        ]
        calls = []

        def transport(payload, timeout):
            calls.append((payload, timeout))
            return responses.pop(0)

        client = OpenAIRuleDiscoveryClient(
            model="test-model",
            api_key="test-key",
            retries=1,
            transport=transport,
        )
        market = MarketText("a", "Will A happen?", "", ["Yes", "No"], "", "", "will-a-happen")

        candidates = client.discover_relations([market])

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].relation_type, "mutually_exclusive")
        self.assertEqual(len(calls), 2)

    def test_discover_relations_accepts_relation_list_and_skips_invalid_rows(self):
        response = {
            "output_text": json.dumps(
                [
                    {
                        "relation_type": "implies",
                        "market_a_id": "a",
                        "market_b_id": "b",
                        "direction": "a_implies_b",
                        "confidence": 0.98,
                        "trade_allowed": True,
                        "risk_flags": [],
                        "reason": "a implies b",
                    },
                    {
                        "relation_type": "implies",
                        "market_a_id": "bad",
                        "market_b_id": "row",
                        "direction": "a_implies_b",
                        "confidence": 3.0,
                        "trade_allowed": True,
                        "risk_flags": [],
                        "reason": "invalid confidence",
                    },
                ]
            )
        }

        client = OpenAIRuleDiscoveryClient(
            model="test-model",
            api_key="test-key",
            transport=lambda payload, timeout: response,
        )
        market = MarketText("a", "Will A happen?", "", ["Yes", "No"], "", "", "will-a-happen")

        candidates = client.discover_relations([market])

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].market_a_id, "a")

    def test_verify_group_parses_structured_response(self):
        response = {
            "output_text": json.dumps(
                {
                    "verdict": "exhaustive_group",
                    "confidence": 0.99,
                    "trade_allowed": True,
                    "risk_flags": [],
                    "reason": "all listed markets form the full outcome set",
                }
            )
        }
        calls = []

        def transport(payload, timeout):
            calls.append((payload, timeout))
            return response

        client = OpenAIExhaustiveGroupVerifierClient(
            model="test-model",
            api_key="test-key",
            timeout=12,
            transport=transport,
        )
        market = MarketText("a", "Will A win?", "", ["Yes", "No"], "", "", "a-wins")

        result = client.verify_group([market])

        self.assertEqual(result["verdict"], "exhaustive_group")
        self.assertEqual(result["confidence"], 0.99)
        self.assertEqual(calls[0][1], 12)
        self.assertEqual(calls[0][0]["text"]["format"]["name"], "polymarket_exhaustive_group_verification")

    def test_verify_group_retries_invalid_structured_response(self):
        responses = [
            {"output_text": "not-json"},
            {
                "output_text": json.dumps(
                    {
                        "verdict": "uncertain",
                        "confidence": 0.2,
                        "trade_allowed": False,
                        "risk_flags": ["insufficient_information"],
                        "reason": "insufficient text",
                    }
                )
            },
        ]

        def transport(payload, timeout):
            return responses.pop(0)

        client = OpenAIExhaustiveGroupVerifierClient(
            model="test-model",
            api_key="test-key",
            retries=1,
            transport=transport,
        )
        market = MarketText("a", "Will A win?", "", ["Yes", "No"], "", "", "a-wins")

        result = client.verify_group([market])

        self.assertEqual(result["verdict"], "uncertain")
        self.assertFalse(result["trade_allowed"])

    def test_missing_api_key_raises_clear_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(OpenAIConfigError):
                OpenAIRuleDiscoveryClient(model="test-model")

    def test_invalid_response_raises_clear_error(self):
        client = OpenAIRuleDiscoveryClient(
            model="test-model",
            api_key="test-key",
            transport=lambda payload, timeout: {"output": []},
        )

        with self.assertRaises(OpenAIResponseError):
            client.discover_relations([MarketText("a", "Will A happen?", "", ["Yes", "No"], "", "", "")])


if __name__ == "__main__":
    unittest.main()
