# P1a-T2: Historical VaR Model Implementation Plan

## Overview

**Task**: Historical VaR model as a standalone Python module (implements `RiskModel` protocol)
**Phase**: 1a — Proof of Concept
**File**: `src/models/historical_var.py`
**Imports**: `numpy`, `math`, all protocol types from `src/engine/protocols.py`

---

## Method 1: `model_info() → ModelInfo`

Returns fixed metadata:

```python
ModelInfo(
    name="historical_var",
    version="1.0.0",
    model_type="historical_var",
    required_market_data=["equity_prices"],
    accepted_trade_types=["equity_position"],
    config_schema={
        "confidence_level": {"type": "float", "default": 0.99, "description": "VaR confidence level"},
        "holding_period_days": {"type": "int", "default": 1, "description": "Holding period in days"},
        "lookback_window": {"type": "int", "default": 252, "description": "Number of historical days to use"},
    }
)
```

---

## Method 2: `validate_inputs(market_data, trades) → ValidationResult`

Checks (accumulate all errors, don't short-circuit):

1. **Snapshot type** — `market_data.snapshot_type == "equity_prices"`, else error
2. **Price data structure** — `market_data.data` has a `"prices"` key containing a dict of ticker → list of price records
3. **Trade completeness** — each trade has `trade_type == "equity_position"` and `instrument_data` contains both `"ticker"` (str) and `"quantity"` (numeric, non-zero)
4. **Ticker coverage** — every trade's ticker exists in the price data dict; collect all missing tickers into one error message
5. **Sufficient history** — each ticker's price list has at least 2 entries (minimum needed to compute 1 return); ideally warn if fewer than default lookback (252), but only hard-fail if < 2

Returns `ValidationResult(is_valid=True)` if no errors, otherwise `ValidationResult(is_valid=False, errors=[...])`.

---

## Method 3: `execute(market_data, trades, config) → RunResult`

### Step 0 — Parse config with defaults

```python
confidence_level = config.parameters.get("confidence_level", 0.99)
holding_period_days = config.parameters.get("holding_period_days", 1)
lookback_window = config.parameters.get("lookback_window", 252)
```

### Step 1 — Extract & align price series

- For each ticker, extract the list of close prices from `market_data.data["prices"][ticker]`
- Expected format per ticker: list of `{"date": "YYYY-MM-DD", "close": float}` sorted ascending by date
- Trim each series to the last `lookback_window + 1` entries (need N+1 prices to get N returns)
- Align dates across tickers — use only dates present in **all** tickers' series (intersection) to ensure portfolio return vectors are the same length

### Step 2 — Compute daily log returns (per ticker)

- `r_i,t = ln(P_i,t / P_i,t-1)` using `numpy.log`
- Result: a 2D array of shape `(num_tickers, num_returns)`

### Step 3 — Compute position weights

- Latest price per ticker: last entry in each aligned price series
- Position value: `qty_i × latest_price_i`
- Portfolio value: `Σ position_values`
- Weights: `w_i = position_value_i / portfolio_value`

### Step 4 — Compute portfolio daily returns

- `r_p,t = Σ w_i × r_i,t` — dot product of weight vector and return matrix
- Result: 1D array of shape `(num_returns,)`

### Step 5 — Compute VaR

- Sort portfolio returns ascending
- VaR percentile index: `(1 - confidence_level)` — e.g., 1st percentile for 99% confidence
- `var_relative = -numpy.percentile(portfolio_returns, (1 - confidence_level) * 100)`
- Apply square-root-of-time scaling: `var_relative *= math.sqrt(holding_period_days)`
- `var_absolute = var_relative × portfolio_value`

### Step 6 — Compute Expected Shortfall (CVaR)

- Threshold: the return value at the VaR percentile (before negation/scaling)
- `tail_returns = portfolio_returns[portfolio_returns <= threshold]`
- `cvar_relative = -numpy.mean(tail_returns) × math.sqrt(holding_period_days)`
- `cvar_absolute = cvar_relative × portfolio_value`

### Step 7 — Return statistics

```python
{
    "mean": float(numpy.mean(portfolio_returns)),
    "std": float(numpy.std(portfolio_returns, ddof=1)),
    "skew": float(manual_skew),
    "kurtosis": float(manual_kurtosis),
}
```

Use numpy-based manual calculation for skew/kurtosis to avoid adding scipy as a dependency.

### Step 8 — Build per-trade results

For each trade, a `TradeResult` with:
- `trade`: the original trade
- `result_data`: `{"ticker", "quantity", "latest_price", "position_value", "weight"}`

### Step 9 — Build and return `RunResult`

```python
RunResult(
    success=True,
    trade_results=[...],
    aggregate={
        "portfolio_value": float,
        "var_absolute": float,
        "var_relative": float,
        "expected_shortfall": float,
        "confidence_level": float,
        "holding_period_days": int,
        "lookback_window": int,
        "return_statistics": {...},
    },
)
```

**Error handling**: Wrap the core computation in a try/except. If any unexpected error occurs, return `RunResult(success=False, errors=[str(e)])`.

---

## Data Format Contracts

### Market Data

The model expects `market_data.data` to have this shape:

```python
{
    "prices": {
        "AAPL": [
            {"date": "2024-01-02", "close": 185.50},
            {"date": "2024-01-03", "close": 186.20},
            ...
        ],
        "MSFT": [...],
    }
}
```

### Trade

Each trade's `instrument_data`:

```python
{"ticker": "AAPL", "quantity": 100}
```

Positive quantity = long position. Negative quantity allowed (short).
