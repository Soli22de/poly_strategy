import math
import os
from dataclasses import dataclass
from typing import List, Optional

from poly_strategy.models import Opportunity
from poly_strategy.paper import PaperTrade, opportunity_key


DEFAULT_CLOB_HOST = "https://clob.polymarket.com"
DEFAULT_CHAIN_ID = 137


class ExecutionConfigError(RuntimeError):
    pass


class ExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExecutionOrder:
    venue: str
    market_id: str
    token: str
    token_id: str
    side: str
    price: float
    size: float
    order_type: str
    tick_size: str
    neg_risk: bool


@dataclass(frozen=True)
class ExecutionPlan:
    opportunity_key: str
    opportunity_kind: str
    ts: Optional[str]
    dry_run: bool
    orders: List[ExecutionOrder]


def build_execution_plan(
    trade: PaperTrade,
    slippage_bps: float = 50.0,
    tick_size: str = "0.01",
    neg_risk: bool = False,
    order_type: str = "FOK",
    dry_run: bool = True,
) -> ExecutionPlan:
    if trade.quantity <= 0:
        raise ExecutionConfigError("trade quantity must be positive")
    if slippage_bps < 0:
        raise ExecutionConfigError("slippage_bps must be non-negative")

    orders = []
    for leg in trade.opportunity.legs:
        if leg.side.lower() != "buy":
            raise ExecutionConfigError("only buy legs are supported")
        if not leg.token_id:
            raise ExecutionConfigError(f"missing token_id for {leg.market_id} {leg.token}")
        reference_price = leg.worst_price if leg.worst_price is not None else leg.average_price
        price = _buy_limit_price(reference_price, slippage_bps, tick_size)
        orders.append(
            ExecutionOrder(
                venue=leg.venue,
                market_id=leg.market_id,
                token=leg.token,
                token_id=leg.token_id,
                side="BUY",
                price=price,
                size=trade.quantity,
                order_type=order_type.upper(),
                tick_size=tick_size,
                neg_risk=neg_risk,
            )
        )
    return ExecutionPlan(
        opportunity_key=opportunity_key(trade.opportunity),
        opportunity_kind=trade.opportunity.kind,
        ts=trade.opportunity.ts,
        dry_run=dry_run,
        orders=orders,
    )


def plan_to_row(plan: ExecutionPlan) -> dict:
    return {
        "type": "execution_plan",
        "opportunity_key": plan.opportunity_key,
        "opportunity_kind": plan.opportunity_kind,
        "ts": plan.ts,
        "dry_run": plan.dry_run,
        "orders": [
            {
                "venue": order.venue,
                "market_id": order.market_id,
                "token": order.token,
                "token_id": order.token_id,
                "side": order.side,
                "price": order.price,
                "size": order.size,
                "order_type": order.order_type,
                "tick_size": order.tick_size,
                "neg_risk": order.neg_risk,
            }
            for order in plan.orders
        ],
    }


def reconcile_execution_responses(plan_row: dict, responses: Optional[List[dict]] = None) -> dict:
    responses = list(responses or [])
    orders = list(plan_row.get("orders") or [])
    dry_run = bool(plan_row.get("dry_run", True))
    legs = []
    submitted = 0
    failed = 0
    partial = 0
    unknown = 0
    for index, order in enumerate(orders):
        response = responses[index] if index < len(responses) else None
        row = _reconcile_order_response(order, response, dry_run)
        legs.append(row)
        if row["state"] in {"submitted", "filled", "posted_unknown_fill"}:
            submitted += 1
        if row["state"] == "failed":
            failed += 1
        if row["partial_fill"]:
            partial += 1
        if row["unknown_fill"]:
            unknown += 1

    missing_responses = max(0, len(orders) - len(responses))
    needs_reconciliation = (not dry_run) and (missing_responses > 0 or failed > 0 or partial > 0 or unknown > 0)
    if dry_run:
        status = "dry_run"
    elif needs_reconciliation:
        status = "needs_reconciliation"
    else:
        status = "submitted"
    return {
        "type": "execution_reconciliation",
        "status": status,
        "dry_run": dry_run,
        "order_count": len(orders),
        "response_count": len(responses),
        "submitted_order_count": submitted,
        "failed_order_count": failed,
        "partial_fill_count": partial,
        "unknown_fill_count": unknown,
        "missing_response_count": missing_responses,
        "needs_reconciliation": needs_reconciliation,
        "partial_fill_detected": partial > 0,
        "legs": legs,
    }


class PolymarketClobExecutor:
    def __init__(
        self,
        private_key: Optional[str] = None,
        host: Optional[str] = None,
        chain_id: Optional[int] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        api_passphrase: Optional[str] = None,
    ):
        self.private_key = private_key or os.environ.get("POLYMARKET_PRIVATE_KEY")
        if not self.private_key:
            raise ExecutionConfigError("POLYMARKET_PRIVATE_KEY is required for live execution")
        self.host = host or os.environ.get("POLYMARKET_CLOB_HOST") or DEFAULT_CLOB_HOST
        self.chain_id = int(chain_id or os.environ.get("POLYMARKET_CHAIN_ID") or DEFAULT_CHAIN_ID)
        self.api_key = api_key or os.environ.get("POLYMARKET_CLOB_API_KEY")
        self.api_secret = (
            api_secret
            or os.environ.get("POLYMARKET_CLOB_API_SECRET")
            or os.environ.get("POLYMARKET_CLOB_SECRET")
        )
        self.api_passphrase = (
            api_passphrase
            or os.environ.get("POLYMARKET_CLOB_PASSPHRASE")
            or os.environ.get("POLYMARKET_CLOB_PASS_PHRASE")
        )
        self._client = None

    def post_plan(
        self,
        plan: ExecutionPlan,
        allow_live: bool = False,
        allow_nonatomic: bool = False,
    ) -> List[dict]:
        if plan.dry_run or not allow_live:
            return [{"dry_run": True, "order": _order_to_row(order)} for order in plan.orders]
        if len(plan.orders) > 1 and not allow_nonatomic:
            raise ExecutionConfigError("multi-leg live execution is non-atomic; pass allow_nonatomic=True to acknowledge")

        client, sdk = self._load_client()
        responses = []
        for order in plan.orders:
            responses.append(self._post_order(client, sdk, order))
        return responses

    def _load_client(self):
        if self._client is not None:
            return self._client

        try:
            sdk = __import__("py_clob_client_v2", fromlist=["ClobClient"])
        except ImportError as exc:
            raise ExecutionConfigError("install py-clob-client-v2 before live execution") from exc

        creds = None
        if self.api_key and self.api_secret and self.api_passphrase:
            creds = sdk.ApiCreds(
                api_key=self.api_key,
                api_secret=self.api_secret,
                api_passphrase=self.api_passphrase,
            )

        client = sdk.ClobClient(
            host=self.host,
            chain_id=self.chain_id,
            key=self.private_key,
            creds=creds,
        )
        if creds is None:
            if hasattr(client, "create_or_derive_api_key"):
                creds = client.create_or_derive_api_key()
            elif hasattr(client, "create_or_derive_api_creds"):
                creds = client.create_or_derive_api_creds()
            else:
                raise ExecutionConfigError("py-clob-client-v2 cannot derive API credentials")
            client = sdk.ClobClient(host=self.host, chain_id=self.chain_id, key=self.private_key, creds=creds)

        self._client = (client, sdk)
        return self._client

    def _post_order(self, client, sdk, order: ExecutionOrder) -> dict:
        order_args = sdk.OrderArgs(
            token_id=order.token_id,
            price=order.price,
            size=order.size,
            side=getattr(sdk.Side, order.side),
        )
        options = _partial_create_order_options(sdk, order.tick_size, order.neg_risk)
        order_type = getattr(sdk.OrderType, order.order_type)
        if hasattr(client, "create_and_post_order"):
            return client.create_and_post_order(order_args=order_args, options=options, order_type=order_type)
        raise ExecutionError("py-clob-client-v2 client is missing create_and_post_order")


def _buy_limit_price(average_price: float, slippage_bps: float, tick_size: str) -> float:
    raw_price = average_price * (1.0 + slippage_bps / 10000.0)
    tick = float(tick_size)
    if tick <= 0:
        raise ExecutionConfigError("tick_size must be positive")
    rounded = math.ceil((raw_price - 1e-12) / tick) * tick
    return min(1.0, round(rounded, _decimal_places(tick_size)))


def _decimal_places(value: str) -> int:
    if "." not in value:
        return 0
    return len(value.rstrip("0").split(".")[1])


def _partial_create_order_options(sdk, tick_size: str, neg_risk: bool):
    options_cls = sdk.PartialCreateOrderOptions
    try:
        return options_cls(tick_size=tick_size, neg_risk=neg_risk)
    except TypeError:
        return options_cls(tick_size=tick_size)


def _order_to_row(order: ExecutionOrder) -> dict:
    return {
        "venue": order.venue,
        "market_id": order.market_id,
        "token": order.token,
        "token_id": order.token_id,
        "side": order.side,
        "price": order.price,
        "size": order.size,
        "order_type": order.order_type,
        "tick_size": order.tick_size,
        "neg_risk": order.neg_risk,
    }


def _reconcile_order_response(order: dict, response: Optional[dict], dry_run: bool) -> dict:
    planned_size = _optional_float(order.get("size")) or 0.0
    filled_size = _response_filled_size(response)
    response_status = _response_status(response, dry_run)
    partial_fill = filled_size is not None and 0.0 < filled_size < planned_size
    filled = filled_size is not None and planned_size > 0 and filled_size >= planned_size
    unknown_fill = (not dry_run) and response_status in {"submitted", "posted_unknown_fill"} and filled_size is None
    return {
        "market_id": order.get("market_id"),
        "token_id": order.get("token_id"),
        "planned_size": planned_size,
        "filled_size": filled_size,
        "order_id": _response_order_id(response),
        "state": "filled" if filled else response_status,
        "partial_fill": partial_fill,
        "unknown_fill": unknown_fill,
        "raw_response": response,
    }


def _response_status(response: Optional[dict], dry_run: bool) -> str:
    if dry_run:
        return "dry_run"
    if not isinstance(response, dict):
        return "failed"
    status = str(response.get("status") or response.get("state") or "").strip().lower()
    if status in {"filled", "matched"}:
        return "filled"
    if status in {"failed", "rejected", "error", "cancelled", "canceled"}:
        return "failed"
    if status in {"open", "live", "posted", "submitted"}:
        return "submitted"
    success = response.get("success")
    if success is False:
        return "failed"
    if success is True or _response_order_id(response):
        return "posted_unknown_fill"
    return "failed"


def _response_order_id(response: Optional[dict]):
    if not isinstance(response, dict):
        return None
    for key in ["order_id", "orderID", "id", "orderId"]:
        value = response.get(key)
        if value:
            return str(value)
    return None


def _response_filled_size(response: Optional[dict]) -> Optional[float]:
    if not isinstance(response, dict):
        return None
    for key in ["filled_size", "filledSize", "matched_size", "matchedSize", "filled"]:
        parsed = _optional_float(response.get(key))
        if parsed is not None:
            return parsed
    return None


def _optional_float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
