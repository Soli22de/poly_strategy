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

    def test_build_payload_can_use_chat_completions_format(self):
        client = OpenAIRuleDiscoveryClient(model="test-model", api_key="test-key", api_mode="chat", max_output_tokens=123)
        market = MarketText("a", "Will A happen?", "", ["Yes", "No"], "", "", "will-a-happen")

        payload = client.build_payload([market])

        self.assertEqual(payload["model"], "test-model")
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(payload["messages"][1]["role"], "user")
        self.assertEqual(payload["max_completion_tokens"], 123)
        self.assertNotIn("input", payload)
        self.assertNotIn("text", payload)
        self.assertEqual(payload["response_format"]["type"], "json_schema")
        self.assertEqual(payload["response_format"]["json_schema"]["name"], "polymarket_relation_discovery")
        self.assertTrue(payload["response_format"]["json_schema"]["strict"])

    def test_verify_group_can_use_chat_completions_format(self):
        client = OpenAIExhaustiveGroupVerifierClient(model="test-model", api_key="test-key", api_mode="chat")
        market = MarketText("a", "Will A win?", "", ["Yes", "No"], "", "", "a-wins")

        payload = client.build_payload([market])

        self.assertEqual(payload["response_format"]["json_schema"]["name"], "polymarket_exhaustive_group_verification")
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertIn("Will A win?", payload["messages"][1]["content"])

    def test_build_payload_omits_reasoning_for_non_reasoning_model(self):
        client = OpenAIRuleDiscoveryClient(model="grok-4.20-0309-non-reasoning", api_key="test-key")
        market = MarketText("a", "Will A happen?", "", ["Yes", "No"], "", "", "will-a-happen")

        payload = client.build_payload([market])

        self.assertNotIn("reasoning", payload)

    def test_verify_group_payload_omits_reasoning_for_non_reasoning_model(self):
        client = OpenAIExhaustiveGroupVerifierClient(model="grok-4.20-0309-non-reasoning", api_key="test-key")
        market = MarketText("a", "Will A win?", "", ["Yes", "No"], "", "", "a-wins")

        payload = client.build_payload([market])

        self.assertNotIn("reasoning", payload)

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

    def test_discover_relations_parses_chat_completions_response(self):
        response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
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
                        )
                    }
                }
            ]
        }
        calls = []

        def transport(payload, timeout):
            calls.append((payload, timeout))
            return response

        client = OpenAIRuleDiscoveryClient(
            model="test-model",
            api_key="test-key",
            timeout=12,
            api_mode="chat",
            transport=transport,
        )
        market = MarketText("a", "Will A happen?", "", ["Yes", "No"], "", "", "will-a-happen")

        candidates = client.discover_relations([market])

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].market_b_id, "b")
        self.assertEqual(calls[0][0]["response_format"]["json_schema"]["name"], "polymarket_relation_discovery")

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

    def test_verify_group_accepts_safe_chat_rejection_aliases(self):
        response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "status": "not_exhaustive",
                                "exhaustive_group": False,
                                "trade_allowed": False,
                                "risk_flags": ["missing_other_possible_winners"],
                                "reason": "only one outcome is provided",
                            }
                        )
                    }
                }
            ]
        }

        client = OpenAIExhaustiveGroupVerifierClient(
            model="test-model",
            api_key="test-key",
            api_mode="chat",
            transport=lambda payload, timeout: response,
        )
        market = MarketText("a", "Will A win?", "", ["Yes", "No"], "", "", "a-wins")

        result = client.verify_group([market])

        self.assertEqual(result["verdict"], "not_exhaustive")
        self.assertEqual(result["confidence"], 0.0)
        self.assertFalse(result["trade_allowed"])

    def test_verify_group_rejects_tradeable_chat_alias_without_confidence(self):
        response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "status": "exhaustive_group",
                                "trade_allowed": True,
                                "risk_flags": [],
                                "reason": "complete",
                            }
                        )
                    }
                }
            ]
        }

        client = OpenAIExhaustiveGroupVerifierClient(
            model="test-model",
            api_key="test-key",
            api_mode="chat",
            retries=0,
            transport=lambda payload, timeout: response,
        )

        with self.assertRaises(OpenAIResponseError):
            client.verify_group([MarketText("a", "Will A win?", "", ["Yes", "No"], "", "", "a-wins")])

    def test_verify_group_parses_json_code_fence(self):
        response = {
            "choices": [
                {
                    "message": {
                        "content": "```json\n"
                        + json.dumps(
                            {
                                "verdict": "not_exhaustive",
                                "confidence": 0.91,
                                "trade_allowed": False,
                                "risk_flags": ["incomplete_outcome_set"],
                                "reason": "missing outcomes",
                            }
                        )
                        + "\n```"
                    }
                }
            ]
        }
        client = OpenAIExhaustiveGroupVerifierClient(
            model="test-model",
            api_key="test-key",
            api_mode="chat",
            transport=lambda payload, timeout: response,
        )

        result = client.verify_group([MarketText("a", "Will A win?", "", ["Yes", "No"], "", "", "a-wins")])

        self.assertEqual(result["verdict"], "not_exhaustive")
        self.assertEqual(result["confidence"], 0.91)

    def test_missing_api_key_raises_clear_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(OpenAIConfigError):
                OpenAIRuleDiscoveryClient(model="test-model")

    def test_invalid_api_mode_raises_clear_error(self):
        with self.assertRaises(OpenAIConfigError):
            OpenAIRuleDiscoveryClient(model="test-model", api_key="test-key", api_mode="legacy")

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
