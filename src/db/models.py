"""SQLAlchemy declarative models for the MEX Risk Model Execution Platform."""

import enum
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# --- Enums ---


class ModelType(str, enum.Enum):
    historical_var = "historical_var"
    bond_pricer = "bond_pricer"
    custom = "custom"


class GovernanceStatus(str, enum.Enum):
    development = "development"
    production = "production"
    deprecated = "deprecated"


class SnapshotType(str, enum.Enum):
    equity_prices = "equity_prices"
    yield_curve = "yield_curve"


class TradeType(str, enum.Enum):
    equity_position = "equity_position"
    bond_position = "bond_position"


class RunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class ResultType(str, enum.Enum):
    per_trade = "per_trade"
    aggregate = "aggregate"


# --- Models ---


class Model(Base):
    __tablename__ = "models"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_type: Mapped[ModelType] = mapped_column(Enum(ModelType), nullable=False)
    owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(tz=UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(tz=UTC), onupdate=lambda: datetime.now(tz=UTC)
    )

    versions: Mapped[list["ModelVersion"]] = relationship(back_populates="model")


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("models.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    governance_status: Mapped[GovernanceStatus] = mapped_column(
        Enum(GovernanceStatus), nullable=False, default=GovernanceStatus.development
    )
    artifact_path: Mapped[str] = mapped_column(String(512), nullable=False)
    artifact_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(tz=UTC))
    status_changed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    model: Mapped["Model"] = relationship(back_populates="versions")
    runs: Mapped[list["Run"]] = relationship(back_populates="model_version")


class MarketDataSnapshot(Base):
    __tablename__ = "market_data_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    snapshot_type: Mapped[SnapshotType] = mapped_column(Enum(SnapshotType), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_path: Mapped[str] = mapped_column(String(512), nullable=False)
    data_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(tz=UTC))
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)

    runs: Mapped[list["Run"]] = relationship(back_populates="market_data_snapshot")


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(tz=UTC))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    positions: Mapped[list["PortfolioPosition"]] = relationship(back_populates="portfolio")
    runs: Mapped[list["Run"]] = relationship(back_populates="portfolio")


class PortfolioPosition(Base):
    __tablename__ = "portfolio_positions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portfolios.id"), nullable=False
    )
    trade_type: Mapped[TradeType] = mapped_column(Enum(TradeType), nullable=False)
    instrument_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(tz=UTC))

    portfolio: Mapped["Portfolio"] = relationship(back_populates="positions")
    results: Mapped[list["RunResult"]] = relationship(back_populates="position")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("model_versions.id"), nullable=False
    )
    market_data_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("market_data_snapshots.id"), nullable=False
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portfolios.id"), nullable=False
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    run_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus), nullable=False, default=RunStatus.pending
    )
    is_official: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    submitted_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(tz=UTC))
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    model_version: Mapped["ModelVersion"] = relationship(back_populates="runs")
    market_data_snapshot: Mapped["MarketDataSnapshot"] = relationship(back_populates="runs")
    portfolio: Mapped["Portfolio"] = relationship(back_populates="runs")
    results: Mapped[list["RunResult"]] = relationship(back_populates="run")


class RunResult(Base):
    __tablename__ = "run_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id"), nullable=False)
    result_type: Mapped[ResultType] = mapped_column(Enum(ResultType), nullable=False)
    position_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("portfolio_positions.id"), nullable=True
    )
    result_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(tz=UTC))

    run: Mapped["Run"] = relationship(back_populates="results")
    position: Mapped["PortfolioPosition | None"] = relationship(back_populates="results")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    actor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(tz=UTC))
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
