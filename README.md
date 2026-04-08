# Risk Model Execution Platform

A MEX-style platform that executes pre-built quantitative risk models against trade portfolios using versioned market data, with full provenance and governance. Models are built by quants externally and handed off to this platform for controlled, auditable execution.

## Key Features

- **Everything versioned and immutable** — models, market data, portfolios, configs
- **Provenance by default** — every result links to exact artifact hashes, snapshot IDs, and config
- **Governance-gated** — only `production` models produce official numbers
- **Batch-first** — nightly runs across trade books are the primary use case
- **Fail-fast** — missing tickers, insufficient yield curves, wrong data types produce clear errors before any calculation runs

## Architecture

Eight core components with a batch-first execution model:

| Component | Description |
|---|---|
| **API Layer** | FastAPI REST endpoints for all operations |
| **Model Registry** | Artifact storage + governance lifecycle (`development → production → deprecated`) |
| **Market Data Service** | Versioned, immutable snapshots (equity prices, yield curves) with as-of-date resolution |
| **Portfolio/Trade Store** | Versioned collections of positions (equities, bonds) |
| **Execution Engine** | Loads models via `RiskModel` protocol (`model_info()` → `validate_inputs()` → `execute()`) |
| **Batch Orchestrator** | Celery/Redis async job management (`pending → running → completed/failed/cancelled`) |
| **Results Store** | Per-trade and aggregate results, queryable by run/model/portfolio |
| **Audit Service** | Full provenance chain on every run and state change |

## Reference Models

Two risk models ship with the platform:

- **Historical VaR** — portfolio loss estimation using historical price returns (VaR, CVaR). Uses equal-weighted returns and square-root-of-time scaling.
- **Bond Pricer** — fixed-rate bond pricing from yield curves (PV, duration, convexity, DV01). Uses linear interpolation on zero rates with ACT/365 day count.

## Tech Stack

- **API**: Python 3.11+ / FastAPI / Pydantic
- **Database**: PostgreSQL + SQLAlchemy + Alembic
- **Calculations**: NumPy / Pandas
- **Async/Batch**: Celery + Redis
- **Infrastructure**: Docker + Docker Compose
- **CI**: GitHub Actions

## Project Structure

```
src/
├── api/            # FastAPI endpoints
├── models/         # Reference model implementations (VaR, bond pricer)
├── engine/         # Execution engine (model loading, compatibility checks)
├── registry/       # Model registry (metadata, versioning, governance)
├── market_data/    # Market data service (snapshots, as-of-date resolution)
├── portfolio/      # Portfolio/trade store
├── jobs/           # Batch orchestrator (Celery tasks)
├── results/        # Results store
├── audit/          # Audit service
└── db/             # SQLAlchemy models, Alembic migrations
tests/              # Test suite
data/seed/          # Sample market data, portfolios, seed scripts
docs/               # Design document and plans
```

## Getting Started

### Prerequisites

- Python 3.11+

### Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Run the API Server

```bash
uvicorn src.api.main:app --reload
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### Run Tests

```bash
pytest
```

## Development

- **Linting**: `ruff check .`
- **Formatting**: `ruff format .`
- **Target Python version**: 3.11
- **Line length**: 100 characters

## Design Document

See [`docs/design-doc.md`](docs/design-doc.md) for full architecture, component specs, reference model math, database schema, and development roadmap.
