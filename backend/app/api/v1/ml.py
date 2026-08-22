from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.live_ops import Shipment
from app.models.route import GeneratedRoute
from app.models.ml import MLPrediction
from app.models.provenance import LineageEdge, ProvenanceRecord
from app.schemas.ml import (
    DelayFeatureInput,
    DelayInferenceResponse,
    DriftReport,
    ModelSummary,
    PredictionOutcomeInput,
    RetrainingReadiness,
)
from app.services.ml_monitoring import build_drift_report, build_retraining_readiness
from app.services.ml_prediction import delay_prediction_service

router = APIRouter()


def _manifests() -> list[dict]:
    root = delay_prediction_service.root
    if not root.exists():
        return []
    by_version: dict[tuple[str, str], dict] = {}
    paths = [*root.glob("*/*/metadata.json"), *root.glob("*/latest.json")]
    for path in paths:
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        model_name = item.get("model_name")
        version = item.get("version")
        if not isinstance(model_name, str) or not isinstance(version, str):
            continue
        key = (model_name, version)
        existing = by_version.get(key)
        if existing is None or item.get("status") == "PRODUCTION":
            by_version[key] = item
    return list(by_version.values())


def _summary(item: dict) -> ModelSummary:
    return ModelSummary(
        model_name=item["model_name"], version=item["version"], status=item["status"],
        production=bool(item.get("production")), algorithm=item["algorithm"],
        artifact_checksum=item["artifact_checksum"],
        feature_schema_version=item["feature_schema_version"],
        metrics=item.get("metrics", {}), eligibility=item.get("eligibility", {}),
    )


def _model_manifest(model_name: str, version: str | None = None) -> dict | None:
    matches = [
        item
        for item in _manifests()
        if item.get("model_name") == model_name
        and (version is None or item.get("version") == version)
    ]
    if not matches:
        return None
    return max(
        matches,
        key=lambda item: (
            item.get("status") == "PRODUCTION",
            str(item.get("created_at", "")),
        ),
    )


def _reference_mae(item: dict) -> tuple[float | None, float | None]:
    metrics = item.get("metrics", {})
    ml_value = metrics.get("test", {}).get("mae_minutes")
    deterministic_value = metrics.get("deterministic_baseline_test", {}).get(
        "mae_minutes"
    )
    return (
        float(ml_value) if isinstance(ml_value, (int, float)) else None,
        float(deterministic_value)
        if isinstance(deterministic_value, (int, float))
        else None,
    )


async def _owned_labeled_predictions(
    db: AsyncSession,
    *,
    user_id: str,
    model_name: str,
    model_version: str,
    limit: int,
) -> list[MLPrediction]:
    return list(
        (
            await db.scalars(
                select(MLPrediction)
                .where(
                    MLPrediction.user_id == user_id,
                    MLPrediction.model_name == model_name,
                    MLPrediction.model_version == model_version,
                    MLPrediction.actual_value_when_known.is_not(None),
                )
                .order_by(desc(MLPrediction.predicted_at))
                .limit(limit)
            )
        ).all()
    )


@router.post("/predictions/delay", response_model=DelayInferenceResponse)
async def predict_delay(
    payload: DelayFeatureInput,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> DelayInferenceResponse:
    if payload.route_id:
        route = await db.scalar(
            select(GeneratedRoute).where(
                GeneratedRoute.id == payload.route_id, GeneratedRoute.user_id == user.id
            )
        )
        if route is None:
            raise HTTPException(404, "Owned route not found")
    if payload.shipment_id:
        shipment = await db.scalar(
            select(Shipment).where(
                Shipment.id == payload.shipment_id, Shipment.user_id == user.id
            )
        )
        if shipment is None:
            raise HTTPException(404, "Owned shipment not found")
        if (
            payload.route_id is not None
            and shipment.route_id is not None
            and shipment.route_id != payload.route_id
        ):
            raise HTTPException(409, "Shipment is assigned to a different route")
        if payload.route_id is None and shipment.route_id is not None:
            payload = payload.model_copy(update={"route_id": shipment.route_id})
    return await delay_prediction_service.predict(payload, user.id, db)


@router.get("/models", response_model=list[ModelSummary])
async def list_models(user: CurrentUser = Depends(get_current_user)) -> list[ModelSummary]:
    return [_summary(item) for item in _manifests()]


@router.get("/models/{model_name}", response_model=ModelSummary)
async def get_model(
    model_name: str, user: CurrentUser = Depends(get_current_user)
) -> ModelSummary:
    item = _model_manifest(model_name)
    if item is None:
        raise HTTPException(404, "Model not found")
    return _summary(item)


@router.get("/models/{model_name}/metrics")
async def get_model_metrics(
    model_name: str, user: CurrentUser = Depends(get_current_user)
) -> dict:
    item = _model_manifest(model_name)
    if item is None:
        raise HTTPException(404, "Model not found")
    metrics_path = item.get("metrics_path")
    if not metrics_path:
        return item.get("metrics", {})
    path = Path(metrics_path)
    if not path.is_absolute():
        path = delay_prediction_service.root / path
    resolved = path.resolve()
    if delay_prediction_service.root not in resolved.parents:
        raise HTTPException(500, "Invalid model metrics path")
    return json.loads(resolved.read_text(encoding="utf-8"))


@router.get("/models/{model_name}/drift", response_model=DriftReport)
async def get_model_drift(
    model_name: str,
    version: str | None = Query(default=None, max_length=40),
    window: int = Query(default=100, ge=20, le=500),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> DriftReport:
    item = _model_manifest(model_name, version)
    if item is None:
        raise HTTPException(404, "Model not found")
    predictions = await _owned_labeled_predictions(
        db,
        user_id=user.id,
        model_name=model_name,
        model_version=item["version"],
        limit=window,
    )
    ml_reference, deterministic_reference = _reference_mae(item)
    return build_drift_report(
        predictions,
        model_name=model_name,
        model_version=item["version"],
        ml_reference_mae=ml_reference,
        deterministic_reference_mae=deterministic_reference,
    )


@router.get(
    "/models/{model_name}/retraining-readiness",
    response_model=RetrainingReadiness,
)
async def get_retraining_readiness(
    model_name: str,
    version: str | None = Query(default=None, max_length=40),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> RetrainingReadiness:
    item = _model_manifest(model_name, version)
    if item is None:
        raise HTTPException(404, "Model not found")
    predictions = await _owned_labeled_predictions(
        db,
        user_id=user.id,
        model_name=model_name,
        model_version=item["version"],
        limit=2000,
    )
    ml_reference, deterministic_reference = _reference_mae(item)
    drift = build_drift_report(
        predictions,
        model_name=model_name,
        model_version=item["version"],
        ml_reference_mae=ml_reference,
        deterministic_reference_mae=deterministic_reference,
    )
    return build_retraining_readiness(predictions, drift)


@router.post("/predictions/{prediction_id}/outcome")
async def record_prediction_outcome(
    prediction_id: uuid.UUID,
    payload: PredictionOutcomeInput,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    prediction = await db.scalar(
        select(MLPrediction).where(
            MLPrediction.id == prediction_id, MLPrediction.user_id == user.id
        )
    )
    if prediction is None:
        raise HTTPException(404, "Prediction not found")
    if prediction.actual_value_when_known is not None:
        raise HTTPException(409, "Prediction outcome is already recorded")
    prediction.actual_value_when_known = payload.actual_remaining_delay_minutes
    prediction.error_when_known = round(
        prediction.predicted_value - payload.actual_remaining_delay_minutes, 4
    )
    prediction.feature_snapshot = {
        **prediction.feature_snapshot,
        "outcome_data_class": payload.data_class,
    }
    recorded_at = datetime.now(timezone.utc)
    outcome_provenance = ProvenanceRecord(
        user_id=user.id,
        route_id=prediction.route_id,
        entity_type="ml_prediction_outcome",
        entity_key=str(prediction.id),
        decision_input_role="OBSERVED_DELAY_OUTCOME",
        canonical_source_type="OPERATOR_INPUT",
        raw_source_state="OPERATOR_CONFIRMED",
        fetched_at=recorded_at,
        freshness_state="NOT_APPLICABLE",
        cache_hit=False,
        used_in_decision=False,
        availability_state="OPERATOR_INPUT",
        completeness=1.0,
        value_summary={
            "actual_remaining_delay_minutes": payload.actual_remaining_delay_minutes,
            "prediction_error_minutes": prediction.error_when_known,
        },
        metadata_json={
            "classification": payload.data_class,
            "recorded_at": recorded_at.isoformat(),
        },
    )
    db.add(outcome_provenance)
    await db.flush()
    if prediction.provenance_record_id is not None:
        db.add(
            LineageEdge(
                parent_record_id=prediction.provenance_record_id,
                child_record_id=outcome_provenance.id,
                relationship="VALIDATED_BY",
            )
        )
    await db.commit()
    return {
        "prediction_id": prediction.id,
        "actual_remaining_delay_minutes": prediction.actual_value_when_known,
        "error_minutes": prediction.error_when_known,
        "data_class": payload.data_class,
        "provenance_record_id": outcome_provenance.id,
    }
