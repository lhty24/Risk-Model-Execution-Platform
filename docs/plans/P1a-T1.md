# P1a-T1: Project Scaffolding

**Phase:** 1a — Proof of Life
**Task:** Directory structure, pyproject.toml, dev dependencies, pytest config

---

## Sub-task 1: Directory structure + packages (small)

**Why:** Establishes the module layout all future code builds on.

**What to create:**
```
src/
├── __init__.py
├── api/__init__.py
├── registry/__init__.py
├── market_data/__init__.py
├── portfolio/__init__.py
├── engine/__init__.py
├── jobs/__init__.py
├── results/__init__.py
├── audit/__init__.py
├── models/__init__.py
└── db/__init__.py
tests/
├── __init__.py
└── conftest.py
data/seed/          (empty, for P1a-T5)
docs/plans/         (for saving implementation plans)
```

All `__init__.py` files start empty. The `conftest.py` gets a minimal stub (see sub-task 3).

---

## Sub-task 2: `pyproject.toml` (small)

**Why:** Single source of truth for project metadata, dependencies, and tool config.

**Project metadata:**
```toml
[project]
name = "risk-model-execution-platform"
version = "0.1.0"
requires-python = ">=3.11"
```

**Runtime dependencies (Phase 1a only):**

| Package | Purpose |
|---|---|
| `fastapi>=0.115` | API layer |
| `uvicorn[standard]>=0.34` | ASGI server |
| `pydantic>=2.0` | Request/response validation |
| `numpy>=1.26` | Numerical computation (returns, percentiles) |
| `pandas>=2.1` | Price history DataFrames, time series ops |

**Dev dependencies (`[project.optional-dependencies] dev`):**

| Package | Purpose |
|---|---|
| `pytest>=8.0` | Test runner |
| `httpx>=0.27` | FastAPI `TestClient` async support |
| `ruff>=0.8` | Linter + formatter |

**Why these versions:** Align with Python 3.11+ ecosystem. FastAPI 0.115+ has Pydantic v2 as default. Numpy 1.26+ and Pandas 2.1+ are the Python 3.11-native releases.

---

## Sub-task 3: Pytest configuration (small)

**Why:** Makes `pytest` discover tests and resolve imports correctly from day one.

**In `pyproject.toml`:**
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

`pythonpath = ["."]` ensures `from src.engine.protocols import RiskModel` works without installing the package in editable mode.

**`tests/conftest.py`:** Empty file with a docstring — placeholder for shared fixtures (FastAPI test client, sample data factories) in later tasks.

---

## Sub-task 4: `.gitignore` (small)

**Why:** Prevent committing virtualenvs, caches, IDE files, and future artifacts.

**Sections to include:**
- Python bytecode (`__pycache__/`, `*.pyc`)
- Virtual environments (`venv/`, `.venv/`, `env/`)
- Distribution/packaging (`dist/`, `*.egg-info/`, `build/`)
- IDE files (`.vscode/`, `.idea/`)
- OS files (`.DS_Store`)
- Environment files (`.env`, `.env.*`)
- Future artifact storage (`artifacts/`)

---

## Sub-task 5: `RiskModel` protocol + core types (small)

**Why:** Defines the contract that all models must implement (design doc Section 5.5). Having this in place first means P1a-T2 (Historical VaR model) can code directly against the protocol and we can type-check from the start.

**File:** `src/engine/protocols.py`

**Types to define (from design doc Sections 5.5 + 6):**

| Type | Fields | Notes |
|---|---|---|
| `ModelInfo` | `name`, `version`, `model_type`, `required_market_data` (list of str like `"equity_prices"`), `accepted_trade_types` (list of str like `"equity_position"`), `config_schema` (dict) | Returned by `model_info()` |
| `ValidationResult` | `is_valid: bool`, `errors: list[str]` | Returned by `validate_inputs()` |
| `MarketData` | `snapshot_type: str`, `as_of_date: date`, `data: dict[str, Any]` | Generic container — equity prices or yield curve |
| `Trade` | `trade_type: str`, `instrument_data: dict[str, Any]` | Generic container — equity or bond position |
| `RunConfig` | `parameters: dict[str, Any]` | E.g., `{"confidence_level": 0.99, "holding_period": 1}` |
| `TradeResult` | `trade: Trade`, `result_data: dict[str, Any]` | Per-trade output |
| `RunResult` | `success: bool`, `trade_results: list[TradeResult]`, `aggregate: dict[str, Any]`, `errors: list[str]` | Full run output |
| `RiskModel` | Protocol with `model_info()`, `validate_inputs()`, `execute()` | The core contract |

All types as `dataclass` — plain Python, no Pydantic here (these are internal engine types, not API schemas). The `RiskModel` itself is a `typing.Protocol` so models don't need to inherit from a base class.

**Testing:** No dedicated tests for this sub-task (it's just type definitions). The protocol gets exercised in P1a-T2 when the VaR model implements it, and in P1a-T4 with unit tests.
