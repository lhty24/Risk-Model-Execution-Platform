# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MEX-style Risk Model Execution Platform — executes pre-built quantitative risk models against trade portfolios using versioned market data, with full provenance and governance. Models are built by quants externally and handed off to this platform for controlled, auditable execution.

## Tech Stack

- **API**: Python 3.11+ / FastAPI / Pydantic
- **Database**: PostgreSQL + SQLAlchemy + Alembic
- **Calculations**: NumPy / Pandas
- **Storage**: Local filesystem (MVP), S3-compatible (future)
- **Async/Batch**: Celery + Redis
- **Infrastructure**: Docker + Docker Compose
- **CI**: GitHub Actions

## Architecture

Eight core components, batch-first execution model:

1. **API Layer (FastAPI)** — REST endpoints for all operations
2. **Model Registry** — artifact storage + governance lifecycle (`development → production → deprecated`; extended states in Phase 4)
3. **Market Data Service** — versioned, immutable snapshots (equity prices, yield curves) with as-of-date resolution
4. **Portfolio/Trade Store** — versioned collections of positions (equities, bonds)
5. **Execution Engine** — loads model via `RiskModel` protocol (`model_info()` → `validate_inputs()` → `execute()`), fails fast on input mismatches
6. **Batch Orchestrator (Celery/Redis)** — async job management (`pending → running → completed/failed/cancelled`)
7. **Results Store** — per-trade and aggregate results, queryable by run/model/portfolio
8. **Audit Service** — full provenance chain on every run and state change

## Key Design Principles

- **Everything is versioned and immutable** — models, market data, portfolios, configs
- **Provenance by default** — every result links to exact artifact hashes, snapshot IDs, config
- **Governance-gated** — only `production` models produce official numbers
- **Models as Python modules** (not pickle) implementing a typed `RiskModel` protocol with `model_info()` for self-description
- **Batch-first** — nightly runs across trade books are the primary use case
- **Fail-fast on input mismatches** — missing tickers, insufficient yield curve, wrong data types → clear errors before any calculation runs

## Reference Models

Two concrete risk models ship with the platform:

- **Historical VaR** — portfolio loss estimation using historical price returns (VaR, CVaR). MVP uses equal-weighted returns, square-root-of-time scaling.
- **Bond Pricer** — fixed-rate bond pricing from yield curves (PV, duration, convexity, DV01). MVP uses linear interpolation on zero rates, ACT/365 day count.

## Source Layout

- `src/api/` — FastAPI endpoints
- `src/registry/` — Model Registry (metadata, versioning, governance)
- `src/market_data/` — Market Data Service (snapshots, as-of-date resolution, interpolation)
- `src/portfolio/` — Portfolio/Trade Store
- `src/engine/` — Execution Engine (model loading, compatibility checks, execution)
- `src/jobs/` — Batch Orchestrator (Celery tasks)
- `src/results/` — Results Store
- `src/audit/` — Audit Service
- `src/models/` — Reference model implementations (VaR, bond pricer)
- `src/db/` — SQLAlchemy models, Alembic migrations
- `tests/` — Test files
- `data/seed/` — Sample market data, portfolios, and seed scripts
- `docs/design-doc.md` — Full design document

## Design Document

`docs/design-doc.md` contains: domain context (Section 2), architecture diagrams (Section 4), component specs (Section 5), reference model math + known simplifications (Section 6), database schema (Section 7), development roadmap with task IDs (Section 8).
