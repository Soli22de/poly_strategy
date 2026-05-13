import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from research_simulation_utils import (  # noqa: E402
    capped_expected_daily_edge,
    maker_target_price,
    qualifying_trade_size,
    simulate_basket_fill,
)


def test_basket_fill_caps_profit_to_common_fillable_size():
    row = simulate_basket_fill(
        [
            {"asks": [(0.40, 2.0)], "fee_rate": 0.0},
            {"asks": [(0.10, 10.0)], "fee_rate": 0.0},
        ],
        requested_size=10.0,
    )

    assert row["requested_size"] == 10.0
    assert row["effective_size"] == 2.0
    assert row["max_fillable_units"] == 2.0
    assert row["total_cost"] == 1.0
    assert row["edge_dollars"] == 1.0
    assert row["edge_pct"] == 0.5


def test_basket_fill_marks_unfillable_when_any_leg_has_no_depth():
    row = simulate_basket_fill(
        [
            {"asks": [(0.40, 2.0)], "fee_rate": 0.0},
            {"asks": [], "fee_rate": 0.0},
        ],
        requested_size=10.0,
    )

    assert row["effective_size"] == 0.0
    assert row["total_cost"] == 0.0
    assert row["edge_dollars"] == 0.0
    assert row["edge_pct"] == 0.0
    assert row["is_full_size_fillable"] is False


def test_maker_target_price_never_crosses_best_ask():
    target = maker_target_price(best_bid=0.40, best_ask=0.45, markup=0.0001, tick_size=0.001)

    assert target == 0.449
    assert target < 0.45


def test_maker_target_price_rejects_spread_without_non_crossing_quote():
    target = maker_target_price(best_bid=0.4995, best_ask=0.50, markup=0.005, tick_size=0.001)

    assert target is None


def test_capped_expected_daily_edge_uses_real_trade_size_not_requested_basket():
    summary = capped_expected_daily_edge(
        [
            {"edge": 0.05, "min_leg_sell_size": 3.0},
            {"edge": 0.02, "min_leg_sell_size": 200.0},
        ],
        n_total_days=2,
        basket_size=100.0,
    )

    assert summary["expected_daily_edge_dollars"] == 1.075
    assert summary["avg_effective_basket_size"] == 51.5
    assert summary["max_effective_basket_size"] == 100.0


def test_qualifying_trade_size_counts_only_trades_at_or_below_target():
    trades = [
        {"price": 0.04, "size": 2.0},
        {"price": 0.05, "size": 3.0},
        {"price": 0.08, "size": 100.0},
    ]

    assert qualifying_trade_size(trades, target_price=0.05) == 5.0
