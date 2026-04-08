"""Unit tests for HistoricalVarModel — VaR calculation against hand-computed values.

Reference dataset: 2 tickers (A, B), 6 days of prices, 10 and 20 shares.
All expected values are pre-computed and hardcoded so the tests are
independent of the implementation under test.
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np
import pytest

from src.engine.protocols import MarketData, RunConfig, Trade
from src.models.historical_var import HistoricalVarModel

# ---------------------------------------------------------------------------
# Reference dataset
# ---------------------------------------------------------------------------

REFERENCE_PRICES = {
    "A": [
        {"date": "2024-01-01", "close": 100.0},
        {"date": "2024-01-02", "close": 102.0},
        {"date": "2024-01-03", "close": 101.0},
        {"date": "2024-01-04", "close": 103.0},
        {"date": "2024-01-05", "close": 104.0},
        {"date": "2024-01-06", "close": 102.0},
    ],
    "B": [
        {"date": "2024-01-01", "close": 50.0},
        {"date": "2024-01-02", "close": 51.0},
        {"date": "2024-01-03", "close": 49.0},
        {"date": "2024-01-04", "close": 50.0},
        {"date": "2024-01-05", "close": 52.0},
        {"date": "2024-01-06", "close": 51.0},
    ],
}

# Pre-computed expected values (NumPy, verified independently)
# Log returns: r_t = ln(P_t / P_{t-1})
#   A: [ln(102/100), ln(101/102), ln(103/101), ln(104/103), ln(102/104)]
#   B: [ln(51/50),   ln(49/51),   ln(50/49),   ln(52/50),   ln(51/52)]
# Weights: pos_A = 10*102 = 1020, pos_B = 20*51 = 1020 → w = [0.5, 0.5]
# Portfolio returns: weighted sum of A and B daily log returns
EXPECTED_PORTFOLIO_VALUE = 2040.0
EXPECTED_VAR_ABSOLUTE_99 = 50.405108136670194
EXPECTED_VAR_RELATIVE_99 = 0.024708386341504997
EXPECTED_CVAR_ABSOLUTE_99 = 50.854783677844466
EXPECTED_VAR_ABSOLUTE_95 = 48.60640597197311
EXPECTED_CVAR_ABSOLUTE_95 = 50.854783677844466
EXPECTED_MEAN = 0.003960525459235864
EXPECTED_STD = 0.024009546859657258
EXPECTED_SKEW = -0.6101616732743945
EXPECTED_KURTOSIS = -3.1142249958588852


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_market_data(
    prices: dict | None = None,
    snapshot_type: str = "equity_prices",
    as_of_date: date = date(2024, 1, 6),
) -> MarketData:
    return MarketData(
        snapshot_type=snapshot_type,
        as_of_date=as_of_date,
        data={"prices": prices if prices is not None else REFERENCE_PRICES},
    )


def make_trades(positions: list[tuple[str, float]]) -> list[Trade]:
    return [
        Trade(
            trade_type="equity_position",
            instrument_data={"ticker": ticker, "quantity": qty},
        )
        for ticker, qty in positions
    ]


def make_config(**overrides) -> RunConfig:
    return RunConfig(parameters=overrides)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def model():
    return HistoricalVarModel()


@pytest.fixture(scope="module")
def reference_result(model):
    """Execute the model once on the reference dataset; reused by all math tests."""
    md = make_market_data()
    trades = make_trades([("A", 10), ("B", 20)])
    cfg = make_config()
    return model.execute(md, trades, cfg)


# ---------------------------------------------------------------------------
# TestValidateInputs
# ---------------------------------------------------------------------------

class TestValidateInputs:

    def test_valid_inputs(self, model):
        md = make_market_data()
        trades = make_trades([("A", 10), ("B", 20)])
        result = model.validate_inputs(md, trades)
        assert result.is_valid is True
        assert result.errors == []

    def test_wrong_snapshot_type(self, model):
        md = make_market_data(snapshot_type="yield_curve")
        trades = make_trades([("A", 10)])
        result = model.validate_inputs(md, trades)
        assert result.is_valid is False
        assert any("Expected snapshot_type 'equity_prices'" in e for e in result.errors)

    def test_prices_not_a_dict(self, model):
        md = MarketData(
            snapshot_type="equity_prices",
            as_of_date=date(2024, 1, 6),
            data={"prices": "not_a_dict"},
        )
        trades = make_trades([("A", 10)])
        result = model.validate_inputs(md, trades)
        assert result.is_valid is False
        assert any("'prices' dict" in e for e in result.errors)
        # Early return — only snapshot-type + prices-structure errors
        assert len(result.errors) <= 2

    def test_wrong_trade_type(self, model):
        md = make_market_data()
        trades = [Trade(trade_type="bond_position", instrument_data={"ticker": "A", "quantity": 10})]
        result = model.validate_inputs(md, trades)
        assert result.is_valid is False
        assert any("expected trade_type 'equity_position'" in e for e in result.errors)

    def test_empty_ticker(self, model):
        md = make_market_data()
        trades = [Trade(trade_type="equity_position", instrument_data={"ticker": "", "quantity": 10})]
        result = model.validate_inputs(md, trades)
        assert result.is_valid is False
        assert any("missing or invalid 'ticker'" in e for e in result.errors)

    def test_zero_quantity(self, model):
        md = make_market_data()
        trades = [Trade(trade_type="equity_position", instrument_data={"ticker": "A", "quantity": 0})]
        result = model.validate_inputs(md, trades)
        assert result.is_valid is False
        assert any("missing or zero 'quantity'" in e for e in result.errors)

    def test_missing_ticker_in_prices(self, model):
        md = make_market_data()
        trades = make_trades([("MSFT", 10)])
        result = model.validate_inputs(md, trades)
        assert result.is_valid is False
        assert any("No price data for tickers: MSFT" in e for e in result.errors)

    def test_insufficient_history(self, model):
        prices = {"A": [{"date": "2024-01-01", "close": 100.0}]}
        md = make_market_data(prices=prices)
        trades = make_trades([("A", 10)])
        result = model.validate_inputs(md, trades)
        assert result.is_valid is False
        assert any("need at least 2 price entries" in e for e in result.errors)

    def test_multiple_errors_accumulated(self, model):
        md = make_market_data()
        trades = [
            Trade(trade_type="bond_position", instrument_data={"ticker": "", "quantity": 0}),
            Trade(trade_type="equity_position", instrument_data={"ticker": "MSFT", "quantity": 5}),
        ]
        result = model.validate_inputs(md, trades)
        assert result.is_valid is False
        assert len(result.errors) > 1


# ---------------------------------------------------------------------------
# TestVarCalculation
# ---------------------------------------------------------------------------

class TestVarCalculation:

    def test_success_flag(self, reference_result):
        assert reference_result.success is True
        assert reference_result.errors == []

    def test_portfolio_value(self, reference_result):
        assert reference_result.aggregate["portfolio_value"] == pytest.approx(
            EXPECTED_PORTFOLIO_VALUE, rel=1e-9
        )

    def test_trade_results_position_values(self, reference_result):
        results_by_ticker = {
            tr.result_data["ticker"]: tr.result_data
            for tr in reference_result.trade_results
        }

        a = results_by_ticker["A"]
        assert a["latest_price"] == pytest.approx(102.0, rel=1e-9)
        assert a["position_value"] == pytest.approx(1020.0, rel=1e-9)
        assert a["weight"] == pytest.approx(0.5, rel=1e-9)

        b = results_by_ticker["B"]
        assert b["latest_price"] == pytest.approx(51.0, rel=1e-9)
        assert b["position_value"] == pytest.approx(1020.0, rel=1e-9)
        assert b["weight"] == pytest.approx(0.5, rel=1e-9)

    def test_var_absolute_and_relative(self, reference_result):
        agg = reference_result.aggregate
        assert agg["var_absolute"] == pytest.approx(EXPECTED_VAR_ABSOLUTE_99, rel=1e-6)
        assert agg["var_relative"] == pytest.approx(EXPECTED_VAR_RELATIVE_99, rel=1e-6)

    def test_expected_shortfall(self, reference_result):
        assert reference_result.aggregate["expected_shortfall"] == pytest.approx(
            EXPECTED_CVAR_ABSOLUTE_99, rel=1e-6
        )

    def test_return_statistics_mean_std(self, reference_result):
        stats = reference_result.aggregate["return_statistics"]
        assert stats["mean"] == pytest.approx(EXPECTED_MEAN, rel=1e-9)
        assert stats["std"] == pytest.approx(EXPECTED_STD, rel=1e-9)

    def test_return_statistics_skew_kurtosis(self, reference_result):
        stats = reference_result.aggregate["return_statistics"]
        assert stats["skew"] == pytest.approx(EXPECTED_SKEW, rel=1e-6)
        assert stats["kurtosis"] == pytest.approx(EXPECTED_KURTOSIS, rel=1e-6)

    def test_lookback_window_reported(self, reference_result):
        # 6 prices → 5 log returns
        assert reference_result.aggregate["lookback_window"] == 5


# ---------------------------------------------------------------------------
# TestVarEdgeCases
# ---------------------------------------------------------------------------

class TestVarEdgeCases:

    def test_confidence_95(self, model):
        md = make_market_data()
        trades = make_trades([("A", 10), ("B", 20)])
        cfg = make_config(confidence_level=0.95)
        result = model.execute(md, trades, cfg)

        assert result.success is True
        agg = result.aggregate
        assert agg["confidence_level"] == 0.95
        assert agg["var_absolute"] == pytest.approx(EXPECTED_VAR_ABSOLUTE_95, rel=1e-6)
        assert agg["expected_shortfall"] == pytest.approx(EXPECTED_CVAR_ABSOLUTE_95, rel=1e-6)
        # 95% VaR should be less than or equal to 99% VaR
        assert agg["var_absolute"] <= EXPECTED_VAR_ABSOLUTE_99 + 1e-9

    def test_multiday_holding_period(self, model):
        md = make_market_data()
        trades = make_trades([("A", 10), ("B", 20)])

        result_1d = model.execute(md, trades, make_config())
        result_10d = model.execute(md, trades, make_config(holding_period_days=10))

        assert result_10d.success is True
        # Multi-day VaR = 1-day VaR * sqrt(holding_days)
        sqrt_10 = math.sqrt(10)
        assert result_10d.aggregate["var_relative"] == pytest.approx(
            result_1d.aggregate["var_relative"] * sqrt_10, rel=1e-9
        )
        assert result_10d.aggregate["var_absolute"] == pytest.approx(
            result_1d.aggregate["var_absolute"] * sqrt_10, rel=1e-9
        )

    def test_single_position_portfolio(self, model):
        md = make_market_data()
        trades = make_trades([("A", 10)])
        result = model.execute(md, trades, make_config())

        assert result.success is True
        assert len(result.trade_results) == 1
        assert result.trade_results[0].result_data["weight"] == pytest.approx(1.0, rel=1e-9)
        assert result.aggregate["portfolio_value"] == pytest.approx(1020.0, rel=1e-9)

    def test_lookback_trims_data(self, model):
        """Default lookback is 252 but only 6 prices available → uses all 5 returns."""
        md = make_market_data()
        trades = make_trades([("A", 10), ("B", 20)])
        cfg = make_config()  # lookback defaults to 252
        result = model.execute(md, trades, cfg)

        assert result.aggregate["lookback_window"] == 5

    def test_short_lookback_config(self, model):
        """lookback_window=3 → only last 4 prices (3 returns) used."""
        md = make_market_data()
        trades = make_trades([("A", 10), ("B", 20)])
        cfg = make_config(lookback_window=3)
        result = model.execute(md, trades, cfg)

        assert result.success is True
        assert result.aggregate["lookback_window"] == 3
        # Prices trimmed to last 4: A=[103,104,102], B=[50,52,51] → 3 returns
        assert result.aggregate["var_absolute"] == pytest.approx(38.00848919991766, rel=1e-6)

    def test_execution_error_returns_failure(self, model):
        """Corrupt market_data to trigger an exception inside _execute()."""
        md = MarketData(
            snapshot_type="equity_prices",
            as_of_date=date(2024, 1, 6),
            data={"prices": {"A": "not_a_list"}},
        )
        trades = make_trades([("A", 10)])
        result = model.execute(md, trades, make_config())

        assert result.success is False
        assert len(result.errors) > 0
