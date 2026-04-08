"""Pydantic schemas for the Risk Model Execution Platform API."""

from __future__ import annotations

from pydantic import BaseModel, Field


# --- Request models ---


class InlinePosition(BaseModel):
    ticker: str
    quantity: float


class InlinePriceEntry(BaseModel):
    date: str
    close: float


class VarRunConfig(BaseModel):
    confidence_level: float | None = None
    holding_period_days: int | None = None
    lookback_window: int | None = None


class VarRunRequest(BaseModel):
    positions: list[InlinePosition] = Field(..., min_length=1)
    prices: dict[str, list[InlinePriceEntry]]
    config: VarRunConfig | None = None


# --- Response models ---


class TradeResultResponse(BaseModel):
    ticker: str
    quantity: float
    latest_price: float
    position_value: float
    weight: float


class ReturnStatistics(BaseModel):
    mean: float
    std: float
    skew: float
    kurtosis: float


class VarAggregateResponse(BaseModel):
    portfolio_value: float
    var_absolute: float
    var_relative: float
    expected_shortfall: float
    confidence_level: float
    holding_period_days: int
    lookback_window: int
    return_statistics: ReturnStatistics


class VarRunResponse(BaseModel):
    success: bool
    trade_results: list[TradeResultResponse] = Field(default_factory=list)
    aggregate: VarAggregateResponse | None = None
    errors: list[str] = Field(default_factory=list)
