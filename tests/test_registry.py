"""Tests for Model Registry — service layer and API endpoints."""

import hashlib
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.api.main import app
from src.db.config import get_session
from src.db.models import Base, ModelType
from src.registry import service as registry

SAMPLE_ARTIFACT = b"# sample risk model\nclass MyModel:\n    pass\n"


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
def sample_model(session):
    """A pre-created model for tests that need one."""
    return registry.create_model(
        session, name="Test VaR", model_type=ModelType.historical_var, owner="tester"
    )


@pytest.fixture()
def client(engine):
    """TestClient with DB session overridden to use in-memory SQLite."""

    def _override_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _override_session
    yield TestClient(app)
    app.dependency_overrides.clear()


# --- Service-level tests ---


class TestCreateModel:
    def test_creates_model_with_fields(self, session):
        model = registry.create_model(
            session,
            name="My VaR",
            description="test",
            model_type=ModelType.historical_var,
            owner="alice",
        )
        assert model.name == "My VaR"
        assert model.description == "test"
        assert model.model_type == ModelType.historical_var
        assert model.owner == "alice"
        assert model.id is not None

    def test_optional_fields_default_to_none(self, session):
        model = registry.create_model(session, name="Minimal", model_type=ModelType.custom)
        assert model.description is None
        assert model.owner is None


class TestGetModel:
    def test_returns_model_with_versions(self, session, sample_model, tmp_path):
        registry.create_version(
            session,
            model_id=sample_model.id,
            artifact_bytes=SAMPLE_ARTIFACT,
            filename="model.py",
            artifact_dir=tmp_path,
        )
        result = registry.get_model(session, sample_model.id)
        assert result is not None
        assert result.name == "Test VaR"
        assert len(result.versions) == 1

    def test_returns_none_for_missing(self, session):
        assert registry.get_model(session, uuid.uuid4()) is None


class TestListModels:
    def test_lists_all(self, session):
        registry.create_model(session, name="A", model_type=ModelType.historical_var)
        registry.create_model(session, name="B", model_type=ModelType.bond_pricer)
        assert len(registry.list_models(session)) == 2

    def test_filters_by_type(self, session):
        registry.create_model(session, name="A", model_type=ModelType.historical_var)
        registry.create_model(session, name="B", model_type=ModelType.bond_pricer)
        result = registry.list_models(session, model_type=ModelType.bond_pricer)
        assert len(result) == 1
        assert result[0].name == "B"


class TestCreateVersion:
    def test_creates_version_with_hash(self, session, sample_model, tmp_path):
        version = registry.create_version(
            session,
            model_id=sample_model.id,
            artifact_bytes=SAMPLE_ARTIFACT,
            filename="model.py",
            artifact_dir=tmp_path,
        )
        expected_hash = hashlib.sha256(SAMPLE_ARTIFACT).hexdigest()
        assert version.version_number == 1
        assert version.artifact_hash == expected_hash
        assert version.governance_status.value == "development"

    def test_auto_increments_version(self, session, sample_model, tmp_path):
        registry.create_version(
            session,
            model_id=sample_model.id,
            artifact_bytes=b"v1",
            filename="model.py",
            artifact_dir=tmp_path,
        )
        v2 = registry.create_version(
            session,
            model_id=sample_model.id,
            artifact_bytes=b"v2",
            filename="model.py",
            artifact_dir=tmp_path,
        )
        assert v2.version_number == 2

    def test_writes_artifact_to_disk(self, session, sample_model, tmp_path):
        registry.create_version(
            session,
            model_id=sample_model.id,
            artifact_bytes=SAMPLE_ARTIFACT,
            filename="model.py",
            artifact_dir=tmp_path,
        )
        path = tmp_path / str(sample_model.id) / "1" / "model.py"
        assert path.exists()
        assert path.read_bytes() == SAMPLE_ARTIFACT

    def test_raises_for_missing_model(self, session, tmp_path):
        with pytest.raises(LookupError):
            registry.create_version(
                session,
                model_id=uuid.uuid4(),
                artifact_bytes=b"x",
                filename="model.py",
                artifact_dir=tmp_path,
            )


class TestGetVersion:
    def test_returns_version(self, session, sample_model, tmp_path):
        version = registry.create_version(
            session,
            model_id=sample_model.id,
            artifact_bytes=SAMPLE_ARTIFACT,
            filename="model.py",
            artifact_dir=tmp_path,
        )
        result = registry.get_version(
            session, model_id=sample_model.id, version_id=version.id
        )
        assert result is not None
        assert result.version_number == 1

    def test_returns_none_for_wrong_model(self, session, sample_model, tmp_path):
        version = registry.create_version(
            session,
            model_id=sample_model.id,
            artifact_bytes=SAMPLE_ARTIFACT,
            filename="model.py",
            artifact_dir=tmp_path,
        )
        assert (
            registry.get_version(session, model_id=uuid.uuid4(), version_id=version.id)
            is None
        )


# --- API-level tests ---


class TestModelAPI:
    def test_create_model(self, client):
        resp = client.post(
            "/models",
            json={"name": "API VaR", "model_type": "historical_var", "owner": "bob"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "API VaR"
        assert data["model_type"] == "historical_var"
        assert "id" in data

    def test_list_models(self, client):
        client.post("/models", json={"name": "A", "model_type": "historical_var"})
        client.post("/models", json={"name": "B", "model_type": "bond_pricer"})
        resp = client.get("/models")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_models_filter(self, client):
        client.post("/models", json={"name": "A", "model_type": "historical_var"})
        client.post("/models", json={"name": "B", "model_type": "bond_pricer"})
        resp = client.get("/models", params={"model_type": "bond_pricer"})
        assert len(resp.json()) == 1

    def test_get_model(self, client):
        create_resp = client.post(
            "/models", json={"name": "Get Me", "model_type": "custom"}
        )
        model_id = create_resp.json()["id"]
        resp = client.get(f"/models/{model_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get Me"

    def test_get_model_404(self, client):
        resp = client.get(f"/models/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestVersionAPI:
    def test_upload_version(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr("src.registry.service.ARTIFACT_DIR", tmp_path)
        create_resp = client.post(
            "/models", json={"name": "Versioned", "model_type": "historical_var"}
        )
        model_id = create_resp.json()["id"]
        resp = client.post(
            f"/models/{model_id}/versions",
            files={"file": ("model.py", SAMPLE_ARTIFACT)},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["version_number"] == 1
        assert data["artifact_hash"] == hashlib.sha256(SAMPLE_ARTIFACT).hexdigest()

    def test_get_version(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr("src.registry.service.ARTIFACT_DIR", tmp_path)
        create_resp = client.post(
            "/models", json={"name": "V", "model_type": "custom"}
        )
        model_id = create_resp.json()["id"]
        ver_resp = client.post(
            f"/models/{model_id}/versions",
            files={"file": ("model.py", SAMPLE_ARTIFACT)},
        )
        version_id = ver_resp.json()["id"]
        resp = client.get(f"/models/{model_id}/versions/{version_id}")
        assert resp.status_code == 200
        assert resp.json()["version_number"] == 1

    def test_upload_version_404(self, client):
        resp = client.post(
            f"/models/{uuid.uuid4()}/versions",
            files={"file": ("model.py", b"x")},
        )
        assert resp.status_code == 404

    def test_get_version_404(self, client):
        resp = client.get(f"/models/{uuid.uuid4()}/versions/{uuid.uuid4()}")
        assert resp.status_code == 404
