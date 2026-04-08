"""FastAPI application for the Risk Model Execution Platform."""

from __future__ import annotations

from datetime import date

from fastapi import FastAPI, HTTPException

from src.api.schemas import (
    TradeResultResponse,
    ReturnStatistics,
    VarAggregateResponse,
    VarRunRequest,
    VarRunResponse,
)
from src.engine.protocols import MarketData, RunConfig, Trade
from src.models.historical_var import HistoricalVarModel

app = FastAPI(title="Risk Model Execution Platform")


@app.post("/runs/var", response_model=VarRunResponse)
def run_var(request: VarRunRequest) -> VarRunResponse:
    """Execute Historical VaR on inline portfolio and price data."""

    # Convert request → protocol types
    market_data = MarketData(
        snapshot_type="equity_prices",
        as_of_date=date.today(),
        data={
            "prices": {
                ticker: [{"date": e.date, "close": e.close} for e in entries]
                for ticker, entries in request.prices.items()
            }
        },
    )

    trades = [
        Trade(
            trade_type="equity_position",
            instrument_data={"ticker": p.ticker, "quantity": p.quantity},
        )
        for p in request.positions
    ]

    config_params: dict = {}
    if request.config:
        if request.config.confidence_level is not None:
            config_params["confidence_level"] = request.config.confidence_level
        if request.config.holding_period_days is not None:
            config_params["holding_period_days"] = request.config.holding_period_days
        if request.config.lookback_window is not None:
            config_params["lookback_window"] = request.config.lookback_window
    run_config = RunConfig(parameters=config_params)

    # Validate and execute
    model = HistoricalVarModel()

    validation = model.validate_inputs(market_data, trades)
    if not validation.is_valid:
        raise HTTPException(status_code=400, detail=validation.errors)

    result = model.execute(market_data, trades, run_config)

    # Build response
    trade_results = [
        TradeResultResponse(
            ticker=tr.result_data["ticker"],
            quantity=tr.result_data["quantity"],
            latest_price=tr.result_data["latest_price"],
            position_value=tr.result_data["position_value"],
            weight=tr.result_data["weight"],
        )
        for tr in result.trade_results
    ]

    aggregate = None
    if result.success and result.aggregate:
        agg = result.aggregate
        stats = agg["return_statistics"]
        aggregate = VarAggregateResponse(
            portfolio_value=agg["portfolio_value"],
            var_absolute=agg["var_absolute"],
            var_relative=agg["var_relative"],
            expected_shortfall=agg["expected_shortfall"],
            confidence_level=agg["confidence_level"],
            holding_period_days=agg["holding_period_days"],
            lookback_window=agg["lookback_window"],
            return_statistics=ReturnStatistics(
                mean=stats["mean"],
                std=stats["std"],
                skew=stats["skew"],
                kurtosis=stats["kurtosis"],
            ),
        )

    return VarRunResponse(
        success=result.success,
        trade_results=trade_results,
        aggregate=aggregate,
        errors=result.errors,
    )
