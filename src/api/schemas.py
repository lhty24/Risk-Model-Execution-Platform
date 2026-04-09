"""Pydantic schemas for the Risk Model Execution Platform API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.db.models import GovernanceStatus, ModelType


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


# --- Model Registry schemas ---


class CreateModelRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    model_type: ModelType
    owner: str | None = None


class ModelVersionResponse(BaseModel):
    id: uuid.UUID
    version_number: int
    governance_status: GovernanceStatus
    artifact_hash: str
    input_schema: dict | None = None
    output_schema: dict | None = None
    created_at: datetime
    status_changed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ModelResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    model_type: ModelType
    owner: str | None = None
    created_at: datetime
    updated_at: datetime
    versions: list[ModelVersionResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ModelSummaryResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    model_type: ModelType
    owner: str | None = None
    created_at: datetime
    updated_at: datetime
    version_count: int = 0

    model_config = ConfigDict(from_attributes=True)
