import json
import os
import time
from typing import Callable, Iterable, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener, urlopen

from poly_strategy.rule_discovery import MarketText, RelationCandidate, market_texts_to_prompt_rows


DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_API_MODE = "responses"
DEFAULT_CHAT_RESPONSE_FORMAT = "json_object"
DEFAULT_CHAT_STREAM = True


def _model_supports_reasoning(model: str) -> bool:
    return "non-reasoning" not in model.lower()


def _normalize_api_mode(api_mode: Optional[str]) -> str:
    value = (api_mode or os.environ.get("OPENAI_API_MODE") or DEFAULT_API_MODE).strip().lower()
    if value in {"responses", "response"}:
        return "responses"
    if value in {"chat", "chat_completions", "chat-completions", "chatcompletions"}:
        return "chat"
    raise OpenAIConfigError(f"unsupported OPENAI_API_MODE: {api_mode!r}")


def _normalize_chat_response_format(value: Optional[str]) -> str:
    normalized = (value or os.environ.get("OPENAI_CHAT_RESPONSE_FORMAT") or DEFAULT_CHAT_RESPONSE_FORMAT).strip().lower()
    if normalized in {"json_object", "json-object", "object"}:
        return "json_object"
    if normalized in {"json_schema", "json-schema", "schema"}:
        return "json_schema"
    if normalized in {"none", "off", "disabled"}:
        return "none"
    raise OpenAIConfigError(f"unsupported OPENAI_CHAT_RESPONSE_FORMAT: {value!r}")


def _optional_float(value: Optional[object]) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in {"", "none", "off", "disabled"}:
        return None
    return float(value)


def _normalize_bool(value: Optional[object], default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on", "enabled"}:
        return True
    if normalized in {"0", "false", "no", "n", "off", "disabled", "none"}:
        return False
    raise OpenAIConfigError(f"unsupported boolean value: {value!r}")


def _normalize_proxy_url(proxy: Optional[str]) -> Optional[str]:
    value = str(proxy or "").strip()
    if not value or value.lower() in {"0", "false", "none", "off"}:
        return None
    if "://" not in value:
        return f"http://{value}"
    return value


def _chat_output_contract(schema_name: str) -> str:
    if schema_name == "polymarket_relation_discovery":
        return json.dumps(
            {
                "relations": [
                    {
                        "relation_type": "implies",
                        "market_a_id": "market_id_that_implies",
                        "market_b_id": "market_id_implied_by_a",
                        "direction": "a_implies_b",
                        "confidence": 0.99,
                        "trade_allowed": True,
                        "risk_flags": [],
                        "reason": "Short wording-based reason.",
                    }
                ]
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    if schema_name == "polymarket_exhaustive_group_verification":
        return json.dumps(
            {
                "verdict": "exhaustive_group",
                "confidence": 0.99,
                "trade_allowed": True,
                "risk_flags": [],
                "reason": "Short wording-based reason.",
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    if schema_name == "polymarket_kalshi_cross_platform_verification":
        return json.dumps(
            {
                "verifications": [
                    {
                        "polymarket_market_id": "polymarket_id",
                        "kalshi_ticker": "kalshi_ticker",
                        "verified_same_binary_event": True,
                        "trade_allowed": True,
                        "confidence": 0.99,
                        "risk_flags": [],
                        "reason": "Short wording-based reason.",
                    }
                ]
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    return "{}"


def _chat_output_instruction(schema_name: str) -> str:
    if schema_name == "polymarket_relation_discovery":
        return (
            'Return {"relations":[]} when no relation exists. '
            "For same-subject same-deadline numeric thresholds, the higher threshold YES implies the lower threshold YES. "
            "Example: if market b is X > 20 and market a is X > 10, use "
            '"market_a_id":"b","market_b_id":"a","direction":"a_implies_b".'
        )
    if schema_name == "polymarket_exhaustive_group_verification":
        return "Return verdict=not_exhaustive or verdict=uncertain when completeness is not proven."
    if schema_name == "polymarket_kalshi_cross_platform_verification":
        return 'Return {"verifications":[]} when no provided pair is the same binary event.'
    return ""


def _relation_chat_prompts(prompt_text: str) -> tuple[str, str]:
    output_contract = _chat_output_contract("polymarket_relation_discovery")
    system_prompt = (
        "You output JSON only. Schema name: polymarket_relation_discovery. "
        "Find deterministic logical relations between binary prediction markets using only the provided market text and market_id values. "
        "Do not predict outcomes, do not cite sources, do not use prices, and do not echo the input. "
        "Never return markdown, safe_items, markets, sources, claims, or answers. "
        "Allowed relation_type values: implies, equivalent, mutually_exclusive, collectively_exhaustive, complement, unknown. "
        "Prefer false negatives over false positives. "
        "For same-subject same-deadline numeric thresholds, higher threshold YES implies lower threshold YES."
    )
    user_prompt = (
        f"Input markets JSON: {prompt_text}\n"
        f"Return exactly one JSON object shaped like this: {output_contract}\n"
        'If no deterministic relation exists, return exactly {"relations":[]}.\n'
        'For threshold implication, set market_a_id to the higher-threshold market, market_b_id to the lower-threshold market, and direction to "a_implies_b".'
    )
    return system_prompt, user_prompt


class OpenAIConfigError(RuntimeError):
    pass


class OpenAIResponseError(RuntimeError):
    pass


class OpenAIRuleDiscoveryClient:
    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        timeout: float = 60.0,
        base_url: Optional[str] = None,
        retries: int = 2,
        max_output_tokens: Optional[int] = 4000,
        reasoning_effort: Optional[str] = "medium",
        verbosity: Optional[str] = None,
        api_mode: Optional[str] = None,
        chat_response_format: Optional[str] = None,
        chat_stream: Optional[bool] = None,
        temperature: Optional[float] = None,
        proxy: Optional[str] = None,
        transport: Optional[Callable[[dict, float], dict]] = None,
    ):
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise OpenAIConfigError("OPENAI_API_KEY is required")
        self.timeout = timeout
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL") or DEFAULT_BASE_URL
        self.retries = max(0, retries)
        self.max_output_tokens = max_output_tokens
        self.reasoning_effort = reasoning_effort
        self.verbosity = verbosity
        self.api_mode = _normalize_api_mode(api_mode)
        self.chat_response_format = _normalize_chat_response_format(chat_response_format)
        stream_value = os.environ.get("OPENAI_CHAT_STREAM") if chat_stream is None else chat_stream
        self.chat_stream = _normalize_bool(stream_value, DEFAULT_CHAT_STREAM)
        temperature_value = os.environ.get("OPENAI_TEMPERATURE") if temperature is None else temperature
        self.temperature = _optional_float(0.0 if temperature_value is None else temperature_value)
        self.proxy = _normalize_proxy_url(proxy or os.environ.get("OPENAI_PROXY") or os.environ.get("PROXY"))
        self._opener = (
            build_opener(ProxyHandler({"http": self.proxy, "https": self.proxy}))
            if self.proxy
            else None
        )
        self._transport = transport or (self._post_chat_completions if self.api_mode == "chat" else self._post_responses)

    def build_payload(self, markets: Iterable[MarketText]) -> dict:
        return self._build_payload(
            markets,
            system_prompt=_SYSTEM_PROMPT,
            schema_name="polymarket_relation_discovery",
            schema=_RESPONSE_SCHEMA,
        )

    def _build_payload(self, markets: Iterable[MarketText], system_prompt: str, schema_name: str, schema: dict) -> dict:
        market_rows = market_texts_to_prompt_rows(list(markets))
        prompt_text = json.dumps({"markets": market_rows}, ensure_ascii=True, sort_keys=True)
        if self.api_mode == "chat":
            if schema_name == "polymarket_relation_discovery":
                chat_system_prompt, chat_user_prompt = _relation_chat_prompts(prompt_text)
            else:
                required_keys = ", ".join(schema.get("required", []))
                output_contract = _chat_output_contract(schema_name)
                output_instruction = _chat_output_instruction(schema_name)
                chat_system_prompt = (
                    f"{system_prompt}\n\n"
                    "Output rules for chat-compatible providers:\n"
                    "- Return exactly one valid JSON object and nothing else.\n"
                    "- Do not use markdown fences, prose, citations, sources, or external facts.\n"
                    "- Do not echo the input rows or create top-level keys such as markets, safe_items, sources, claims, or answers.\n"
                    f"- Schema name: {schema_name}.\n"
                    f"- The top-level required key(s) are: {required_keys}.\n"
                    f"- Required JSON shape example:\n{output_contract}\n"
                    f"- {output_instruction}"
                )
                if self.chat_response_format == "json_schema":
                    chat_system_prompt += f"\n- Full JSON Schema:\n{json.dumps(schema, ensure_ascii=True, sort_keys=True)}"
                chat_user_prompt = (
                    "Do not answer the prediction market question and do not estimate probabilities. "
                    "Compare only the provided market rows under the system task. "
                    "Use only the required output shape. "
                    "Never return verification sources, market summaries, safe_items, or a top-level markets key.\n\n"
                    f"Input markets JSON:\n{prompt_text}"
                )
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": chat_system_prompt},
                    {"role": "user", "content": chat_user_prompt},
                ],
            }
            self._apply_chat_response_format(payload, schema_name, schema)
            if self.max_output_tokens is not None:
                payload["max_completion_tokens"] = self.max_output_tokens
            if self.temperature is not None:
                payload["temperature"] = self.temperature
            return payload

        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": system_prompt,
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt_text,
                        }
                    ],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                }
            },
        }
        if self.max_output_tokens is not None:
            payload["max_output_tokens"] = self.max_output_tokens
        if self.reasoning_effort and _model_supports_reasoning(self.model):
            payload["reasoning"] = {"effort": self.reasoning_effort}
        if self.verbosity:
            payload.setdefault("text", {})["verbosity"] = self.verbosity
        return payload

    def discover_relations(self, markets: Iterable[MarketText]) -> List[RelationCandidate]:
        payload = self.build_payload(list(markets))
        return _call_parser_with_retries(self._call_with_retries, payload, self.retries, _parse_relation_response)

    def _post_responses(self, payload: dict, timeout: float) -> dict:
        request = Request(
            _responses_url(self.base_url),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "authorization": f"Bearer {self.api_key}",
                "content-type": "application/json",
                "accept": "application/json",
                "user-agent": "poly-strategy/0.1",
            },
            method="POST",
        )
        with self._open_request(request, timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _post_chat_completions(self, payload: dict, timeout: float) -> dict:
        request_payload = dict(payload)
        if self.chat_stream:
            request_payload["stream"] = True
        request = Request(
            _chat_completions_url(self.base_url),
            data=json.dumps(request_payload).encode("utf-8"),
            headers={
                "authorization": f"Bearer {self.api_key}",
                "content-type": "application/json",
                "accept": "text/event-stream" if self.chat_stream else "application/json",
                "user-agent": "poly-strategy/0.1",
            },
            method="POST",
        )
        with self._open_request(request, timeout) as response:
            if self.chat_stream:
                return _parse_chat_stream_response(response)
            return json.loads(response.read().decode("utf-8"))

    def _open_request(self, request: Request, timeout: float):
        if self._opener is not None:
            return self._opener.open(request, timeout=timeout)
        return urlopen(request, timeout=timeout)

    def _apply_chat_response_format(self, payload: dict, schema_name: str, schema: dict) -> None:
        if self.chat_response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}
            return
        if self.chat_response_format == "json_schema":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                },
            }
            return
        if self.chat_response_format != "none":
            raise OpenAIConfigError(f"unsupported chat response format: {self.chat_response_format!r}")

    def _call_with_retries(self, payload: dict) -> dict:
        last_error = None
        for attempt in range(self.retries + 1):
            try:
                return self._transport(payload, self.timeout)
            except (HTTPError, URLError, TimeoutError, ConnectionError, OSError) as exc:
                last_error = exc
                if attempt >= self.retries or not _is_retryable(exc):
                    raise
                time.sleep(min(2 ** attempt, 5))
        raise OpenAIResponseError(str(last_error))


class OpenAIExhaustiveGroupVerifierClient(OpenAIRuleDiscoveryClient):
    def build_payload(self, markets: Iterable[MarketText]) -> dict:
        return self._build_payload(
            markets,
            system_prompt=_GROUP_SYSTEM_PROMPT,
            schema_name="polymarket_exhaustive_group_verification",
            schema=_GROUP_RESPONSE_SCHEMA,
        )

    def verify_group(self, markets: Iterable[MarketText]) -> dict:
        payload = self.build_payload(list(markets))
        return _call_parser_with_retries(self._call_with_retries, payload, self.retries, _parse_group_response)


class OpenAICrossPlatformVerifierClient(OpenAIRuleDiscoveryClient):
    def build_payload(self, matches: Iterable[dict]) -> dict:
        rows = [_cross_platform_prompt_row(match) for match in matches]
        prompt_text = json.dumps({"matches": rows}, ensure_ascii=True, sort_keys=True)
        if self.api_mode == "chat":
            required_keys = ", ".join(_CROSS_PLATFORM_RESPONSE_SCHEMA.get("required", []))
            output_contract = _chat_output_contract("polymarket_kalshi_cross_platform_verification")
            output_instruction = _chat_output_instruction("polymarket_kalshi_cross_platform_verification")
            chat_system_prompt = (
                f"{_CROSS_PLATFORM_SYSTEM_PROMPT}\n\n"
                "Output rules for chat-compatible providers:\n"
                "- Return exactly one valid JSON object and nothing else.\n"
                "- Do not use markdown fences, prose, citations, sources, or external facts.\n"
                "- Do not echo the input rows or create top-level keys such as matches, safe_items, sources, claims, or answers.\n"
                "- Schema name: polymarket_kalshi_cross_platform_verification.\n"
                f"- The top-level required key(s) are: {required_keys}.\n"
                f"- Required JSON shape example:\n{output_contract}\n"
                f"- {output_instruction}"
            )
            if self.chat_response_format == "json_schema":
                chat_system_prompt += (
                    f"\n- Full JSON Schema:\n{json.dumps(_CROSS_PLATFORM_RESPONSE_SCHEMA, ensure_ascii=True, sort_keys=True)}"
                )
            chat_user_prompt = (
                "Use only the provided market text. Do not estimate probabilities or use prices. "
                "Never return verification sources, market summaries, safe_items, or a top-level matches key. "
                "Return only one JSON object matching the schema; no markdown, no prose.\n\n"
                f"Input matches JSON:\n{prompt_text}"
            )
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": chat_system_prompt},
                    {"role": "user", "content": chat_user_prompt},
                ],
            }
            self._apply_chat_response_format(
                payload,
                "polymarket_kalshi_cross_platform_verification",
                _CROSS_PLATFORM_RESPONSE_SCHEMA,
            )
            if self.max_output_tokens is not None:
                payload["max_completion_tokens"] = self.max_output_tokens
            if self.temperature is not None:
                payload["temperature"] = self.temperature
            return payload

        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": _CROSS_PLATFORM_SYSTEM_PROMPT,
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt_text,
                        }
                    ],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "polymarket_kalshi_cross_platform_verification",
                    "strict": True,
                    "schema": _CROSS_PLATFORM_RESPONSE_SCHEMA,
                }
            },
        }
        if self.max_output_tokens is not None:
            payload["max_output_tokens"] = self.max_output_tokens
        if self.reasoning_effort and _model_supports_reasoning(self.model):
            payload["reasoning"] = {"effort": self.reasoning_effort}
        if self.verbosity:
            payload.setdefault("text", {})["verbosity"] = self.verbosity
        return payload

    def verify_matches(self, matches: Iterable[dict]) -> List[dict]:
        payload = self.build_payload(list(matches))
        return _call_parser_with_retries(self._call_with_retries, payload, self.retries, _parse_cross_platform_response)


_SYSTEM_PROMPT = """You identify conservative logical relations between binary prediction markets.

Definitions:
- A => B means: if market A resolves YES, market B must resolve YES under the written resolution criteria.
- equivalent means A YES iff B YES.
- mutually_exclusive means A YES and B YES cannot both happen.
- collectively_exhaustive means A YES or B YES must happen; they cannot both resolve NO.
- complement means exactly one of A YES and B YES must happen.

Workflow:
- Compare every plausible high-confidence pair in the provided batch.
- Use neg_risk_market_id, group_item_title, group_item_threshold, question, description, end_date, and outcomes.
- Shared non-empty neg_risk_market_id with different group items is strong evidence for mutually_exclusive.
- Winner markets for different teams in the same competition are mutually_exclusive, but not collectively_exhaustive unless every possible winner is present.
- Range/bracket markets for the same event are mutually_exclusive when their written intervals do not overlap.
- Use collectively_exhaustive or complement only when the written criteria guarantee at least one or exactly one YES.
- Use implication only when one YES resolution necessarily forces the other YES resolution; set direction precisely.

Safety:
- Prefer false negatives over false positives.
- Do not estimate real-world probabilities.
- Do not use market prices, liquidity, popularity, or outside assumptions.
- Use only the provided market IDs.
- Set trade_allowed=false and add risk_flags when wording, deadlines, resolution sources, or subjects may differ.
- Return only structured JSON matching the schema.
"""


_GROUP_SYSTEM_PROMPT = """You verify whether a provided set of binary prediction markets is a complete exhaustive outcome set.

Definitions:
- exhaustive_group means exactly one provided market must resolve YES and every other provided market must resolve NO.
- The set must cover every possible YES outcome under the written resolution criteria.
- Shared neg_risk_market_id is useful evidence for mutual exclusion, but it is not enough to prove completeness.

Workflow:
- Use only the provided market IDs and market text.
- Compare question, description, end_date, slug, neg_risk_market_id, group_item_title, group_item_threshold, and outcomes.
- Return exhaustive_group only when all markets clearly describe the same event/resolution source/deadline and no possible winner/outcome is missing.
- Return not_exhaustive if the provided markets are only a subset, if an unlisted outcome can win, or if multiple listed outcomes could resolve YES.
- Return uncertain when wording is ambiguous or the market text is insufficient.

Safety:
- Prefer false negatives over false positives.
- Do not use prices, liquidity, popularity, or outside assumptions.
- Set trade_allowed=false unless the group is complete and exactly-one-YES with high confidence.
- Add risk_flags for any reason a trade could be unsafe.
- Return only structured JSON matching the schema.
"""


_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "relations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "relation_type": {
                        "type": "string",
                        "enum": [
                            "implies",
                            "equivalent",
                            "mutually_exclusive",
                            "collectively_exhaustive",
                            "complement",
                            "unknown",
                        ],
                    },
                    "market_a_id": {"type": "string"},
                    "market_b_id": {"type": "string"},
                    "direction": {
                        "type": "string",
                        "enum": ["a_implies_b", "b_implies_a", "bidirectional", "none"],
                    },
                    "confidence": {"type": "number"},
                    "trade_allowed": {"type": "boolean"},
                    "risk_flags": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "different_resolution_source",
                                "different_deadline",
                                "ambiguous_wording",
                                "conditional_or_fallback_resolution",
                                "non_binary_or_non_yes_no",
                                "stale_or_closed_market",
                                "insufficient_information",
                                "possible_subject_mismatch",
                            ],
                        },
                    },
                    "reason": {"type": "string"},
                },
                "required": [
                    "relation_type",
                    "market_a_id",
                    "market_b_id",
                    "direction",
                    "confidence",
                    "trade_allowed",
                    "risk_flags",
                    "reason",
                ],
            },
        }
    },
    "required": ["relations"],
}


_GROUP_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "verdict": {
            "type": "string",
            "enum": ["exhaustive_group", "not_exhaustive", "uncertain"],
        },
        "confidence": {"type": "number"},
        "trade_allowed": {"type": "boolean"},
        "risk_flags": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [
                    "incomplete_outcome_set",
                    "not_same_event",
                    "not_exactly_one_yes",
                    "different_resolution_source",
                    "different_deadline",
                    "ambiguous_wording",
                    "conditional_or_fallback_resolution",
                    "non_binary_or_non_yes_no",
                    "stale_or_closed_market",
                    "insufficient_information",
                    "possible_subject_mismatch",
                ],
            },
        },
        "reason": {"type": "string"},
    },
    "required": ["verdict", "confidence", "trade_allowed", "risk_flags", "reason"],
}


def _responses_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/responses"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/responses"
    return f"{normalized}/v1/responses"


def _chat_completions_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/chat/completions"
    return f"{normalized}/v1/chat/completions"


def _parse_chat_stream_response(response) -> dict:
    content_parts = []
    for data in _iter_sse_data(response):
        if data == "[DONE]":
            break
        try:
            event = json.loads(data)
        except json.JSONDecodeError as exc:
            raise OpenAIResponseError("OpenAI chat stream emitted invalid JSON") from exc
        content = _extract_chat_stream_content(event)
        if content:
            content_parts.append(content)
    return {"choices": [{"message": {"content": "".join(content_parts)}}]}


def _iter_sse_data(response):
    data_lines = []
    for raw_chunk in response:
        if isinstance(raw_chunk, bytes):
            chunk = raw_chunk.decode("utf-8", errors="replace")
        else:
            chunk = str(raw_chunk)
        for line in chunk.splitlines():
            line = line.rstrip("\r\n")
            if not line:
                if data_lines:
                    yield "\n".join(data_lines)
                    data_lines = []
                continue
            if line.startswith(":"):
                continue
            if not line.startswith("data:"):
                continue
            data_lines.append(line[5:].lstrip())
    if data_lines:
        yield "\n".join(data_lines)


def _extract_chat_stream_content(event: dict) -> str:
    choices = event.get("choices")
    if not isinstance(choices, list):
        return ""
    parts = []
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        delta = choice.get("delta")
        if isinstance(delta, dict):
            content = _content_value_to_text(delta.get("content"))
            if content:
                parts.append(content)
            text = _content_value_to_text(delta.get("text"))
            if text:
                parts.append(text)
        message = choice.get("message")
        if isinstance(message, dict):
            content = _content_value_to_text(message.get("content"))
            if content:
                parts.append(content)
        text = _content_value_to_text(choice.get("text"))
        if text:
            parts.append(text)
    return "".join(parts)


def _content_value_to_text(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def _extract_output_text(response: dict) -> str:
    output_text = response.get("output_text")
    if isinstance(output_text, str) and output_text:
        return output_text

    output = response.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                    return part["text"]

    choices = response.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message")
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if isinstance(content, str) and content:
                return content
            if isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    if part.get("type") in {"text", "output_text"} and isinstance(part.get("text"), str):
                        return part["text"]
            if isinstance(message.get("text"), str) and message["text"]:
                return message["text"]
    raise OpenAIResponseError("OpenAI response is missing output text")


def _call_parser_with_retries(call_fn: Callable[[dict], dict], payload: dict, retries: int, parser: Callable[[dict], object]):
    last_error = None
    for attempt in range(retries + 1):
        try:
            return parser(call_fn(payload))
        except OpenAIResponseError as exc:
            last_error = exc
            if attempt >= retries:
                raise
            time.sleep(min(2 ** attempt, 5))
    raise OpenAIResponseError(str(last_error))


def _parse_relation_response(response: dict) -> List[RelationCandidate]:
    content = _extract_output_text(response)
    try:
        parsed = _loads_json_payload(content)
    except json.JSONDecodeError as exc:
        raise OpenAIResponseError("OpenAI response was not valid JSON") from exc
    if isinstance(parsed, list):
        relations = parsed
    elif isinstance(parsed, dict):
        relations = parsed.get("relations")
    else:
        raise OpenAIResponseError("OpenAI response was not a JSON object or relation list")
    if not isinstance(relations, list):
        raise OpenAIResponseError("OpenAI response is missing relations")
    candidates = []
    for row in relations:
        if not isinstance(row, dict):
            continue
        try:
            candidates.append(_candidate_from_row(row))
        except OpenAIResponseError:
            continue
    return candidates


def _parse_group_response(response: dict) -> dict:
    content = _extract_output_text(response)
    try:
        parsed = _loads_json_payload(content)
    except json.JSONDecodeError as exc:
        raise OpenAIResponseError("OpenAI response was not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise OpenAIResponseError("OpenAI exhaustive group verification is not a JSON object")
    return _group_verification_from_row(parsed)


def _loads_json_payload(content: str):
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        stripped = content.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            return json.loads("\n".join(lines).strip())
        starts = [index for index in (stripped.find("{"), stripped.find("[")) if index >= 0]
        if not starts:
            raise
        start = min(starts)
        end = max(stripped.rfind("}"), stripped.rfind("]"))
        if end <= start:
            raise
        return json.loads(stripped[start : end + 1])


def _candidate_from_row(row: dict) -> RelationCandidate:
    try:
        risk_flags = row.get("risk_flags") or []
        if not isinstance(risk_flags, list):
            raise ValueError("risk_flags must be a list")
        trade_allowed = row["trade_allowed"]
        if not isinstance(trade_allowed, bool):
            raise ValueError("trade_allowed must be a boolean")
        confidence = float(row["confidence"])
        if confidence < 0 or confidence > 1:
            raise ValueError("confidence must be between 0 and 1")
        return RelationCandidate(
            relation_type=str(row["relation_type"]),
            market_a_id=str(row["market_a_id"]),
            market_b_id=str(row["market_b_id"]),
            direction=str(row["direction"]),
            confidence=confidence,
            trade_allowed=trade_allowed,
            risk_flags=[str(flag) for flag in risk_flags],
            reason=str(row.get("reason") or ""),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise OpenAIResponseError("OpenAI relation candidate is invalid") from exc


def _group_verification_from_row(row: dict) -> dict:
    try:
        risk_flags = row.get("risk_flags") or []
        if not isinstance(risk_flags, list):
            raise ValueError("risk_flags must be a list")
        trade_allowed = row["trade_allowed"]
        if not isinstance(trade_allowed, bool):
            raise ValueError("trade_allowed must be a boolean")
        if "confidence" in row:
            confidence = float(row["confidence"])
        elif trade_allowed:
            raise ValueError("tradeable verification must include confidence")
        else:
            confidence = 0.0
        if confidence < 0 or confidence > 1:
            raise ValueError("confidence must be between 0 and 1")
        verdict = _normalize_group_verdict(row)
        if verdict not in {"exhaustive_group", "not_exhaustive", "uncertain"}:
            raise ValueError("unsupported verdict")
        return {
            "verdict": verdict,
            "confidence": confidence,
            "trade_allowed": trade_allowed,
            "risk_flags": [str(flag) for flag in risk_flags],
            "reason": str(row.get("reason") or ""),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise OpenAIResponseError("OpenAI exhaustive group verification is invalid") from exc


def _parse_cross_platform_response(response: dict) -> List[dict]:
    content = _extract_output_text(response)
    try:
        parsed = _loads_json_payload(content)
    except json.JSONDecodeError as exc:
        raise OpenAIResponseError("OpenAI response was not valid JSON") from exc
    if isinstance(parsed, dict):
        verifications = parsed.get("verifications")
        if verifications is None:
            for key in ["results", "matches", "items", "verification"]:
                value = parsed.get(key)
                if isinstance(value, list):
                    verifications = value
                    break
                if isinstance(value, dict):
                    verifications = [value]
                    break
        if verifications is None and "polymarket_market_id" in parsed and "kalshi_ticker" in parsed:
            verifications = [parsed]
    elif isinstance(parsed, list):
        verifications = parsed
    else:
        raise OpenAIResponseError("OpenAI cross-platform verification was not a JSON object or list")
    if not isinstance(verifications, list):
        raise OpenAIResponseError("OpenAI cross-platform verification is missing verifications")
    rows = []
    for row in verifications:
        if not isinstance(row, dict):
            continue
        try:
            rows.append(_cross_platform_verification_from_row(row))
        except OpenAIResponseError:
            continue
    return rows


def _cross_platform_verification_from_row(row: dict) -> dict:
    try:
        risk_flags = _risk_flags_from_value(row.get("risk_flags") or row.get("risks") or [])
        trade_allowed = _bool_from_value(
            _first_present(row, ["trade_allowed", "allowed", "tradeable", "is_tradeable"])
        )
        if trade_allowed is None:
            raise ValueError("trade_allowed must be a boolean")
        confidence_value = _first_present(row, ["confidence", "score"])
        missing_confidence = confidence_value is None
        if missing_confidence:
            if trade_allowed:
                risk_flags.append("missing_confidence")
                trade_allowed = False
            confidence = 0.0
        else:
            confidence = float(confidence_value)
        if confidence < 0 or confidence > 1:
            raise ValueError("confidence must be between 0 and 1")
        verified_same_binary_event = _bool_from_value(
            _first_present(row, ["verified_same_binary_event", "same_binary_event", "same_event", "same"])
        )
        if verified_same_binary_event is None:
            verified_same_binary_event = trade_allowed
        if trade_allowed and (not verified_same_binary_event or confidence < 0.95 or risk_flags):
            trade_allowed = False
            if confidence < 0.95 and "confidence_below_trade_threshold" not in risk_flags:
                risk_flags.append("confidence_below_trade_threshold")
        polymarket_market_id = _first_present(
            row, ["polymarket_market_id", "poly_market_id", "polymarket_id", "poly_id", "market_id"]
        )
        kalshi_ticker = _first_present(row, ["kalshi_ticker", "ticker", "kalshi_market_id", "kalshi_id", "market_ticker"])
        if polymarket_market_id is None or kalshi_ticker is None:
            raise ValueError("missing market identifiers")
        return {
            "polymarket_market_id": str(polymarket_market_id),
            "kalshi_ticker": str(kalshi_ticker),
            "verified_same_binary_event": verified_same_binary_event,
            "trade_allowed": trade_allowed,
            "confidence": confidence,
            "risk_flags": risk_flags,
            "reason": str(row.get("reason") or ""),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise OpenAIResponseError("OpenAI cross-platform verification is invalid") from exc


def _first_present(row: dict, keys: Iterable[str]):
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return None


def _bool_from_value(value) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "1", "allowed", "trade_allowed", "same"}:
            return True
        if normalized in {"false", "no", "n", "0", "rejected", "not_allowed", "different"}:
            return False
    return None


def _risk_flags_from_value(value) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(flag) for flag in value]
    if isinstance(value, str):
        return [value]
    raise ValueError("risk_flags must be a list or string")


def _normalize_group_verdict(row: dict) -> str:
    verdict = row.get("verdict", row.get("status"))
    if isinstance(verdict, str):
        normalized = verdict.strip().lower()
        if normalized in {"exhaustive_group", "not_exhaustive", "uncertain"}:
            return normalized
        if normalized in {"exhaustive", "complete"}:
            return "exhaustive_group"
        if normalized in {"incomplete", "not exhaustive"}:
            return "not_exhaustive"
    exhaustive = row.get("exhaustive_group")
    if isinstance(exhaustive, bool):
        return "exhaustive_group" if exhaustive else "not_exhaustive"
    raise ValueError("missing verdict")


def _cross_platform_prompt_row(match: dict) -> dict:
    return {
        "polymarket_market_id": str(match.get("polymarket_market_id") or ""),
        "polymarket_title": str(match.get("polymarket_title") or ""),
        "polymarket_question": str(match.get("polymarket_question") or match.get("polymarket_title") or ""),
        "polymarket_description": str(match.get("polymarket_description") or "")[:2000],
        "polymarket_end_date": str(match.get("polymarket_end_date") or ""),
        "polymarket_resolution_source": str(match.get("polymarket_resolution_source") or ""),
        "kalshi_ticker": str(match.get("kalshi_ticker") or ""),
        "kalshi_event_ticker": str(match.get("kalshi_event_ticker") or ""),
        "kalshi_title": str(match.get("kalshi_title") or ""),
        "kalshi_rules_primary": str(match.get("kalshi_rules_primary") or ""),
        "kalshi_rules_secondary": str(match.get("kalshi_rules_secondary") or "")[:2500],
        "kalshi_close_time": str(match.get("kalshi_close_time") or ""),
        "kalshi_early_close_condition": str(match.get("kalshi_early_close_condition") or ""),
        "score": float(match.get("score") or 0.0),
        "status": str(match.get("status") or ""),
    }


_CROSS_PLATFORM_SYSTEM_PROMPT = """You verify whether a Polymarket market and a Kalshi market are the same binary event.

Definitions:
- verified_same_binary_event means both markets resolve on the same underlying real-world event, with the same substance and compatible resolution criteria.
- trade_allowed means the pair is safe to trade as a same-event cross-venue hedge or arb candidate.

Workflow:
- Compare question/title, subject, deadline, resolution source, and wording.
- Be conservative: prefer false negatives over false positives.
- Treat a pair as tradeable only when YES on one venue and YES on the other venue are economically equivalent.
- Reject pairs with different subjects, different event deadlines that can change payout, or clearly incompatible resolution criteria.
- Do not reject solely because one venue has a later administrative close/settlement time after the underlying event deadline.
- A Polymarket market that belongs to a multi-outcome event can still match a Kalshi binary market when the provided group item/candidate name makes the YES condition the same.
- Reject pairs where the supplied text leaves a realistic path for one venue to resolve YES while the other resolves NO.
- Ignore market prices and liquidity.
- Every verification row MUST include confidence as a number from 0 to 1.
- If trade_allowed=true, confidence must be at least 0.95 and risk_flags must be empty.
- If confidence is missing, the downstream trading system will reject the pair.
- Return only structured JSON matching the schema."""


_CROSS_PLATFORM_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "verifications": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "polymarket_market_id": {"type": "string"},
                    "kalshi_ticker": {"type": "string"},
                    "verified_same_binary_event": {"type": "boolean"},
                    "trade_allowed": {"type": "boolean"},
                    "confidence": {"type": "number"},
                    "risk_flags": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "different_subject",
                                "different_deadline",
                                "different_resolution_source",
                                "conditional_or_fallback_resolution",
                                "non_binary_or_non_yes_no",
                                "ambiguous_wording",
                                "insufficient_information",
                                "possible_subject_mismatch",
                            ],
                        },
                    },
                    "reason": {"type": "string"},
                },
                "required": [
                    "polymarket_market_id",
                    "kalshi_ticker",
                    "verified_same_binary_event",
                    "trade_allowed",
                    "confidence",
                    "risk_flags",
                    "reason",
                ],
            },
        }
    },
    "required": ["verifications"],
}


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, HTTPError):
        return exc.code in {408, 409, 425, 429, 500, 502, 503, 504}
    if isinstance(exc, (URLError, TimeoutError, ConnectionError, OSError)):
        return True
    return False
