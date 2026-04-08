# P1a-T5: Seed Data

**Phase:** 1a — Proof of Life
**Task:** Sample equity prices (5-10 tickers, ~1 year daily closes) + sample portfolio (5 equity positions)

---

## Sub-task 1: Generate equity prices CSV (`data/seed/equity_prices.csv`)

**Why:** The platform needs realistic sample market data that exercises the Historical VaR model meaningfully — enough tickers and history to produce non-trivial risk numbers, and enough variance across tickers to show diversification effects.

**What to build:**
- A generation script (`data/seed/generate_prices.py`) that uses geometric Brownian motion (GBM) to create synthetic daily closes
- 7 tickers: `AAPL`, `MSFT`, `GOOGL`, `AMZN`, `JPM`, `JNJ`, `XOM` — chosen to span tech, finance, healthcare, energy sectors
- ~252 trading days from 2024-04-01 to 2025-03-31 (skip weekends, not holidays for simplicity)
- Each ticker gets a realistic starting price, annualized drift (5-15%), and volatility (15-35%) — varied per ticker so VaR results aren't trivially uniform
- GBM formula: `S(t+1) = S(t) * exp((μ - σ²/2)Δt + σ√Δt * Z)` where Z ~ N(0,1)
- Fixed random seed (`np.random.seed(42)`) so the data is deterministic and reproducible
- Output CSV columns: `date,ticker,close` — one row per ticker per day, close rounded to 2 decimals
- Expected size: ~1,764 rows (252 days × 7 tickers)

**Output format chosen because:**
- CSV is simple, inspectable, and diff-friendly in git
- Long format (date/ticker/close) is easy to pivot into the dict-of-lists format the VaR model expects
- Matches what a real market data feed would look like

**How to test:** The demo script (sub-task 3) validates the data works end-to-end. Spot-check that prices stay positive and within reasonable bounds.

---

## Sub-task 2: Sample portfolio JSON (`data/seed/portfolio.json`)

**Why:** The VaR model needs a portfolio of equity positions to compute risk against. The seed portfolio should be simple but non-trivial — different position sizes to show weight effects.

**What to build:**
- A JSON file with 5 positions using a subset of the 7 tickers from sub-task 1
- Structure matches `InlinePosition` schema from `src/api/schemas.py:11`:
  ```json
  [
    {"ticker": "AAPL", "quantity": 150},
    {"ticker": "MSFT", "quantity": 200},
    {"ticker": "GOOGL", "quantity": 50},
    {"ticker": "JPM",  "quantity": 300},
    {"ticker": "XOM",  "quantity": 250}
  ]
  ```
- Quantities intentionally varied (50-300 shares) so portfolio weights are unequal, producing more interesting VaR decomposition
- Uses 5 of 7 available tickers — the 2 unused tickers (AMZN, JNJ) serve as extra market data available for future portfolio variations

**Patterns reused:** `InlinePosition` (ticker + quantity) from `src/api/schemas.py:11-13`, and the `Trade` protocol's `instrument_data` dict from `src/engine/protocols.py`.

---

## Sub-task 3: Demo script (`data/seed/run_var_demo.py`)

**Why:** Proves the seed data works end-to-end with the existing VaR model and API. Also serves as a quick-start example for anyone onboarding to the project.

**What to build:**
- A standalone Python script that:
  1. Loads `equity_prices.csv` using the `csv` module (no pandas dependency needed)
  2. Loads `portfolio.json` using `json`
  3. Transforms CSV rows into the `prices` dict format: `{"AAPL": [{"date": "2024-04-01", "close": 150.0}, ...], ...}`
  4. **Two execution modes:**
     - **Direct model call** (default, no server needed): Instantiates `HistoricalVarModel`, builds `MarketData`/`Trade`/`RunConfig` objects, calls `validate_inputs()` then `execute()`, prints results
     - **API call** (with `--api` flag): POSTs to `http://localhost:8000/var/run` using `requests`, matching the `VarRunRequest` schema
  5. Pretty-prints the output: portfolio value, VaR, CVaR, per-position weights, return statistics
- Uses only stdlib + numpy (already a dependency) for the direct mode; `requests` only for `--api` mode
- Includes `argparse` for the `--api` flag and optional `--confidence` / `--holding-period` overrides

**Patterns reused:**
- `HistoricalVarModel` from `src/models/historical_var.py`
- `MarketData`, `Trade`, `RunConfig` from `src/engine/protocols.py`
- `VarRunRequest` schema structure from `src/api/schemas.py:27-30`

**How to test:** Run the script directly — it should print VaR results without errors. This is a manual validation step, not a pytest test.

---

## Files summary

| File | Action | Complexity |
|------|--------|------------|
| `data/seed/generate_prices.py` | Create | Medium |
| `data/seed/equity_prices.csv` | Generated output | — |
| `data/seed/portfolio.json` | Create | Small |
| `data/seed/run_var_demo.py` | Create | Small-Medium |
| `docs/design-doc.md` | Check off P1a-T5 | Trivial |
