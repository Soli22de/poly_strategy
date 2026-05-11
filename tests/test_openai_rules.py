import json
import os
import unittest
from unittest.mock import patch

from poly_strategy.openai_rules import (
    OpenAIConfigError,
    OpenAICrossPlatformVerifierClient,
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
        self.assertEqual(payload["temperature"], 0.0)
        self.assertNotIn("input", payload)
        self.assertNotIn("text", payload)
        self.assertEqual(payload["response_format"]["type"], "json_object")
        self.assertIn("polymarket_relation_discovery", payload["messages"][0]["content"])
        self.assertIn('"relations"', payload["messages"][1]["content"])

    def test_chat_payload_can_opt_into_json_schema_response_format(self):
        client = OpenAIRuleDiscoveryClient(
            model="test-model",
            api_key="test-key",
            api_mode="chat",
            chat_response_format="json_schema",
        )
        market = MarketText("a", "Will A happen?", "", ["Yes", "No"], "", "", "will-a-happen")

        payload = client.build_payload([market])

        self.assertEqual(payload["response_format"]["type"], "json_schema")
        self.assertEqual(payload["response_format"]["json_schema"]["name"], "polymarket_relation_discovery")
        self.assertTrue(payload["response_format"]["json_schema"]["strict"])

    def test_client_normalizes_explicit_proxy(self):
        client = OpenAIRuleDiscoveryClient(model="test-model", api_key="test-key", proxy="127.0.0.1:10808")

        self.assertEqual(client.proxy, "http://127.0.0.1:10808")

    def test_client_can_read_proxy_from_environment(self):
        with patch.dict(os.environ, {"PROXY": "127.0.0.1:10808"}, clear=True):
            client = OpenAIRuleDiscoveryClient(model="test-model", api_key="test-key")

        self.assertEqual(client.proxy, "http://127.0.0.1:10808")

    def test_chat_post_uses_configured_proxy_opener(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps({"choices": [{"message": {"content": "{\"relations\":[]}"}}]}).encode("utf-8")

        class FakeOpener:
            def __init__(self):
                self.calls = []

            def open(self, request, timeout):
                self.calls.append((request, timeout))
                return FakeResponse()

        client = OpenAIRuleDiscoveryClient(
            model="test-model",
            api_key="test-key",
            api_mode="chat",
            proxy="127.0.0.1:10808",
            chat_stream=False,
        )
        fake_opener = FakeOpener()
        client._opener = fake_opener

        response = client._post_chat_completions({"model": "test-model", "messages": []}, timeout=12)

        self.assertEqual(response["choices"][0]["message"]["content"], "{\"relations\":[]}")
        self.assertEqual(len(fake_opener.calls), 1)
        self.assertEqual(fake_opener.calls[0][1], 12)

    def test_chat_post_defaults_to_streaming(self):
        class FakeStreamResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def __iter__(self):
                events = [
                    {"choices": [{"delta": {"content": "{\"relations\":["}}]},
                    {
                        "choices": [
                            {
                                "delta": {
                                    "content": (
                                        "{\"relation_type\":\"implies\","
                                        "\"market_a_id\":\"a\","
                                        "\"market_b_id\":\"b\","
                                        "\"direction\":\"a_implies_b\","
                                        "\"confidence\":0.99,"
                                        "\"trade_allowed\":true,"
                                        "\"risk_flags\":[],"
                                        "\"reason\":\"a implies b\"}"
                                    )
                                }
                            }
                        ]
                    },
                    {"choices": [{"delta": {"content": "]}"}}]},
                ]
                lines = [f"data: {json.dumps(event)}\n\n".encode("utf-8") for event in events]
                lines.append(b"data: [DONE]\n\n")
                return iter(lines)

        class FakeOpener:
            def __init__(self):
                self.calls = []

            def open(self, request, timeout):
                self.calls.append((request, timeout))
                return FakeStreamResponse()

        client = OpenAIRuleDiscoveryClient(model="test-model", api_key="test-key", api_mode="chat")
        fake_opener = FakeOpener()
        client._opener = fake_opener

        response = client._post_chat_completions({"model": "test-model", "messages": []}, timeout=12)

        payload = json.loads(fake_opener.calls[0][0].data.decode("utf-8"))
        self.assertTrue(payload["stream"])
        self.assertEqual(fake_opener.calls[0][0].get_header("Accept"), "text/event-stream")
        self.assertEqual(json.loads(response["choices"][0]["message"]["content"])["relations"][0]["market_a_id"], "a")

    def test_chat_stream_can_be_disabled_from_environment(self):
        with patch.dict(os.environ, {"OPENAI_CHAT_STREAM": "0"}, clear=True):
            client = OpenAIRuleDiscoveryClient(model="test-model", api_key="test-key", api_mode="chat")

        self.assertFalse(client.chat_stream)

    def test_verify_group_can_use_chat_completions_format(self):
        client = OpenAIExhaustiveGroupVerifierClient(model="test-model", api_key="test-key", api_mode="chat")
        market = MarketText("a", "Will A win?", "", ["Yes", "No"], "", "", "a-wins")

        payload = client.build_payload([market])

        self.assertEqual(payload["response_format"]["type"], "json_object")
        self.assertIn("polymarket_exhaustive_group_verification", payload["messages"][0]["content"])
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertIn("Will A win?", payload["messages"][1]["content"])

    def test_cross_platform_verifier_payload_can_use_chat_completions_format(self):
        client = OpenAICrossPlatformVerifierClient(model="test-model", api_key="test-key", api_mode="chat")

        payload = client.build_payload(
            [
                {
                    "polymarket_market_id": "pm1",
                    "polymarket_title": "Will Bitcoin hit 100k in 2026?",
                    "kalshi_ticker": "KXBTC",
                    "kalshi_title": "Will Bitcoin hit 100k in 2026?",
                }
            ]
        )

        self.assertEqual(payload["response_format"]["type"], "json_object")
        self.assertIn("polymarket_kalshi_cross_platform_verification", payload["messages"][0]["content"])
        self.assertIn("Will Bitcoin hit 100k in 2026?", payload["messages"][1]["content"])

    def test_cross_platform_verifier_payload_includes_kalshi_rules(self):
        client = OpenAICrossPlatformVerifierClient(model="test-model", api_key="test-key", api_mode="chat")

        payload = client.build_payload(
            [
                {
                    "polymarket_market_id": "pm1",
                    "polymarket_title": "Will Italy recognize Palestine before 2027?",
                    "kalshi_ticker": "KXRECOGPALESTINE-27-ITA",
                    "kalshi_title": "Who will recognize Palestine? | Italy",
                    "kalshi_rules_primary": "If Italy recognizes Palestine before Jan 1, 2027, then Yes.",
                    "kalshi_rules_secondary": "Formal diplomatic recognition counts; trade relations alone do not count.",
                    "kalshi_close_time": "2027-01-01T04:59:00Z",
                }
            ]
        )

        prompt = payload["messages"][1]["content"]
        self.assertIn("Formal diplomatic recognition counts", prompt)
        self.assertIn("2027-01-01T04:59:00Z", prompt)

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
        self.assertEqual(calls[0][0]["response_format"]["type"], "json_object")

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

    def test_cross_platform_verifier_parses_structured_response(self):
        response = {
            "output_text": json.dumps(
                {
                    "verifications": [
                        {
                            "polymarket_market_id": "pm1",
                            "kalshi_ticker": "KXBTC",
                            "verified_same_binary_event": True,
                            "trade_allowed": True,
                            "confidence": 0.99,
                            "risk_flags": [],
                            "reason": "same binary event",
                        }
                    ]
                }
            )
        }
        client = OpenAICrossPlatformVerifierClient(
            model="test-model",
            api_key="test-key",
            transport=lambda payload, timeout: response,
        )

        rows = client.verify_matches(
            [
                {
                    "polymarket_market_id": "pm1",
                    "polymarket_title": "Will Bitcoin hit 100k in 2026?",
                    "kalshi_ticker": "KXBTC",
                    "kalshi_title": "Will Bitcoin hit 100k in 2026?",
                }
            ]
        )

        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["trade_allowed"])
        self.assertEqual(rows[0]["confidence"], 0.99)

    def test_cross_platform_verifier_accepts_safe_rejection_aliases(self):
        response = {
            "output_text": json.dumps(
                {
                    "results": [
                        {
                            "polymarket_id": "pm1",
                            "ticker": "KXBTC",
                            "same_event": False,
                            "allowed": False,
                            "reason": "different wording",
                        }
                    ]
                }
            )
        }
        client = OpenAICrossPlatformVerifierClient(
            model="test-model",
            api_key="test-key",
            transport=lambda payload, timeout: response,
        )

        rows = client.verify_matches(
            [
                {
                    "polymarket_market_id": "pm1",
                    "polymarket_title": "Will Bitcoin hit 100k in 2026?",
                    "kalshi_ticker": "KXBTC",
                    "kalshi_title": "Will Bitcoin hit 100k in 2026?",
                }
            ]
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["polymarket_market_id"], "pm1")
        self.assertEqual(rows[0]["kalshi_ticker"], "KXBTC")
        self.assertFalse(rows[0]["trade_allowed"])
        self.assertEqual(rows[0]["confidence"], 0.0)

    def test_cross_platform_verifier_blocks_tradeable_row_without_confidence(self):
        response = {
            "output_text": json.dumps(
                {
                    "results": [
                        {
                            "polymarket_market_id": "pm1",
                            "kalshi_ticker": "KXBTC",
                            "verified_same_binary_event": True,
                            "trade_allowed": True,
                            "risk_flags": [],
                            "reason": "same wording",
                        }
                    ]
                }
            )
        }
        client = OpenAICrossPlatformVerifierClient(
            model="test-model",
            api_key="test-key",
            transport=lambda payload, timeout: response,
        )

        rows = client.verify_matches(
            [
                {
                    "polymarket_market_id": "pm1",
                    "polymarket_title": "Will Bitcoin hit 100k in 2026?",
                    "kalshi_ticker": "KXBTC",
                    "kalshi_title": "Will Bitcoin hit 100k in 2026?",
                }
            ]
        )

        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]["trade_allowed"])
        self.assertIn("missing_confidence", rows[0]["risk_flags"])

    def test_cross_platform_verifier_blocks_tradeable_row_below_confidence_threshold(self):
        response = {
            "output_text": json.dumps(
                {
                    "results": [
                        {
                            "polymarket_market_id": "pm1",
                            "kalshi_ticker": "KXBTC",
                            "verified_same_binary_event": True,
                            "trade_allowed": True,
                            "confidence": 0.8,
                            "risk_flags": [],
                            "reason": "same wording",
                        }
                    ]
                }
            )
        }
        client = OpenAICrossPlatformVerifierClient(
            model="test-model",
            api_key="test-key",
            transport=lambda payload, timeout: response,
        )

        rows = client.verify_matches(
            [
                {
                    "polymarket_market_id": "pm1",
                    "polymarket_title": "Will Bitcoin hit 100k in 2026?",
                    "kalshi_ticker": "KXBTC",
                    "kalshi_title": "Will Bitcoin hit 100k in 2026?",
                }
            ]
        )

        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]["trade_allowed"])
        self.assertIn("confidence_below_trade_threshold", rows[0]["risk_flags"])

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
