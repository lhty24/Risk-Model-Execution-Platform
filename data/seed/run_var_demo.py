"""Run Historical VaR on seed data.

Loads equity_prices.csv and portfolio.json, then executes the VaR model
either directly (default) or via the FastAPI endpoint (--api).

Usage:
    python data/seed/run_var_demo.py                # direct model call
    python data/seed/run_var_demo.py --api           # call running server
    python data/seed/run_var_demo.py --confidence 0.95 --holding-period 10
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path


SEED_DIR = Path(__file__).parent


def load_prices() -> dict[str, list[dict[str, str | float]]]:
    """Load equity_prices.csv into {ticker: [{date, close}, ...]} format."""
    prices: dict[str, list[dict[str, str | float]]] = defaultdict(list)
    with open(SEED_DIR / "equity_prices.csv") as f:
        for row in csv.DictReader(f):
            prices[row["ticker"]].append(
                {"date": row["date"], "close": float(row["close"])}
            )
    return dict(prices)


def load_portfolio() -> list[dict[str, str | float]]:
    """Load portfolio.json."""
    with open(SEED_DIR / "portfolio.json") as f:
        return json.load(f)


def run_direct(
    prices: dict,
    portfolio: list[dict],
    confidence: float,
    holding_period: int,
) -> None:
    """Execute VaR via direct model call (no server needed)."""
    from src.engine.protocols import MarketData, RunConfig, Trade
    from src.models.historical_var import HistoricalVarModel

    # Find the last date in the price data for as_of_date
    all_dates = [
        entry["date"]
        for series in prices.values()
        for entry in series
    ]
    as_of = date.fromisoformat(max(all_dates))

    market_data = MarketData(
        snapshot_type="equity_prices",
        as_of_date=as_of,
        data={"prices": prices},
    )

    trades = [
        Trade(
            trade_type="equity_position",
            instrument_data={"ticker": p["ticker"], "quantity": p["quantity"]},
        )
        for p in portfolio
    ]

    config = RunConfig(
        parameters={
            "confidence_level": confidence,
            "holding_period_days": holding_period,
        }
    )

    model = HistoricalVarModel()

    validation = model.validate_inputs(market_data, trades)
    if not validation.is_valid:
        print("Validation failed:")
        for err in validation.errors:
            print(f"  - {err}")
        sys.exit(1)

    result = model.execute(market_data, trades, config)
    _print_results(result, confidence, holding_period)


def run_api(
    prices: dict,
    portfolio: list[dict],
    confidence: float,
    holding_period: int,
) -> None:
    """Execute VaR via the FastAPI endpoint."""
    try:
        import requests
    except ImportError:
        print("requests package required for --api mode: pip install requests")
        sys.exit(1)

    payload = {
        "positions": portfolio,
        "prices": prices,
        "config": {
            "confidence_level": confidence,
            "holding_period_days": holding_period,
        },
    }

    url = "http://localhost:8000/runs/var"
    print(f"POST {url}")
    resp = requests.post(url, json=payload, timeout=30)

    if resp.status_code != 200:
        print(f"Error {resp.status_code}: {resp.text}")
        sys.exit(1)

    data = resp.json()
    print(json.dumps(data, indent=2))


def _print_results(result, confidence: float, holding_period: int) -> None:
    """Pretty-print VaR run results."""
    if not result.success:
        print("Run failed:")
        for err in result.errors:
            print(f"  - {err}")
        return

    agg = result.aggregate
    stats = agg["return_statistics"]

    print("=" * 60)
    print("  Historical VaR — Seed Data Results")
    print("=" * 60)
    print()
    print(f"  Confidence level:    {confidence:.0%}")
    print(f"  Holding period:      {holding_period} day(s)")
    print(f"  Lookback window:     {agg['lookback_window']} returns")
    print()
    print(f"  Portfolio value:     ${agg['portfolio_value']:>14,.2f}")
    print(f"  VaR (absolute):      ${agg['var_absolute']:>14,.2f}")
    print(f"  VaR (relative):      {agg['var_relative']:>14.6f}")
    print(f"  Expected Shortfall:  ${agg['expected_shortfall']:>14,.2f}")
    print()
    print("  Return Statistics:")
    print(f"    Mean:              {stats['mean']:>14.8f}")
    print(f"    Std Dev:           {stats['std']:>14.8f}")
    print(f"    Skewness:          {stats['skew']:>14.8f}")
    print(f"    Excess Kurtosis:   {stats['kurtosis']:>14.8f}")
    print()
    print("  Per-Position Breakdown:")
    print(f"  {'Ticker':<8} {'Qty':>8} {'Price':>10} {'Value':>14} {'Weight':>8}")
    print(f"  {'-'*8} {'-'*8} {'-'*10} {'-'*14} {'-'*8}")
    for tr in result.trade_results:
        d = tr.result_data
        print(
            f"  {d['ticker']:<8} {d['quantity']:>8.0f} "
            f"${d['latest_price']:>9,.2f} "
            f"${d['position_value']:>13,.2f} "
            f"{d['weight']:>7.2%}"
        )
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Historical VaR on seed data"
    )
    parser.add_argument(
        "--api", action="store_true",
        help="Call the running FastAPI server instead of the model directly",
    )
    parser.add_argument(
        "--confidence", type=float, default=0.99,
        help="VaR confidence level (default: 0.99)",
    )
    parser.add_argument(
        "--holding-period", type=int, default=1,
        help="Holding period in days (default: 1)",
    )
    args = parser.parse_args()

    prices = load_prices()
    portfolio = load_portfolio()

    if args.api:
        run_api(prices, portfolio, args.confidence, args.holding_period)
    else:
        run_direct(prices, portfolio, args.confidence, args.holding_period)


if __name__ == "__main__":
    main()
