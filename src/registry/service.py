"""Model Registry service — CRUD for models and versioned artifacts."""

from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from src.db.models import Model, ModelType, ModelVersion

ARTIFACT_DIR = Path(os.environ.get("ARTIFACT_DIR", "artifacts"))


def create_model(
    session: Session,
    *,
    name: str,
    description: str | None = None,
    model_type: ModelType,
    owner: str | None = None,
) -> Model:
    """Register a new model in the registry."""
    model = Model(name=name, description=description, model_type=model_type, owner=owner)
    session.add(model)
    session.commit()
    session.refresh(model)
    return model


def get_model(session: Session, model_id: uuid.UUID) -> Model | None:
    """Fetch a model by ID with all its versions eagerly loaded."""
    stmt = (
        select(Model)
        .where(Model.id == model_id)
        .options(selectinload(Model.versions))
    )
    return session.execute(stmt).scalar_one_or_none()


def list_models(
    session: Session, *, model_type: ModelType | None = None
) -> list[Model]:
    """List models, optionally filtered by type."""
    stmt = select(Model).options(selectinload(Model.versions))
    if model_type is not None:
        stmt = stmt.where(Model.model_type == model_type)
    stmt = stmt.order_by(Model.created_at.desc())
    return list(session.execute(stmt).scalars().all())


def create_version(
    session: Session,
    *,
    model_id: uuid.UUID,
    artifact_bytes: bytes,
    filename: str,
    artifact_dir: Path | None = None,
) -> ModelVersion:
    """Upload a new version for an existing model.

    Computes SHA-256 hash, auto-increments version number, and stores
    the artifact on the local filesystem.
    """
    model = session.get(Model, model_id)
    if model is None:
        raise LookupError(f"Model {model_id} not found")

    artifact_hash = hashlib.sha256(artifact_bytes).hexdigest()

    # Auto-increment version number
    max_ver = session.execute(
        select(func.coalesce(func.max(ModelVersion.version_number), 0)).where(
            ModelVersion.model_id == model_id
        )
    ).scalar_one()
    version_number = max_ver + 1

    # Store artifact on disk
    base = artifact_dir or ARTIFACT_DIR
    dest = base / str(model_id) / str(version_number)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / filename).write_bytes(artifact_bytes)

    artifact_path = str(dest / filename)

    version = ModelVersion(
        model_id=model_id,
        version_number=version_number,
        artifact_path=artifact_path,
        artifact_hash=artifact_hash,
    )
    session.add(version)
    session.commit()
    session.refresh(version)
    return version


def get_version(
    session: Session, *, model_id: uuid.UUID, version_id: uuid.UUID
) -> ModelVersion | None:
    """Fetch a specific version, scoped to its parent model."""
    stmt = select(ModelVersion).where(
        ModelVersion.id == version_id,
        ModelVersion.model_id == model_id,
    )
    return session.execute(stmt).scalar_one_or_none()
