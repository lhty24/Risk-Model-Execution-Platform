"""Tests for Market Data Service — service layer and API endpoints."""

import hashlib
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.api.main import app
from src.db.config import get_session
from src.db.models import Base, SnapshotType
from src.market_data import service as market_data

SAMPLE_CSV = b"date,ticker,close\n2024-04-01,AAPL,170.00\n2024-04-01,MSFT,380.00\n2024-04-02,AAPL,171.23\n2024-04-02,MSFT,381.50\n"

MALFORMED_CSV = b"bad,header,columns\n1,2,3\n"


# --- Fixtures ---


@pytest.fixture()
def engine():
    """In-memory SQLite engine shared across threads via StaticPool."""
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session(engine):
    """SQLite session for service-level tests."""
    with Session(engine) as s:
        yield s


@pytest.fixture()
def client(engine):
    """TestClient with DB session overridden to use in-memory SQLite."""

    def _override_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _override_session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def sample_snapshot(session, tmp_path):
    """A pre-created equity_prices snapshot for tests that need one."""
    return market_data.upload_snapshot(
        session,
        snapshot_type=SnapshotType.equity_prices,
        as_of_date=date(2024, 4, 1),
        file_bytes=SAMPLE_CSV,
        filename="prices.csv",
        description="Test snapshot",
        snapshot_dir=tmp_path,
    )


# --- Service-level tests ---


class TestUploadSnapshot:
    def test_creates_snapshot_with_correct_hash(self, session, tmp_path):
        snapshot = market_data.upload_snapshot(
            session,
            snapshot_type=SnapshotType.equity_prices,
            as_of_date=date(2024, 4, 1),
            file_bytes=SAMPLE_CSV,
            filename="prices.csv",
            snapshot_dir=tmp_path,
        )
        assert snapshot.data_hash == hashlib.sha256(SAMPLE_CSV).hexdigest()
        assert snapshot.snapshot_type == SnapshotType.equity_prices
        assert snapshot.as_of_date == date(2024, 4, 1)
        assert snapshot.id is not None

    def test_stores_file_to_disk(self, session, tmp_path):
        snapshot = market_data.upload_snapshot(
            session,
            snapshot_type=SnapshotType.equity_prices,
            as_of_date=date(2024, 4, 1),
            file_bytes=SAMPLE_CSV,
            filename="prices.csv",
            snapshot_dir=tmp_path,
        )
        from pathlib import Path

        assert Path(snapshot.data_path).exists()
        assert Path(snapshot.data_path).read_bytes() == SAMPLE_CSV

    def test_extracts_metadata(self, session, tmp_path):
        snapshot = market_data.upload_snapshot(
            session,
            snapshot_type=SnapshotType.equity_prices,
            as_of_date=date(2024, 4, 1),
            file_bytes=SAMPLE_CSV,
            filename="prices.csv",
            snapshot_dir=tmp_path,
        )
        assert snapshot.metadata_ is not None
        assert snapshot.metadata_["tickers"] == ["AAPL", "MSFT"]
        assert snapshot.metadata_["row_count"] == 4

    def test_raises_for_malformed_csv(self, session, tmp_path):
        with pytest.raises(ValueError, match="CSV must contain columns"):
            market_data.upload_snapshot(
                session,
                snapshot_type=SnapshotType.equity_prices,
                as_of_date=date(2024, 4, 1),
                file_bytes=MALFORMED_CSV,
                filename="bad.csv",
                snapshot_dir=tmp_path,
            )

    def test_raises_for_empty_csv(self, session, tmp_path):
        empty = b"date,ticker,close\n"
        with pytest.raises(ValueError, match="no data rows"):
            market_data.upload_snapshot(
                session,
                snapshot_type=SnapshotType.equity_prices,
                as_of_date=date(2024, 4, 1),
                file_bytes=empty,
                filename="empty.csv",
                snapshot_dir=tmp_path,
            )

    def test_raises_for_yield_curve(self, session, tmp_path):
        with pytest.raises(ValueError, match="yield_curve"):
            market_data.upload_snapshot(
                session,
                snapshot_type=SnapshotType.yield_curve,
                as_of_date=date(2024, 4, 1),
                file_bytes=b"{}",
                filename="curve.json",
                snapshot_dir=tmp_path,
            )


class TestGetSnapshot:
    def test_returns_snapshot_by_id(self, session, sample_snapshot):
        result = market_data.get_snapshot(session, sample_snapshot.id)
        assert result is not None
        assert result.id == sample_snapshot.id

    def test_returns_none_for_missing(self, session):
        assert market_data.get_snapshot(session, uuid.uuid4()) is None


class TestListSnapshots:
    def test_lists_all(self, session, tmp_path):
        market_data.upload_snapshot(
            session,
            snapshot_type=SnapshotType.equity_prices,
            as_of_date=date(2024, 4, 1),
            file_bytes=SAMPLE_CSV,
            filename="a.csv",
            snapshot_dir=tmp_path,
        )
        market_data.upload_snapshot(
            session,
            snapshot_type=SnapshotType.equity_prices,
            as_of_date=date(2024, 4, 2),
            file_bytes=SAMPLE_CSV,
            filename="b.csv",
            snapshot_dir=tmp_path,
        )
        assert len(market_data.list_snapshots(session)) == 2

    def test_filters_by_type(self, session, sample_snapshot):
        result = market_data.list_snapshots(
            session, snapshot_type=SnapshotType.equity_prices
        )
        assert len(result) == 1

        result = market_data.list_snapshots(
            session, snapshot_type=SnapshotType.yield_curve
        )
        assert len(result) == 0

    def test_filters_by_date(self, session, sample_snapshot):
        result = market_data.list_snapshots(session, as_of_date=date(2024, 4, 1))
        assert len(result) == 1

        result = market_data.list_snapshots(session, as_of_date=date(2099, 1, 1))
        assert len(result) == 0

    def test_filters_by_type_and_date(self, session, sample_snapshot):
        result = market_data.list_snapshots(
            session,
            snapshot_type=SnapshotType.equity_prices,
            as_of_date=date(2024, 4, 1),
        )
        assert len(result) == 1


class TestResolve:
    def test_returns_exact_match(self, session, sample_snapshot):
        result = market_data.resolve(
            session,
            snapshot_type=SnapshotType.equity_prices,
            as_of_date=date(2024, 4, 1),
        )
        assert result.id == sample_snapshot.id

    def test_raises_when_no_match(self, session):
        with pytest.raises(LookupError, match="No equity_prices snapshot"):
            market_data.resolve(
                session,
                snapshot_type=SnapshotType.equity_prices,
                as_of_date=date(2099, 1, 1),
            )


class TestLoadSnapshotData:
    def test_parses_csv_to_dict(self, session, sample_snapshot):
        data = market_data.load_snapshot_data(sample_snapshot)
        assert "prices" in data
        assert sorted(data["prices"].keys()) == ["AAPL", "MSFT"]
        aapl = data["prices"]["AAPL"]
        assert len(aapl) == 2
        assert aapl[0] == {"date": "2024-04-01", "close": 170.0}
        assert aapl[1] == {"date": "2024-04-02", "close": 171.23}


# --- API-level tests ---


class TestSnapshotAPI:
    def test_upload_snapshot(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr("src.market_data.service.SNAPSHOT_DIR", tmp_path)
        resp = client.post(
            "/market-data/snapshots",
            data={"snapshot_type": "equity_prices", "as_of_date": "2024-04-01"},
            files={"file": ("prices.csv", SAMPLE_CSV)},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["snapshot_type"] == "equity_prices"
        assert data["data_hash"] == hashlib.sha256(SAMPLE_CSV).hexdigest()

    def test_upload_bad_csv_returns_400(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr("src.market_data.service.SNAPSHOT_DIR", tmp_path)
        resp = client.post(
            "/market-data/snapshots",
            data={"snapshot_type": "equity_prices", "as_of_date": "2024-04-01"},
            files={"file": ("bad.csv", MALFORMED_CSV)},
        )
        assert resp.status_code == 400

    def test_list_snapshots(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr("src.market_data.service.SNAPSHOT_DIR", tmp_path)
        client.post(
            "/market-data/snapshots",
            data={"snapshot_type": "equity_prices", "as_of_date": "2024-04-01"},
            files={"file": ("a.csv", SAMPLE_CSV)},
        )
        resp = client.get("/market-data/snapshots")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_list_snapshots_filtered(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr("src.market_data.service.SNAPSHOT_DIR", tmp_path)
        client.post(
            "/market-data/snapshots",
            data={"snapshot_type": "equity_prices", "as_of_date": "2024-04-01"},
            files={"file": ("a.csv", SAMPLE_CSV)},
        )
        resp = client.get(
            "/market-data/snapshots",
            params={"snapshot_type": "equity_prices", "as_of_date": "2024-04-01"},
        )
        assert len(resp.json()) == 1

        resp = client.get(
            "/market-data/snapshots", params={"as_of_date": "2099-01-01"}
        )
        assert len(resp.json()) == 0

    def test_get_snapshot_detail(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr("src.market_data.service.SNAPSHOT_DIR", tmp_path)
        create_resp = client.post(
            "/market-data/snapshots",
            data={
                "snapshot_type": "equity_prices",
                "as_of_date": "2024-04-01",
                "description": "Test",
            },
            files={"file": ("prices.csv", SAMPLE_CSV)},
        )
        snapshot_id = create_resp.json()["id"]
        resp = client.get(f"/market-data/snapshots/{snapshot_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "AAPL" in data["data"]["prices"]
        assert data["description"] == "Test"

    def test_get_snapshot_404(self, client):
        resp = client.get(f"/market-data/snapshots/{uuid.uuid4()}")
        assert resp.status_code == 404
