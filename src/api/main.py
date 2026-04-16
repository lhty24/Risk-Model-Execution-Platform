"""FastAPI application for the Risk Model Execution Platform."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from src.api.schemas import (
    CreateModelRequest,
    ModelResponse,
    ModelSummaryResponse,
    ModelVersionResponse,
    SnapshotDetailResponse,
    SnapshotResponse,
    TradeResultResponse,
    ReturnStatistics,
    VarAggregateResponse,
    VarRunRequest,
    VarRunResponse,
)
from src.db.config import get_session
from src.db.models import ModelType, SnapshotType
from src.engine.protocols import MarketData, RunConfig, Trade
from src.market_data import service as market_data
from src.models.historical_var import HistoricalVarModel
from src.registry import service as registry

SessionDep = Annotated[Session, Depends(get_session)]

app = FastAPI(title="Risk Model Execution Platform")


@app.post("/runs/var", response_model=VarRunResponse)
def run_var(request: VarRunRequest) -> VarRunResponse:
    """Execute Historical VaR on inline portfolio and price data."""

    # Convert request → protocol types
    market_data = MarketData(
        snapshot_type="equity_prices",
        as_of_date=date.today(),
        data={
            "prices": {
                ticker: [{"date": e.date, "close": e.close} for e in entries]
                for ticker, entries in request.prices.items()
            }
        },
    )

    trades = [
        Trade(
            trade_type="equity_position",
            instrument_data={"ticker": p.ticker, "quantity": p.quantity},
        )
        for p in request.positions
    ]

    config_params: dict = {}
    if request.config:
        if request.config.confidence_level is not None:
            config_params["confidence_level"] = request.config.confidence_level
        if request.config.holding_period_days is not None:
            config_params["holding_period_days"] = request.config.holding_period_days
        if request.config.lookback_window is not None:
            config_params["lookback_window"] = request.config.lookback_window
    run_config = RunConfig(parameters=config_params)

    # Validate and execute
    model = HistoricalVarModel()

    validation = model.validate_inputs(market_data, trades)
    if not validation.is_valid:
        raise HTTPException(status_code=400, detail=validation.errors)

    result = model.execute(market_data, trades, run_config)

    # Build response
    trade_results = [
        TradeResultResponse(
            ticker=tr.result_data["ticker"],
            quantity=tr.result_data["quantity"],
            latest_price=tr.result_data["latest_price"],
            position_value=tr.result_data["position_value"],
            weight=tr.result_data["weight"],
        )
        for tr in result.trade_results
    ]

    aggregate = None
    if result.success and result.aggregate:
        agg = result.aggregate
        stats = agg["return_statistics"]
        aggregate = VarAggregateResponse(
            portfolio_value=agg["portfolio_value"],
            var_absolute=agg["var_absolute"],
            var_relative=agg["var_relative"],
            expected_shortfall=agg["expected_shortfall"],
            confidence_level=agg["confidence_level"],
            holding_period_days=agg["holding_period_days"],
            lookback_window=agg["lookback_window"],
            return_statistics=ReturnStatistics(
                mean=stats["mean"],
                std=stats["std"],
                skew=stats["skew"],
                kurtosis=stats["kurtosis"],
            ),
        )

    return VarRunResponse(
        success=result.success,
        trade_results=trade_results,
        aggregate=aggregate,
        errors=result.errors,
    )


# --- Model Registry endpoints ---


@app.post("/models", response_model=ModelResponse, status_code=201)
def create_model(request: CreateModelRequest, session: SessionDep) -> ModelResponse:
    """Register a new model in the registry."""
    model = registry.create_model(
        session,
        name=request.name,
        description=request.description,
        model_type=request.model_type,
        owner=request.owner,
    )
    return ModelResponse.model_validate(model)


@app.get("/models", response_model=list[ModelSummaryResponse])
def list_models(
    session: SessionDep, model_type: ModelType | None = None
) -> list[ModelSummaryResponse]:
    """List all models, optionally filtered by type."""
    models = registry.list_models(session, model_type=model_type)
    return [
        ModelSummaryResponse(
            id=m.id,
            name=m.name,
            description=m.description,
            model_type=m.model_type,
            owner=m.owner,
            created_at=m.created_at,
            updated_at=m.updated_at,
            version_count=len(m.versions),
        )
        for m in models
    ]


@app.get("/models/{model_id}", response_model=ModelResponse)
def get_model(model_id: UUID, session: SessionDep) -> ModelResponse:
    """Get a model by ID with all its versions."""
    model = registry.get_model(session, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return ModelResponse.model_validate(model)


@app.post(
    "/models/{model_id}/versions",
    response_model=ModelVersionResponse,
    status_code=201,
)
async def create_model_version(
    model_id: UUID, file: UploadFile, session: SessionDep
) -> ModelVersionResponse:
    """Upload a new version artifact for an existing model."""
    content = await file.read()
    try:
        version = registry.create_version(
            session,
            model_id=model_id,
            artifact_bytes=content,
            filename=file.filename or "model.py",
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Model not found")
    return ModelVersionResponse.model_validate(version)


@app.get(
    "/models/{model_id}/versions/{version_id}",
    response_model=ModelVersionResponse,
)
def get_model_version(
    model_id: UUID, version_id: UUID, session: SessionDep
) -> ModelVersionResponse:
    """Get a specific model version."""
    version = registry.get_version(session, model_id=model_id, version_id=version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Model version not found")
    return ModelVersionResponse.model_validate(version)


# --- Market Data endpoints ---


@app.post("/market-data/snapshots", response_model=SnapshotResponse, status_code=201)
async def upload_snapshot(
    snapshot_type: SnapshotType = Form(...),
    as_of_date: date = Form(...),
    file: UploadFile = ...,
    description: str | None = Form(None),
    session: Session = Depends(get_session),
) -> SnapshotResponse:
    """Upload a market data snapshot."""
    content = await file.read()
    try:
        snapshot = market_data.upload_snapshot(
            session,
            snapshot_type=snapshot_type,
            as_of_date=as_of_date,
            file_bytes=content,
            filename=file.filename or "snapshot.csv",
            description=description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return SnapshotResponse.model_validate(snapshot)


@app.get("/market-data/snapshots", response_model=list[SnapshotResponse])
def list_snapshots(
    session: SessionDep,
    snapshot_type: SnapshotType | None = None,
    as_of_date: date | None = None,
) -> list[SnapshotResponse]:
    """List market data snapshots, optionally filtered by type and/or date."""
    snapshots = market_data.list_snapshots(
        session, snapshot_type=snapshot_type, as_of_date=as_of_date
    )
    return [SnapshotResponse.model_validate(s) for s in snapshots]


@app.get("/market-data/snapshots/{snapshot_id}", response_model=SnapshotDetailResponse)
def get_snapshot_detail(
    snapshot_id: UUID, session: SessionDep
) -> SnapshotDetailResponse:
    """Get a snapshot's metadata and parsed data."""
    snapshot = market_data.get_snapshot(session, snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    data = market_data.load_snapshot_data(snapshot)
    return SnapshotDetailResponse.model_validate({**snapshot.__dict__, "data": data})
