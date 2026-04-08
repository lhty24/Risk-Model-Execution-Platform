# P1b-T1: Docker Compose for PostgreSQL + Redis

**Phase**: 1b — Platform Foundation
**Status**: Planned

## Sub-tasks

### 1. Create `docker-compose.yml` (Small)
- **Why**: PostgreSQL stores all platform entities (models, runs, results, audit). Redis backs Celery for async batch jobs. Both are needed for every subsequent Phase 1b task.
- **What**: Compose file with two services:
  - `postgres`: PostgreSQL 16, port 5432, named volume for data persistence, health check via `pg_isready`
  - `redis`: Redis 7, port 6379, health check via `redis-cli ping`
- **Files**: `docker-compose.yml` (new)
- **Test**: `docker compose up -d` → both services healthy

### 2. Add `.env.example` (Small)
- **Why**: Centralizes connection config, documents required env vars for new contributors.
- **What**: Template with `DATABASE_URL`, `REDIS_URL`, and Postgres-specific vars (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`).
- **Files**: `.env.example` (new)
- **Test**: Copy to `.env`, compose reads it correctly

### 3. Add `src/db/config.py` — database + Redis config (Small)
- **Why**: P1b-T2 (schemas + migrations) needs a SQLAlchemy engine. Setting up the config now keeps the next task focused on models/migrations.
- **What**: Read `DATABASE_URL` and `REDIS_URL` from environment with sensible defaults matching docker-compose. Expose `get_engine()` and `get_session` factory using SQLAlchemy 2.0 patterns (sync).
- **Files**: `src/db/config.py` (new)
- **Test**: Import `src.db.config` with default env → no errors, engine connects to local Postgres

### 4. Update `pyproject.toml` — add dependencies (Small)
- **Why**: Need SQLAlchemy, Alembic, psycopg2-binary, and redis as project dependencies.
- **What**: Add to `dependencies` list in `pyproject.toml`.
- **Files**: `pyproject.toml` (edit)
- **Test**: `pip install -e .` succeeds
