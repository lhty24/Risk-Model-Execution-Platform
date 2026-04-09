"""Tests for SQLAlchemy models — schema creation, inserts, and relationships."""

import uuid
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.db.models import (
    AuditLog,
    Base,
    GovernanceStatus,
    MarketDataSnapshot,
    Model,
    ModelType,
    ModelVersion,
    Portfolio,
    PortfolioPosition,
    ResultType,
    Run,
    RunResult,
    RunStatus,
    SnapshotType,
    TradeType,
)


@pytest.fixture()
def session():
    """In-memory SQLite session with all tables created."""
    engine = create_engine("sqlite://", echo=False)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_create_all_tables(session):
    """All 8 tables should be created without error."""
    table_names = set(Base.metadata.tables.keys())
    expected = {
        "models",
        "model_versions",
        "market_data_snapshots",
        "portfolios",
        "portfolio_positions",
        "runs",
        "run_results",
        "audit_log",
    }
    assert expected == table_names


def test_model_and_version_relationship(session):
    model = Model(name="Historical VaR", model_type=ModelType.historical_var)
    session.add(model)
    session.flush()

    version = ModelVersion(
        model_id=model.id,
        version_number=1,
        artifact_path="/models/var_v1.py",
        artifact_hash="abc123" * 10,
    )
    session.add(version)
    session.flush()

    assert version in model.versions
    assert version.model is model
    assert version.governance_status == GovernanceStatus.development


def test_portfolio_and_positions(session):
    portfolio = Portfolio(name="Test Equity Book")
    session.add(portfolio)
    session.flush()

    pos = PortfolioPosition(
        portfolio_id=portfolio.id,
        trade_type=TradeType.equity_position,
        instrument_data={"ticker": "AAPL", "quantity": 100},
    )
    session.add(pos)
    session.flush()

    assert pos in portfolio.positions
    assert pos.portfolio is portfolio


def test_market_data_snapshot(session):
    snap = MarketDataSnapshot(
        snapshot_type=SnapshotType.equity_prices,
        as_of_date=date(2025, 1, 15),
        data_path="/data/equity_2025-01-15.csv",
        data_hash="def456" * 10,
        metadata_={"tickers": ["AAPL", "MSFT"]},
    )
    session.add(snap)
    session.flush()

    assert snap.id is not None
    assert snap.as_of_date == date(2025, 1, 15)


def test_run_full_chain(session):
    """A run links model_version, snapshot, and portfolio — verify the full chain."""
    model = Model(name="VaR", model_type=ModelType.historical_var)
    session.add(model)
    session.flush()

    version = ModelVersion(
        model_id=model.id,
        version_number=1,
        artifact_path="/models/var.py",
        artifact_hash="a" * 64,
    )
    snap = MarketDataSnapshot(
        snapshot_type=SnapshotType.equity_prices,
        as_of_date=date(2025, 3, 1),
        data_path="/data/snap.csv",
        data_hash="b" * 64,
    )
    portfolio = Portfolio(name="Book A")
    session.add_all([version, snap, portfolio])
    session.flush()

    run = Run(
        model_version_id=version.id,
        market_data_snapshot_id=snap.id,
        portfolio_id=portfolio.id,
        as_of_date=date(2025, 3, 1),
        run_config={"confidence_level": 0.99},
    )
    session.add(run)
    session.flush()

    assert run.status == RunStatus.pending
    assert run.is_official is False
    assert run.model_version is version
    assert run.market_data_snapshot is snap
    assert run.portfolio is portfolio
    assert run in version.runs


def test_run_results(session):
    """Per-trade and aggregate results link back to a run."""
    model = Model(name="VaR", model_type=ModelType.historical_var)
    session.add(model)
    session.flush()

    version = ModelVersion(
        model_id=model.id, version_number=1,
        artifact_path="/m.py", artifact_hash="c" * 64,
    )
    snap = MarketDataSnapshot(
        snapshot_type=SnapshotType.equity_prices,
        as_of_date=date(2025, 1, 1),
        data_path="/d.csv", data_hash="d" * 64,
    )
    portfolio = Portfolio(name="Book B")
    session.add_all([version, snap, portfolio])
    session.flush()

    pos = PortfolioPosition(
        portfolio_id=portfolio.id,
        trade_type=TradeType.equity_position,
        instrument_data={"ticker": "GOOG", "quantity": 50},
    )
    session.add(pos)
    session.flush()

    run = Run(
        model_version_id=version.id,
        market_data_snapshot_id=snap.id,
        portfolio_id=portfolio.id,
        as_of_date=date(2025, 1, 1),
    )
    session.add(run)
    session.flush()

    per_trade = RunResult(
        run_id=run.id,
        result_type=ResultType.per_trade,
        position_id=pos.id,
        result_data={"pnl": -1500.0},
    )
    aggregate = RunResult(
        run_id=run.id,
        result_type=ResultType.aggregate,
        result_data={"var_absolute": 25000.0, "var_relative": 0.025},
    )
    session.add_all([per_trade, aggregate])
    session.flush()

    assert len(run.results) == 2
    assert per_trade.position is pos
    assert aggregate.position is None


def test_audit_log(session):
    entry = AuditLog(
        event_type="model_registered",
        entity_type="model",
        entity_id=uuid.uuid4(),
        actor="admin",
        detail={"name": "Historical VaR"},
    )
    session.add(entry)
    session.flush()

    assert entry.id is not None
    assert entry.timestamp is not None
