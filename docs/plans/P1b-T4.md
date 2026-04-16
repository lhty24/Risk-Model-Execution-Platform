# P1b-T4: Market Data Service

## Context

The platform needs a Market Data Service to upload and retrieve versioned, immutable market data snapshots (equity prices, yield curves) with as-of-date resolution. This is the next step after the Model Registry (P1b-T3) — the execution engine (P1b-T6) will depend on this service to resolve market data for model runs.

---

## Sub-tasks

### 1. Service Layer — `src/market_data/service.py` (medium)

**Why**: The service layer is the foundation everything else depends on. The execution engine (P1b-T6) will call `resolve()` to find the right snapshot for a run, and `load_snapshot_data()` to feed parsed market data into models. Without this layer, there's no way to store or retrieve market data programmatically — the API endpoints and tests are just thin wrappers around these functions.

**What to build** (following `src/registry/service.py` pattern exactly):

- `SNAPSHOT_DIR = Path(os.environ.get("SNAPSHOT_DIR", "snapshots"))`
- `_parse_equity_prices_csv(raw: bytes) -> dict` — parse CSV (date,ticker,close) into `{"prices": {"AAPL": [{"date": "...", "close": 150.0}, ...]}}`  matching the `MarketData.data` format in `src/engine/protocols.py`
- `_extract_metadata(snapshot_type, parsed_data) -> dict` — extract tickers list + row count for equity_prices
- `upload_snapshot(session, *, snapshot_type, as_of_date, file_bytes, filename, description=None, snapshot_dir=None) -> MarketDataSnapshot` — compute SHA-256, validate/parse file, store to disk, persist to DB
- `get_snapshot(session, snapshot_id) -> MarketDataSnapshot | None`
- `list_snapshots(session, *, snapshot_type=None, as_of_date=None) -> list[MarketDataSnapshot]` — filterable, ordered by created_at desc
- `resolve(session, *, snapshot_type, as_of_date) -> MarketDataSnapshot` — exact match, raises `LookupError` if not found
- `load_snapshot_data(snapshot) -> dict` — read file from disk, parse based on snapshot_type

**Note**: yield_curve parsing is deferred to P2-T3/P2-T4. For now, `upload_snapshot` raises `ValueError` for yield_curve type.

**Reuse**: `MarketDataSnapshot` and `SnapshotType` from `src/db/models.py` (already exist).

### 2. Pydantic Schemas — add to `src/api/schemas.py` (small)

**Why**: The API endpoints need typed request/response contracts. `SnapshotResponse` serializes the ORM model for list/summary views. `SnapshotDetailResponse` extends it with the parsed data payload so clients (and eventually the UI in P5) can inspect snapshot contents without downloading raw files. Defining these before the endpoints keeps the API layer thin.

**What to add**:

```
SnapshotResponse:
    id, snapshot_type, as_of_date, description, data_hash, created_at, metadata_
    model_config = ConfigDict(from_attributes=True)

SnapshotDetailResponse(SnapshotResponse):
    data: dict   # parsed file contents inline
```

**Reuse**: import `SnapshotType` from `src/db/models.py`, follow existing `ConfigDict(from_attributes=True)` pattern.

### 3. API Endpoints — add to `src/api/main.py` (small)

**Why**: These are the public interface for uploading and querying market data. The seed script (P1b-T8) will use POST to load sample data. The run submission endpoint (P1b-T7) will need snapshots to exist before executing models. Without these endpoints, market data can only be manipulated in code — no CLI/curl/UI access.

Three endpoints following registry pattern:

- `POST /market-data/snapshots` (201) — multipart: `snapshot_type` Form, `as_of_date` Form, `description` Form (optional), `file` UploadFile. Catches `ValueError` → 400.
- `GET /market-data/snapshots` — query params: `snapshot_type`, `as_of_date` (both optional)
- `GET /market-data/snapshots/{snapshot_id}` — returns metadata + parsed data inline. 404 if not found.

### 4. Tests — `tests/test_market_data.py` (medium)

**Why**: Market data is a critical input to every model run — if parsing silently drops rows, truncates tickers, or mismatches the `MarketData.data` format, VaR/bond pricing results will be wrong with no obvious error. Tests lock down the CSV parsing contract, the as-of-date resolution logic (which the execution engine relies on), and the API error handling (400 on bad files, 404 on missing snapshots).

Following `tests/test_registry.py` pattern (in-memory SQLite, `engine`/`session`/`client` fixtures):

**Service tests**:
- `TestUploadSnapshot` — correct hash, file stored to disk, metadata extracted (tickers, row_count), ValueError on malformed CSV
- `TestGetSnapshot` — by ID, None for missing
- `TestListSnapshots` — all, filter by type, filter by date, filter by both
- `TestResolve` — exact match found, LookupError when no match
- `TestLoadSnapshotData` — parses stored CSV into correct dict format

**API tests**:
- `TestSnapshotAPI` — POST 201, POST 400 (bad CSV), GET list, GET list filtered, GET detail with data, GET 404

---

## Files to Modify/Create

| File | Action |
|------|--------|
| `src/market_data/service.py` | Create — service layer |
| `src/api/schemas.py` | Edit — add snapshot schemas |
| `src/api/main.py` | Edit — add 3 market-data endpoints |
| `tests/test_market_data.py` | Create — service + API tests |

---

## Verification

1. `pytest tests/test_market_data.py -v` — all tests pass
2. `pytest tests/ -v` — no regressions in existing tests
3. Manual: start API, upload `data/seed/equity_prices.csv` via POST, list snapshots, GET detail with parsed data
