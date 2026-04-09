# P1b-T2: Database Schema + SQLAlchemy Models + Alembic Migrations

## Sub-tasks

### 1. Alembic initialization (small)
- **Why**: Alembic manages schema migrations for PostgreSQL
- **What**: Run `alembic init alembic`, then customize `alembic.ini` (set `sqlalchemy.url` placeholder) and `alembic/env.py` (import `Base.metadata` from our models, read `DATABASE_URL` from env)
- **Files**: New `alembic.ini`, `alembic/env.py`, `alembic/versions/`
- **Pattern**: Standard Alembic setup with env var override for the DB URL
- **Test**: Migration runs without error in sub-task 3

### 2. SQLAlchemy declarative models (medium)
- **Why**: Core of the task — typed ORM models matching the Section 7 schema
- **What**: Create `src/db/models.py` with `Base = declarative_base()` and 8 model classes:
  - `Model` — risk model registry entry
  - `ModelVersion` — versioned artifacts with governance status
  - `MarketDataSnapshot` — versioned, immutable market data
  - `Portfolio` — named portfolio with version
  - `PortfolioPosition` — individual positions (equity/bond) with JSON instrument data
  - `Run` — execution record linking model + data + portfolio
  - `RunResult` — per-trade and aggregate results
  - `AuditLog` — event log for provenance
- **Files**: New `src/db/models.py`
- **Details**: UUIDs with `uuid4` defaults, JSON columns via `sqlalchemy.JSON`, string enums via `sqlalchemy.Enum`, foreign keys and indexes per Section 7
- **Reuse**: `engine`, `SessionLocal` from `src/db/config.py`

### 3. Initial Alembic migration (small)
- **Why**: Generate actual DDL from models for PostgreSQL
- **What**: `alembic revision --autogenerate -m "initial schema"`, review generated migration
- **Files**: New `alembic/versions/001_initial_schema.py`
- **Test**: `alembic upgrade head` against Docker PostgreSQL

### 4. Update `src/db/__init__.py` (small)
- **Why**: Clean import path — `from src.db import Base, Model, Run, ...`
- **What**: Import and re-export `Base` and all model classes

### 5. Unit tests (medium)
- **Why**: Verify models are well-formed and relationships work
- **What**: `tests/test_db_models.py` — use SQLite in-memory engine, `Base.metadata.create_all()`, insert sample rows for each table, verify foreign key relationships and enum constraints
- **Files**: New `tests/test_db_models.py`
- **Test**: `pytest tests/test_db_models.py`
