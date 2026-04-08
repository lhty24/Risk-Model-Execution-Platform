# P1a-T4: Unit tests — VaR calculation against hand-computed expected values

**Phase**: 1a — Vertical Slice
**Status**: Not started
**File**: `tests/test_historical_var.py`

---

## Sub-task 1: Hand-computed reference dataset

Design a deterministic 2-ticker, 6-day price series small enough to verify every intermediate value by hand.

**Raw data:**
- **Ticker A** prices: [100, 102, 101, 103, 104, 102]
- **Ticker B** prices: [50, 51, 49, 50, 52, 51]
- **Portfolio**: 10 shares of A, 20 shares of B

**Hand-computed intermediates (to be verified in code comments):**

1. **Log returns** (5 returns each from 6 prices):
   - A: [ln(102/100), ln(101/102), ln(103/101), ln(104/103), ln(102/104)]
   - B: [ln(51/50), ln(49/51), ln(50/49), ln(52/50), ln(51/52)]

2. **Position values** (using last price):
   - A: 10 × 102 = 1020
   - B: 20 × 51 = 1020
   - Portfolio value: 2040
   - Weights: A = 0.5, B = 0.5

3. **Portfolio daily returns**: weighted sum of A and B returns for each of 5 days

4. **Sorted portfolio returns** → identify the percentile values for VaR at 99% and 95%

5. **CVaR**: mean of returns at or below the VaR threshold

6. **Return statistics**: mean, std (ddof=1), skewness (adjusted 3rd moment), excess kurtosis (adjusted 4th moment)

All expected values will be pre-computed using a standalone Python/NumPy script, then hardcoded as constants in the test file with inline comments showing the math. This ensures the test is truly independent of the implementation.

**Helper functions** in the test module:
- `make_market_data(prices_dict, as_of_date=None)` → returns a `MarketData` instance
- `make_trades(positions: list[tuple[str, float]])` → returns a list of `Trade` instances
- `make_config(**overrides)` → returns a `RunConfig` with defaults merged

## Sub-task 2: `validate_inputs()` tests — class `TestValidateInputs`

Each test constructs minimal invalid input and asserts the specific error message appears:

| Test name | Setup | Expected error substring |
|---|---|---|
| `test_valid_inputs` | Reference dataset | `is_valid=True`, no errors |
| `test_wrong_snapshot_type` | `snapshot_type="yield_curve"` | `"Expected equity_prices"` |
| `test_prices_not_a_dict` | `data={"prices": "not_a_dict"}` | `"prices must be a dict"` |
| `test_wrong_trade_type` | `trade_type="bond_position"` | `"Unsupported trade type"` |
| `test_empty_ticker` | `instrument_data={"ticker": "", "quantity": 10}` | `"ticker must be a non-empty string"` |
| `test_zero_quantity` | `instrument_data={"ticker": "AAPL", "quantity": 0}` | `"quantity must be non-zero"` |
| `test_missing_ticker_in_prices` | Ticker "MSFT" not in prices dict | `"Missing price data"` |
| `test_insufficient_history` | Only 1 price entry for a ticker | `"at least 2"` |
| `test_multiple_errors_accumulated` | Several invalid trades at once | Multiple errors returned in one call |

Pattern: instantiate `HistoricalVarModel()`, call `validate_inputs()`, assert on `result.is_valid` and `result.errors`. Read actual error strings from `src/models/historical_var.py` to match exactly.

## Sub-task 3: Core VaR math tests — class `TestVarCalculation`

Using the reference dataset with default config (`confidence=0.99, holding_period=1, lookback=252`):

| Test name | What it verifies | Assertion approach |
|---|---|---|
| `test_trade_results_position_values` | Each `TradeResult.result_data` has correct `latest_price`, `position_value`, `weight` | `pytest.approx(expected, rel=1e-9)` per field |
| `test_portfolio_value` | `aggregate["portfolio_value"]` matches sum of absolute position values | Exact float comparison via `approx` |
| `test_var_absolute_and_relative` | `var_absolute` and `var_relative` match hand-computed percentile | `pytest.approx(expected, rel=1e-6)` — slightly looser tolerance for percentile interpolation |
| `test_expected_shortfall` | `expected_shortfall` matches hand-computed CVaR | `pytest.approx(expected, rel=1e-6)` |
| `test_return_statistics_mean_std` | `return_statistics["mean"]` and `["std"]` match NumPy `mean()` / `std(ddof=1)` | `pytest.approx(expected, rel=1e-9)` |
| `test_return_statistics_skew_kurtosis` | Skewness and excess kurtosis match the adjusted-moment formulas | `pytest.approx(expected, rel=1e-6)` — these are higher-order so slightly looser |
| `test_lookback_window_reported` | `aggregate["lookback_window"]` equals actual number of returns used | Exact int comparison |
| `test_success_flag` | `result.success is True`, `result.errors == []` | Direct equality |

Each test calls `model.execute()` once on the reference dataset and checks one aspect of the result. A module-level fixture (`@pytest.fixture(scope="module")`) will cache the `RunResult` so the model only executes once across all tests in this class.

## Sub-task 4: Edge cases & config — class `TestVarEdgeCases`

| Test name | Setup | What it verifies |
|---|---|---|
| `test_confidence_95` | `confidence_level=0.95` | VaR is smaller than at 99% (less extreme percentile); verify exact value against hand-computed 5th percentile |
| `test_multiday_holding_period` | `holding_period_days=10` | `var_relative` equals 1-day VaR × √10; `var_absolute` scales accordingly |
| `test_single_position_portfolio` | 1 ticker, 1 trade | Weight = 1.0, portfolio returns = asset returns exactly |
| `test_lookback_trims_data` | 252-day default but only 6 days provided | Uses all available data (5 returns), `lookback_window` in result reflects actual count |
| `test_short_lookback_config` | `lookback_window=3` with 6-day data | Only last 4 prices (3 returns) used; VaR computed on 3 observations |
| `test_execution_error_returns_failure` | Corrupt `market_data.data` to trigger exception inside `_execute()` | `result.success is False`, `result.errors` is non-empty |

**Tolerance strategy**: Use `pytest.approx(rel=1e-6)` for VaR/CVaR/skew/kurtosis (percentile interpolation and higher-order moments), `pytest.approx(rel=1e-9)` for exact arithmetic (weights, position values, mean, std).

**File location**: `tests/test_historical_var.py` — all tests import directly from `src.models.historical_var` and `src.engine.protocols`, bypassing the API layer entirely.
