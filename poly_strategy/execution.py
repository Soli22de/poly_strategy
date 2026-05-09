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
