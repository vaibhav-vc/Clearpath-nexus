from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Sequence

from app.schemas.ml import DriftReport, RetrainingReadiness

MIN_DRIFT_SAMPLES = 20
MIN_RETRAINING_LABELS = 100
MIN_RETRAINING_COVERAGE_DAYS = 14
MIN_RETRAINING_ROUTES = 3


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def build_drift_report(
    predictions: Sequence[Any],
    *,
    model_name: str,
    model_version: str,
    ml_reference_mae: float | None,
    deterministic_reference_mae: float | None,
    minimum_samples: int = MIN_DRIFT_SAMPLES,
) -> DriftReport:
    labeled = [row for row in predictions if row.actual_value_when_known is not None]
    mode_counts: Counter[str] = Counter()
    absolute_errors: list[float] = []
    signed_errors: list[float] = []
    row_references: list[float] = []
    for row in labeled:
        signed = float(row.predicted_value) - float(row.actual_value_when_known)
        signed_errors.append(signed)
        absolute_errors.append(abs(signed))
        fallback = abs(float(row.predicted_value) - float(row.deterministic_value)) < 1e-9
        mode = "DETERMINISTIC_FALLBACK" if fallback else "ML_PRODUCTION"
        mode_counts[mode] += 1
        reference = deterministic_reference_mae if fallback else ml_reference_mae
        if isinstance(reference, (int, float)) and reference > 0:
            row_references.append(float(reference))

    times = sorted(_as_utc(row.predicted_at) for row in labeled)
    source_line = {
        "canonical_source_type": "DERIVED",
        "parent_source_type": "OPERATOR_INPUT",
        "raw_source_state": "OPERATOR_CONFIRMED_OUTCOMES",
        "transform_name": "prediction_error_drift_monitor",
        "transform_version": "1.0.0",
        "used_record_count": len(labeled),
        "threshold_policy": {
            "watch_mae_ratio": 1.2,
            "drift_mae_ratio": 1.5,
        },
    }
    if len(labeled) < minimum_samples or len(row_references) != len(labeled):
        return DriftReport(
            model_name=model_name,
            model_version=model_version,
            status="INSUFFICIENT_DATA",
            labeled_sample_count=len(labeled),
            minimum_sample_count=minimum_samples,
            window_start=times[0].isoformat() if times else None,
            window_end=times[-1].isoformat() if times else None,
            operational_mode_counts=dict(mode_counts),
            source_line=source_line,
        )

    observed_mae = sum(absolute_errors) / len(absolute_errors)
    observed_bias = sum(signed_errors) / len(signed_errors)
    reference_mae = sum(row_references) / len(row_references)
    ratio = observed_mae / reference_mae
    status = "DRIFT_DETECTED" if ratio > 1.5 else "WATCH" if ratio > 1.2 else "STABLE"
    return DriftReport(
        model_name=model_name,
        model_version=model_version,
        status=status,
        labeled_sample_count=len(labeled),
        minimum_sample_count=minimum_samples,
        observed_mae_minutes=round(observed_mae, 4),
        observed_bias_minutes=round(observed_bias, 4),
        reference_mae_minutes=round(reference_mae, 4),
        mae_ratio=round(ratio, 4),
        window_start=times[0].isoformat(),
        window_end=times[-1].isoformat(),
        operational_mode_counts=dict(mode_counts),
        source_line=source_line,
    )


def build_retraining_readiness(
    predictions: Sequence[Any], drift: DriftReport
) -> RetrainingReadiness:
    labeled = [row for row in predictions if row.actual_value_when_known is not None]
    times = sorted(_as_utc(row.predicted_at) for row in labeled)
    coverage_days = (
        max(1, int((times[-1] - times[0]).total_seconds() // 86400) + 1)
        if times
        else 0
    )
    route_count = len({row.route_id for row in labeled if row.route_id is not None})
    source_counts = Counter(
        str(row.feature_snapshot.get("outcome_data_class", "UNCLASSIFIED"))
        for row in labeled
    )
    gates = {
        "minimum_labeled_outcomes": len(labeled) >= MIN_RETRAINING_LABELS,
        "minimum_coverage_days": coverage_days >= MIN_RETRAINING_COVERAGE_DAYS,
        "minimum_routes": route_count >= MIN_RETRAINING_ROUTES,
        "trusted_operator_confirmed_labels": bool(labeled)
        and set(source_counts) == {"OPERATOR_CONFIRMED"},
        "drift_requires_attention": drift.status in {"WATCH", "DRIFT_DETECTED"},
    }
    if all(gates.values()):
        status = "READY_FOR_MANUAL_REVIEW"
        action = (
            "A qualified reviewer may approve creation of a versioned candidate training run; "
            "promotion remains a separate manual gate."
        )
    elif drift.status == "STABLE" and len(labeled) >= MIN_DRIFT_SAMPLES:
        status = "NOT_NEEDED"
        action = "Current labeled outcomes do not indicate a retraining need. Continue monitoring."
    else:
        status = "NOT_READY"
        action = "Collect additional owner-confirmed outcomes and continue drift monitoring."
    source_line = {
        "canonical_source_type": "DERIVED",
        "parent_source_type": "OPERATOR_INPUT",
        "raw_source_state": "OPERATOR_CONFIRMED_OUTCOMES",
        "transform_name": "manual_retraining_readiness",
        "transform_version": "1.0.0",
        "used_record_count": len(labeled),
    }
    return RetrainingReadiness(
        model_name=drift.model_name,
        model_version=drift.model_version,
        status=status,
        gates=gates,
        evidence={
            "labeled_outcomes": len(labeled),
            "coverage_days": coverage_days,
            "routes": route_count,
            "source_classes": dict(source_counts),
            "drift_status": drift.status,
        },
        recommended_action=action,
        source_line=source_line,
    )
