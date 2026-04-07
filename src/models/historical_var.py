"""Historical VaR (Value at Risk) model implementation.

Estimates the worst expected loss on a portfolio over a given holding period
at a given confidence level, using historical price data. Outputs VaR,
Expected Shortfall (CVaR), and return distribution statistics.

Implements the RiskModel protocol defined in src/engine/protocols.py.
"""

from __future__ import annotations

import math

import numpy as np

from src.engine.protocols import (
    MarketData,
    ModelInfo,
    RunConfig,
    RunResult,
    Trade,
    TradeResult,
    ValidationResult,
)

_DEFAULT_CONFIDENCE = 0.99
_DEFAULT_HOLDING_PERIOD = 1
_DEFAULT_LOOKBACK = 252


class HistoricalVarModel:
    """Historical VaR model using equal-weighted historical returns."""

    def model_info(self) -> ModelInfo:
        return ModelInfo(
            name="historical_var",
            version="1.0.0",
            model_type="historical_var",
            required_market_data=["equity_prices"],
            accepted_trade_types=["equity_position"],
            config_schema={
                "confidence_level": {
                    "type": "float",
                    "default": _DEFAULT_CONFIDENCE,
                    "description": "VaR confidence level",
                },
                "holding_period_days": {
                    "type": "int",
                    "default": _DEFAULT_HOLDING_PERIOD,
                    "description": "Holding period in days",
                },
                "lookback_window": {
                    "type": "int",
                    "default": _DEFAULT_LOOKBACK,
                    "description": "Number of historical days to use",
                },
            },
        )

    def validate_inputs(
        self, market_data: MarketData, trades: list[Trade]
    ) -> ValidationResult:
        errors: list[str] = []

        # 1. Snapshot type
        if market_data.snapshot_type != "equity_prices":
            errors.append(
                f"Expected snapshot_type 'equity_prices', "
                f"got '{market_data.snapshot_type}'"
            )

        # 2. Price data structure
        prices = market_data.data.get("prices")
        if not isinstance(prices, dict):
            errors.append("market_data.data must contain a 'prices' dict")
            return ValidationResult(is_valid=False, errors=errors)

        # 3. Trade completeness
        tickers: list[str] = []
        for i, trade in enumerate(trades):
            if trade.trade_type != "equity_position":
                errors.append(
                    f"Trade {i}: expected trade_type 'equity_position', "
                    f"got '{trade.trade_type}'"
                )
            ticker = trade.instrument_data.get("ticker")
            quantity = trade.instrument_data.get("quantity")
            if not isinstance(ticker, str) or not ticker:
                errors.append(f"Trade {i}: missing or invalid 'ticker'")
            else:
                tickers.append(ticker)
            if quantity is None or quantity == 0:
                errors.append(f"Trade {i}: missing or zero 'quantity'")

        # 4. Ticker coverage
        missing = [t for t in tickers if t not in prices]
        if missing:
            errors.append(f"No price data for tickers: {', '.join(missing)}")

        # 5. Sufficient history
        for ticker in tickers:
            series = prices.get(ticker, [])
            if isinstance(series, list) and len(series) < 2:
                errors.append(
                    f"Ticker '{ticker}': need at least 2 price entries, "
                    f"got {len(series)}"
                )

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def execute(
        self, market_data: MarketData, trades: list[Trade], config: RunConfig
    ) -> RunResult:
        try:
            return self._execute(market_data, trades, config)
        except Exception as exc:
            return RunResult(success=False, errors=[str(exc)])

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _execute(
        self, market_data: MarketData, trades: list[Trade], config: RunConfig
    ) -> RunResult:
        confidence = config.parameters.get("confidence_level", _DEFAULT_CONFIDENCE)
        holding_days = config.parameters.get("holding_period_days", _DEFAULT_HOLDING_PERIOD)
        lookback = config.parameters.get("lookback_window", _DEFAULT_LOOKBACK)

        prices_dict = market_data.data["prices"]

        # --- Step 1: extract & align price series ---
        tickers = [t.instrument_data["ticker"] for t in trades]
        quantities = [t.instrument_data["quantity"] for t in trades]

        # Build date→close maps per ticker, trim to lookback+1
        ticker_date_close: dict[str, dict[str, float]] = {}
        for ticker in tickers:
            records = prices_dict[ticker]
            trimmed = records[-(lookback + 1) :]
            ticker_date_close[ticker] = {r["date"]: r["close"] for r in trimmed}

        # Intersect dates across all tickers, sorted ascending
        common_dates = sorted(
            set.intersection(*(set(dc.keys()) for dc in ticker_date_close.values()))
        )

        # Build aligned price matrix: (num_tickers, num_dates)
        price_matrix = np.array(
            [[ticker_date_close[tk][d] for d in common_dates] for tk in tickers]
        )

        # --- Step 2: daily log returns ---
        log_returns = np.diff(np.log(price_matrix), axis=1)  # (num_tickers, num_returns)

        # --- Step 3: position weights ---
        latest_prices = price_matrix[:, -1]
        qty_array = np.array(quantities, dtype=float)
        position_values = qty_array * latest_prices
        portfolio_value = float(np.sum(np.abs(position_values)))
        weights = position_values / portfolio_value

        # --- Step 4: portfolio daily returns ---
        portfolio_returns = log_returns.T @ weights  # (num_returns,)

        # --- Step 5: VaR ---
        percentile = (1.0 - confidence) * 100.0
        var_threshold = float(np.percentile(portfolio_returns, percentile))
        var_relative = -var_threshold * math.sqrt(holding_days)
        var_absolute = var_relative * portfolio_value

        # --- Step 6: Expected Shortfall (CVaR) ---
        tail = portfolio_returns[portfolio_returns <= var_threshold]
        cvar_relative = -float(np.mean(tail)) * math.sqrt(holding_days)
        cvar_absolute = cvar_relative * portfolio_value

        # --- Step 7: return statistics ---
        mean = float(np.mean(portfolio_returns))
        std = float(np.std(portfolio_returns, ddof=1))
        n = len(portfolio_returns)
        skew = (
            float((n / ((n - 1) * (n - 2))) * np.sum(((portfolio_returns - mean) / std) ** 3))
            if n > 2 and std > 0
            else 0.0
        )
        excess_kurtosis = (
            float(
                (n * (n + 1))
                / ((n - 1) * (n - 2) * (n - 3))
                * np.sum(((portfolio_returns - mean) / std) ** 4)
                - 3 * (n - 1) ** 2 / ((n - 2) * (n - 3))
            )
            if n > 3 and std > 0
            else 0.0
        )

        return_statistics = {
            "mean": mean,
            "std": std,
            "skew": skew,
            "kurtosis": excess_kurtosis,
        }

        # --- Step 8: per-trade results ---
        trade_results = []
        for i, trade in enumerate(trades):
            trade_results.append(
                TradeResult(
                    trade=trade,
                    result_data={
                        "ticker": tickers[i],
                        "quantity": quantities[i],
                        "latest_price": float(latest_prices[i]),
                        "position_value": float(position_values[i]),
                        "weight": float(weights[i]),
                    },
                )
            )

        # --- Step 9: aggregate result ---
        return RunResult(
            success=True,
            trade_results=trade_results,
            aggregate={
                "portfolio_value": portfolio_value,
                "var_absolute": var_absolute,
                "var_relative": var_relative,
                "expected_shortfall": cvar_absolute,
                "confidence_level": confidence,
                "holding_period_days": holding_days,
                "lookback_window": len(portfolio_returns),
                "return_statistics": return_statistics,
            },
        )
