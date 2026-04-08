"""Tests for the POST /runs/var endpoint."""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def _make_prices(tickers: list[str], num_days: int = 20) -> dict:
    """Generate synthetic price data for testing."""
    import random

    random.seed(42)
    prices = {}
    for ticker in tickers:
        base = 100.0 + random.random() * 100
        entries = []
        for day in range(num_days):
            base *= 1 + (random.random() - 0.5) * 0.04  # ±2% daily moves
            entries.append({"date": f"2024-01-{day + 1:02d}", "close": round(base, 2)})
        prices[ticker] = entries
    return prices


class TestVarEndpointHappyPath:
    def test_returns_200_with_var_results(self):
        tickers = ["AAPL", "MSFT", "GOOG"]
        payload = {
            "positions": [
                {"ticker": "AAPL", "quantity": 100},
                {"ticker": "MSFT", "quantity": 50},
                {"ticker": "GOOG", "quantity": 30},
            ],
            "prices": _make_prices(tickers),
        }

        resp = client.post("/runs/var", json=payload)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["errors"]) == 0
        assert len(body["trade_results"]) == 3
        assert body["aggregate"] is not None
        assert body["aggregate"]["var_absolute"] > 0
        assert body["aggregate"]["expected_shortfall"] > 0
        assert body["aggregate"]["confidence_level"] == 0.99  # default

    def test_trade_results_have_expected_fields(self):
        payload = {
            "positions": [{"ticker": "AAPL", "quantity": 100}],
            "prices": _make_prices(["AAPL"]),
        }

        resp = client.post("/runs/var", json=payload)
        body = resp.json()

        tr = body["trade_results"][0]
        assert tr["ticker"] == "AAPL"
        assert tr["quantity"] == 100
        assert tr["latest_price"] > 0
        assert tr["position_value"] > 0
        assert tr["weight"] == pytest.approx(1.0)

    def test_config_override(self):
        payload = {
            "positions": [{"ticker": "AAPL", "quantity": 100}],
            "prices": _make_prices(["AAPL"]),
            "config": {"confidence_level": 0.95},
        }

        resp = client.post("/runs/var", json=payload)
        body = resp.json()

        assert resp.status_code == 200
        assert body["aggregate"]["confidence_level"] == 0.95


class TestVarEndpointValidation:
    def test_missing_ticker_returns_400(self):
        payload = {
            "positions": [{"ticker": "AAPL", "quantity": 100}],
            "prices": _make_prices(["MSFT"]),  # no AAPL prices
        }

        resp = client.post("/runs/var", json=payload)

        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert any("AAPL" in err for err in detail)

    def test_empty_positions_returns_422(self):
        payload = {
            "positions": [],
            "prices": _make_prices(["AAPL"]),
        }

        resp = client.post("/runs/var", json=payload)

        # Pydantic min_length=1 triggers 422
        assert resp.status_code == 422

    def test_missing_positions_field_returns_422(self):
        payload = {"prices": _make_prices(["AAPL"])}

        resp = client.post("/runs/var", json=payload)

        assert resp.status_code == 422
