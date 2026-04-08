# P1a-T3: Minimal FastAPI Endpoint — Inline VaR Execution

**Phase**: 1a — Vertical Slice
**Goal**: Accept inline portfolio + price data via REST, run Historical VaR, return results. No database, no registry, no persistence.

---

## Sub-task 1: Pydantic Request/Response Schemas

**File**: `src/api/schemas.py` (new) — **small**

**Why**: FastAPI needs Pydantic models for request validation and response serialization.

**What to build**:
- `InlinePosition`: ticker (str), quantity (float)
- `InlinePriceEntry`: date (str), close (float)
- `VarRunRequest`:
  - `positions`: list[InlinePosition]
  - `prices`: dict[str, list[InlinePriceEntry]] — ticker → price history
  - `config`: optional object with confidence_level, holding_period_days, lookback_window
- `TradeResultResponse`: ticker, quantity, latest_price, position_value, weight
- `ReturnStatistics`: mean, std, skew, kurtosis
- `VarAggregateResponse`: portfolio_value, var_absolute, var_relative, expected_shortfall, confidence_level, holding_period_days, lookback_window, return_statistics
- `VarRunResponse`: success, trade_results (list[TradeResultResponse]), aggregate (VarAggregateResponse | None), errors (list[str])

**Patterns to reuse**: Mirror shapes from protocol dataclasses in `src/engine/protocols.py`.

---

## Sub-task 2: FastAPI App + VaR Endpoint

**File**: `src/api/main.py` (new) — **medium**

**Why**: The core deliverable — a working endpoint that runs VaR.

**What to build**:
- `app = FastAPI(title="Risk Model Execution Platform")`
- `POST /runs/var` handler:
  1. Convert `VarRunRequest` → `MarketData`, `list[Trade]`, `RunConfig` (protocol types)
  2. Instantiate `HistoricalVarModel`
  3. Call `validate_inputs()` — if invalid, return 400 with validation errors
  4. Call `execute()` — return `VarRunResponse`

**Imports**:
- `HistoricalVarModel` from `src/models/historical_var.py`
- Protocol types from `src/engine/protocols.py`
- Schemas from `src/api/schemas.py`

**Error handling**:
- Validation failures (from `validate_inputs()`) → HTTP 400 with error list
- Unexpected model exceptions → HTTP 500

---

## Sub-task 3: Wire Up Entry Point

**File**: `src/api/__init__.py` (update) — **small**

**Why**: Allow `uvicorn src.api.main:app` to work and provide a clean import.

**What**: Export `app` from `src/api/__init__.py`.

---

## Testing

**File**: `tests/test_api_var.py` (new)

Using FastAPI `TestClient` (from `httpx`):
- **Happy path**: valid 3-ticker portfolio + price history → 200, response has VaR/CVaR values
- **Missing ticker**: position references ticker not in prices → 400 with descriptive error
- **Empty positions**: no trades → 400
- **Minimal config override**: custom confidence_level → 200, aggregate reflects the override
