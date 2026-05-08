import json
import os
import time
from typing import Callable, Iterable, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from poly_strategy.rule_discovery import MarketText, RelationCandidate, market_texts_to_prompt_rows


DEFAULT_BASE_URL = "https://api.openai.com/v1"


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
        self._transport = transport or self._post_responses

    def build_payload(self, markets: Iterable[MarketText]) -> dict:
        market_rows = market_texts_to_prompt_rows(list(markets))
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": _SYSTEM_PROMPT,
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": json.dumps({"markets": market_rows}, ensure_ascii=True, sort_keys=True),
                        }
                    ],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "polymarket_relation_discovery",
                    "strict": True,
                    "schema": _RESPONSE_SCHEMA,
                }
            },
        }
        if self.max_output_tokens is not None:
            payload["max_output_tokens"] = self.max_output_tokens
        if self.reasoning_effort:
            payload["reasoning"] = {"effort": self.reasoning_effort}
        if self.verbosity:
            payload.setdefault("text", {})["verbosity"] = self.verbosity
        return payload

    def discover_relations(self, markets: Iterable[MarketText]) -> List[RelationCandidate]:
        payload = self.build_payload(list(markets))
        response = self._call_with_retries(payload)
        content = _extract_output_text(response)
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise OpenAIResponseError("OpenAI response was not valid JSON") from exc
        relations = parsed.get("relations")
        if not isinstance(relations, list):
            raise OpenAIResponseError("OpenAI response is missing relations")
        return [_candidate_from_row(row) for row in relations if isinstance(row, dict)]

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
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

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


def _responses_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/responses"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/responses"
    return f"{normalized}/v1/responses"


def _extract_output_text(response: dict) -> str:
    output_text = response.get("output_text")
    if isinstance(output_text, str) and output_text:
        return output_text

    output = response.get("output")
    if not isinstance(output, list):
        raise OpenAIResponseError("OpenAI response is missing output")

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
    raise OpenAIResponseError("OpenAI response is missing output text")


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


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, HTTPError):
        return exc.code in {408, 409, 425, 429, 500, 502, 503, 504}
    if isinstance(exc, (URLError, TimeoutError, ConnectionError, OSError)):
        return True
    return False
