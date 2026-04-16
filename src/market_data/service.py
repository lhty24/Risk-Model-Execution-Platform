"""Market Data Service — upload, retrieve, and resolve versioned market data snapshots."""

from __future__ import annotations

import csv
import hashlib
import io
import os
import uuid
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import MarketDataSnapshot, SnapshotType

SNAPSHOT_DIR = Path(os.environ.get("SNAPSHOT_DIR", "snapshots"))


# --- Parsing helpers ---


def _parse_equity_prices_csv(raw: bytes) -> dict:
    """Parse equity prices CSV (date,ticker,close) into MarketData.data format.

    Returns {"prices": {"AAPL": [{"date": "2024-04-01", "close": 170.0}, ...], ...}}
    """
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"File is not valid UTF-8: {exc}") from exc

    reader = csv.DictReader(io.StringIO(text))

    required_columns = {"date", "ticker", "close"}
    if reader.fieldnames is None or not required_columns.issubset(set(reader.fieldnames)):
        raise ValueError(
            f"CSV must contain columns {required_columns}, "
            f"got {reader.fieldnames}"
        )

    prices: dict[str, list[dict]] = {}
    row_count = 0
    for row in reader:
        ticker = row["ticker"].strip()
        if not ticker:
            raise ValueError(f"Empty ticker at row {row_count + 1}")
        try:
            close = float(row["close"])
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"Invalid close price '{row['close']}' for {ticker}: {exc}"
            ) from exc

        prices.setdefault(ticker, []).append(
            {"date": row["date"].strip(), "close": close}
        )
        row_count += 1

    if row_count == 0:
        raise ValueError("CSV contains no data rows")

    return {"prices": prices}


def _extract_metadata(snapshot_type: SnapshotType, parsed_data: dict) -> dict:
    """Extract summary metadata from parsed snapshot data."""
    if snapshot_type == SnapshotType.equity_prices:
        prices = parsed_data.get("prices", {})
        tickers = sorted(prices.keys())
        row_count = sum(len(entries) for entries in prices.values())
        return {"tickers": tickers, "row_count": row_count}
    return {}


# --- Service functions ---


def upload_snapshot(
    session: Session,
    *,
    snapshot_type: SnapshotType,
    as_of_date: date,
    file_bytes: bytes,
    filename: str,
    description: str | None = None,
    snapshot_dir: Path | None = None,
) -> MarketDataSnapshot:
    """Upload a market data snapshot — validate, hash, store to disk, persist to DB."""
    if snapshot_type == SnapshotType.yield_curve:
        raise ValueError("yield_curve upload not yet supported (coming in P2-T4)")

    # Validate and parse file
    parsed_data = _parse_equity_prices_csv(file_bytes)

    # Compute SHA-256
    data_hash = hashlib.sha256(file_bytes).hexdigest()

    # Extract metadata
    metadata = _extract_metadata(snapshot_type, parsed_data)

    # Store raw file to disk
    base = snapshot_dir or SNAPSHOT_DIR
    dest = base / str(snapshot_type.value) / str(as_of_date)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / filename).write_bytes(file_bytes)
    data_path = str(dest / filename)

    # Persist to DB
    snapshot = MarketDataSnapshot(
        snapshot_type=snapshot_type,
        as_of_date=as_of_date,
        description=description,
        data_path=data_path,
        data_hash=data_hash,
        metadata_=metadata,
    )
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)
    return snapshot


def get_snapshot(
    session: Session, snapshot_id: uuid.UUID
) -> MarketDataSnapshot | None:
    """Fetch a snapshot by ID."""
    stmt = select(MarketDataSnapshot).where(MarketDataSnapshot.id == snapshot_id)
    return session.execute(stmt).scalar_one_or_none()


def list_snapshots(
    session: Session,
    *,
    snapshot_type: SnapshotType | None = None,
    as_of_date: date | None = None,
) -> list[MarketDataSnapshot]:
    """List snapshots, optionally filtered by type and/or as-of date."""
    stmt = select(MarketDataSnapshot)
    if snapshot_type is not None:
        stmt = stmt.where(MarketDataSnapshot.snapshot_type == snapshot_type)
    if as_of_date is not None:
        stmt = stmt.where(MarketDataSnapshot.as_of_date == as_of_date)
    stmt = stmt.order_by(MarketDataSnapshot.created_at.desc())
    return list(session.execute(stmt).scalars().all())


def resolve(
    session: Session,
    *,
    snapshot_type: SnapshotType,
    as_of_date: date,
) -> MarketDataSnapshot:
    """Resolve a snapshot by type and as-of date (exact match).

    Raises LookupError if no matching snapshot exists.
    """
    stmt = select(MarketDataSnapshot).where(
        MarketDataSnapshot.snapshot_type == snapshot_type,
        MarketDataSnapshot.as_of_date == as_of_date,
    )
    snapshot = session.execute(stmt).scalar_one_or_none()
    if snapshot is None:
        raise LookupError(
            f"No {snapshot_type.value} snapshot for as-of date {as_of_date}"
        )
    return snapshot


def load_snapshot_data(snapshot: MarketDataSnapshot) -> dict:
    """Read and parse a snapshot's data file from disk.

    Returns the parsed dict suitable for MarketData.data.
    """
    raw = Path(snapshot.data_path).read_bytes()
    if snapshot.snapshot_type == SnapshotType.equity_prices:
        return _parse_equity_prices_csv(raw)
    raise ValueError(f"Unsupported snapshot type: {snapshot.snapshot_type}")
