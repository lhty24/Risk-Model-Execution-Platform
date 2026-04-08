"""Generate synthetic equity prices using Geometric Brownian Motion.

Produces data/seed/equity_prices.csv with ~261 trading days of daily closes
for 7 tickers. Uses a fixed random seed for reproducibility.

Usage:
    python data/seed/generate_prices.py
"""

from __future__ import annotations

import csv
import math
from datetime import date, timedelta
from pathlib import Path

import numpy as np

# Fixed seed for deterministic output
np.random.seed(42)

# Ticker configurations: (start_price, annualized_drift, annualized_volatility)
TICKERS: dict[str, tuple[float, float, float]] = {
    "AAPL": (170.0, 0.10, 0.22),
    "MSFT": (380.0, 0.12, 0.20),
    "GOOGL": (155.0, 0.08, 0.25),
    "AMZN": (180.0, 0.15, 0.30),
    "JPM": (195.0, 0.07, 0.18),
    "JNJ": (155.0, 0.05, 0.15),
    "XOM": (115.0, 0.06, 0.28),
}

START_DATE = date(2024, 4, 1)
END_DATE = date(2025, 3, 31)
DT = 1.0 / 252.0  # one trading day in years


def _trading_days(start: date, end: date) -> list[date]:
    """Return weekdays (Mon-Fri) between start and end inclusive."""
    days: list[date] = []
    current = start
    while current <= end:
        if current.weekday() < 5:  # Mon=0 ... Fri=4
            days.append(current)
        current += timedelta(days=1)
    return days


def _generate_prices(
    s0: float, mu: float, sigma: float, n_days: int
) -> list[float]:
    """Simulate daily closing prices using GBM.

    S(t+1) = S(t) * exp((mu - sigma^2/2)*dt + sigma*sqrt(dt)*Z)
    """
    prices = [s0]
    drift = (mu - 0.5 * sigma**2) * DT
    diffusion = sigma * math.sqrt(DT)
    z = np.random.standard_normal(n_days - 1)
    for i in range(n_days - 1):
        prices.append(prices[-1] * math.exp(drift + diffusion * z[i]))
    return prices


def main() -> None:
    days = _trading_days(START_DATE, END_DATE)
    n_days = len(days)

    # Generate prices for each ticker
    rows: list[tuple[str, str, str]] = []
    for ticker, (s0, mu, sigma) in TICKERS.items():
        prices = _generate_prices(s0, mu, sigma, n_days)
        for d, p in zip(days, prices):
            rows.append((d.isoformat(), ticker, f"{p:.2f}"))

    # Sort by date then ticker for readability
    rows.sort(key=lambda r: (r[0], r[1]))

    # Write CSV
    out_path = Path(__file__).parent / "equity_prices.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "ticker", "close"])
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {out_path}")
    print(f"  Tickers: {', '.join(TICKERS)}")
    print(f"  Date range: {days[0]} to {days[-1]} ({n_days} trading days)")


if __name__ == "__main__":
    main()
