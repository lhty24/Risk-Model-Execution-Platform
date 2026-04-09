# P1b-T3: Model Registry — Upload Model Artifact, Create Versions, List Models

## Context

The platform needs a Model Registry to manage risk model artifacts and their versions. Currently, the Historical VaR model is instantiated inline in the API endpoint. The registry introduces proper model lifecycle management: registration, versioned artifact storage with SHA-256 integrity hashing, and CRUD API endpoints. This is the foundation for the Execution Engine (P1b-T6) which will load models from the registry.

SQLAlchemy models (`Model`, `ModelVersion`) and Alembic migrations already exist from P1b-T2. The `src/registry/` package exists but is empty.

## Implementation

### 1. Pydantic Schemas — `src/api/schemas.py`

**Why:** The API endpoints need typed request/response contracts. Pydantic schemas enforce validation on incoming requests (e.g., `model_type` must be a valid enum value) and provide consistent, documented response shapes. Defining these first establishes the API contract that the service layer and endpoints will implement against.

Add to existing file:

```python
# Request
CreateModelRequest(name, description?, model_type, owner?)
# Response
ModelVersionResponse(id, version_number, governance_status, artifact_hash, input_schema?, output_schema?, created_at, status_changed_at?)
ModelResponse(id, name, description?, model_type, owner?, created_at, updated_at, versions: list[ModelVersionResponse])
ModelSummaryResponse(id, name, description?, model_type, owner?, created_at, updated_at, version_count)
```

- Reuse `ModelType` and `GovernanceStatus` enums from `src/db/models.py`
- No `CreateModelVersionRequest` body needed — metadata comes from the uploaded artifact's `model_info()` call; artifact is a file upload

### 2. Registry Service — `src/registry/service.py`

**Why:** Separating business logic from the API layer keeps endpoints thin and testable. The service layer owns all database queries, artifact storage, version auto-increment logic, and SHA-256 hashing. This makes it possible to test the core registry logic with a lightweight SQLite session (no HTTP overhead), and later reuse it from the Execution Engine (P1b-T6) or Batch Orchestrator without going through HTTP.

New file with these functions:

- **`create_model(session, name, description, model_type, owner)`** → insert `Model` row, return it
- **`get_model(session, model_id)`** → fetch `Model` with eager-loaded `versions`, raise 404 if missing
- **`list_models(session, model_type?)`** → query `models` with optional type filter, return list
- **`create_version(session, model_id, artifact_bytes, filename)`**:
  1. Verify model exists (404 if not)
  2. Compute SHA-256 of artifact bytes
  3. Auto-increment `version_number` (max existing + 1, or 1)
  4. Save artifact to `artifacts/{model_id}/{version_number}/{filename}`
  5. Insert `ModelVersion` row (governance_status=development)
  6. Return the new version
- **`get_version(session, model_id, version_id)`** → fetch specific version, verify it belongs to model_id

Artifact storage path: `artifacts/` directory (already in `.gitignore`). Use `ARTIFACT_DIR` constant, default to `artifacts/` relative to project root.

### 3. FastAPI Endpoints — `src/api/main.py`

**Why:** The REST API is the primary interface for all platform operations (per design doc Section 4). These endpoints let users register models, upload versioned artifacts, and discover available models — all prerequisite operations before a model can be executed. Adding them to the existing `main.py` keeps the single FastAPI app pattern established in Phase 1a. The endpoints are thin wrappers that delegate to the service layer.

Add to existing app, using `Depends(get_session)` for DB sessions:

| Method | Path | Handler | Notes |
|--------|------|---------|-------|
| POST | `/models` | `create_model` | JSON body → `CreateModelRequest` |
| GET | `/models` | `list_models` | Query param `model_type?` |
| GET | `/models/{model_id}` | `get_model` | Returns model + versions |
| POST | `/models/{model_id}/versions` | `create_model_version` | `UploadFile` for artifact |
| GET | `/models/{model_id}/versions/{version_id}` | `get_model_version` | Single version detail |

All return appropriate Pydantic response models. Use `HTTPException(404)` for missing resources.

### 4. Tests — `tests/test_registry.py`

**Why:** The registry is a critical platform component — models that aren't stored correctly or versioned properly would break the entire execution pipeline downstream. Service-level tests verify the core logic (hashing, auto-increment, file storage) in isolation with fast SQLite sessions. API-level tests verify the HTTP contract (status codes, response shapes, file upload handling) and catch integration issues between FastAPI, Pydantic schemas, and the service layer.

Follow existing patterns from `test_db_models.py` (SQLite session fixture) and `test_api_var.py` (TestClient):

**Service-level tests** (with SQLite session + tmp_path for artifacts):
- Create model → verify fields
- Create version → verify auto-increment, SHA-256, file written to disk
- Create multiple versions → verify version_number increments
- List models → verify filtering by type
- Get model → verify versions included
- Get non-existent model → 404

**API-level tests** (with TestClient + session override):
- POST /models → 201, verify response shape
- GET /models → list, filter by type
- GET /models/{id} → model with versions
- POST /models/{id}/versions → file upload, verify hash returned
- GET /models/{id}/versions/{vid} → version detail
- 404 cases for missing model/version

Use `tmp_path` fixture for artifact directory to avoid filesystem pollution.

## Key Files

| File | Action |
|------|--------|
| `src/api/schemas.py` | Edit — add registry schemas |
| `src/registry/service.py` | Create — registry service layer |
| `src/api/main.py` | Edit — add registry endpoints |
| `tests/test_registry.py` | Create — registry tests |

## Reuse

- `Model`, `ModelVersion`, `ModelType`, `GovernanceStatus` from `src/db/models.py`
- `Base` from `src/db/models.py` (for test SQLite setup)
- `get_session` from `src/db/config.py` (for FastAPI dependency injection)
- SQLite in-memory session fixture pattern from `tests/test_db_models.py`
- TestClient pattern from `tests/test_api_var.py`

## Verification

1. `pytest tests/test_registry.py -v` — all tests pass
2. `pytest tests/ -v` — no regressions in existing tests
3. `ruff check src/ tests/` — no lint errors
