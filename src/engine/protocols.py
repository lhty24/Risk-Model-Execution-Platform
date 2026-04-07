"""Core types and protocols for the Risk Model Execution Platform.

Defines the RiskModel protocol that all model implementations must conform to,
along with the data types used for model inputs, outputs, and configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol


@dataclass
class ModelInfo:
    """Metadata returned by a model's model_info() method."""

    name: str
    version: str
    model_type: str  # e.g. "historical_var", "bond_pricer"
    required_market_data: list[str]  # e.g. ["equity_prices"]
    accepted_trade_types: list[str]  # e.g. ["equity_position"]
    config_schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Result of model input validation."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)


@dataclass
class MarketData:
    """Container for market data passed to models."""

    snapshot_type: str  # "equity_prices" or "yield_curve"
    as_of_date: date
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Trade:
    """A single trade/position in a portfolio."""

    trade_type: str  # "equity_position" or "bond_position"
    instrument_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunConfig:
    """Configuration parameters for a model run."""

    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class TradeResult:
    """Result for a single trade from a model run."""

    trade: Trade
    result_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunResult:
    """Complete result of a model execution."""

    success: bool
    trade_results: list[TradeResult] = field(default_factory=list)
    aggregate: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class RiskModel(Protocol):
    """Protocol that all risk models must implement.

    Models are loaded as Python modules and must provide:
    - model_info(): self-description for compatibility checks
    - validate_inputs(): fail-fast validation before execution
    - execute(): the actual computation
    """

    def model_info(self) -> ModelInfo: ...

    def validate_inputs(
        self, market_data: MarketData, trades: list[Trade]
    ) -> ValidationResult: ...

    def execute(
        self, market_data: MarketData, trades: list[Trade], config: RunConfig
    ) -> RunResult: ...
