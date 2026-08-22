from __future__ import annotations

import hashlib
import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import (
    ExtraTreesRegressor,
    GradientBoostingRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.metrics import mean_absolute_error, mean_squared_error, median_absolute_error, r2_score

from app.services.ml_prediction import FEATURES, FEATURE_SCHEMA_VERSION, deterministic_delay

TARGET = "remaining_delay_minutes"
FORBIDDEN_FEATURES = {"final_arrival_delay", "actual_value_when_known", "error_when_known", TARGET}
# Only labels admitted through a future curated/admin-controlled ingestion path
# may satisfy production evidence gates. The public owner outcome API produces
# OPERATOR_CONFIRMED labels, which remain useful for audit and candidate research
# but are not independently verified operational ground truth.
REAL_CLASSES = {"REAL_LIVE", "REAL_HISTORICAL"}
DATA_CLASSES = REAL_CLASSES | {"OPERATOR_CONFIRMED", "SIMULATED", "SEEDED"}
CANDIDATE_PARAMETERS: dict[str, dict[str, Any]] = {
    "HistGradientBoostingRegressor": {
        "max_iter": 180,
        "learning_rate": 0.06,
        "max_leaf_nodes": 24,
        "random_state": 520,
    },
    "RandomForestRegressor": {
        "n_estimators": 160,
        "max_depth": 12,
        "min_samples_leaf": 3,
        "random_state": 520,
        "n_jobs": 1,
    },
    "ExtraTreesRegressor": {
        "n_estimators": 160,
        "max_depth": 14,
        "min_samples_leaf": 2,
        "max_features": 1.0,
        "random_state": 520,
        "n_jobs": 1,
    },
    "GradientBoostingRegressor": {
        "n_estimators": 180,
        "learning_rate": 0.05,
        "max_depth": 3,
        "min_samples_leaf": 3,
        "loss": "huber",
        "random_state": 520,
    },
}


def candidate_estimators() -> dict[str, Any]:
    return {
        "HistGradientBoostingRegressor": HistGradientBoostingRegressor(
            **CANDIDATE_PARAMETERS["HistGradientBoostingRegressor"]
        ),
        "RandomForestRegressor": RandomForestRegressor(
            **CANDIDATE_PARAMETERS["RandomForestRegressor"]
        ),
        "ExtraTreesRegressor": ExtraTreesRegressor(
            **CANDIDATE_PARAMETERS["ExtraTreesRegressor"]
        ),
        "GradientBoostingRegressor": GradientBoostingRegressor(
            **CANDIDATE_PARAMETERS["GradientBoostingRegressor"]
        ),
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def simulated_rows(count: int = 600, seed: int = 520) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    corridors = [("NGP", "JNPT", 840.0, 11), ("BSL", "JNPT", 430.0, 7), ("KYN", "JNPT", 65.0, 3)]
    rows: list[dict[str, Any]] = []
    for index in range(count):
        origin, destination, distance, segments = corridors[index % len(corridors)]
        timestamp = start + timedelta(minutes=index * 55)
        features = {
            "route_distance": distance + rng.uniform(-12, 12), "segment_count": segments,
            "departure_hour": timestamp.hour, "day_of_week": timestamp.weekday(), "month": timestamp.month,
            "current_delay": max(0, rng.gauss(18, 14)), "journey_progress": rng.uniform(0, 0.92),
            "weather_score": rng.uniform(45, 100), "rainfall": max(0, rng.gauss(2, 4)),
            "temperature": rng.uniform(14, 41), "wind_speed": rng.uniform(1, 38),
            "visibility": rng.uniform(1200, 15000), "corridor_congestion": rng.uniform(5, 85),
            "station_pressure": rng.uniform(5, 90), "historical_delay": rng.uniform(10, 90),
            "schedule_conflicts": rng.randrange(0, 3), "port_pressure": rng.uniform(10, 95),
            "loading_window_delta": rng.uniform(-180, 480), "cargo_weight": rng.uniform(40, 180),
        }
        target = deterministic_delay(features) + rng.gauss(0, 6)
        rows.append({
            "observation_time": timestamp.isoformat(), "data_class": "SIMULATED",
            "route_id": f"sim-route-{index % 9}", "corridor": f"{origin}-{destination}",
            **features, TARGET: round(max(0, target), 2),
        })
    return rows


def validate_dataset(frame: pd.DataFrame) -> None:
    missing = [name for name in ["observation_time", "data_class", *FEATURES, TARGET] if name not in frame.columns]
    if missing:
        raise ValueError(f"dataset missing columns: {', '.join(missing)}")
    leakage = FORBIDDEN_FEATURES.intersection(FEATURES)
    if leakage:
        raise ValueError(f"leakage fields configured as features: {sorted(leakage)}")
    if frame.empty:
        raise ValueError("dataset has no labeled rows")
    if frame[FEATURES + [TARGET]].isna().any().any():
        raise ValueError("numeric feature/target data contains missing values")
    try:
        numeric = frame[FEATURES + [TARGET]].astype(float).to_numpy()
    except (TypeError, ValueError) as exc:
        raise ValueError("features and target must be numeric") from exc
    if not np.isfinite(numeric).all():
        raise ValueError("numeric feature/target data contains non-finite values")
    unknown_classes = sorted(set(frame["data_class"].astype(str)) - DATA_CLASSES)
    if unknown_classes:
        raise ValueError(f"dataset contains unknown data classes: {', '.join(unknown_classes)}")
    parsed = pd.to_datetime(frame["observation_time"], utc=True, errors="coerce")
    if parsed.isna().any():
        raise ValueError("observation_time contains invalid or timezone-ambiguous values")


def dataset_report(frame: pd.DataFrame) -> dict[str, Any]:
    times = pd.to_datetime(frame["observation_time"], utc=True)
    counts = frame["data_class"].value_counts().to_dict()
    return {
        "row_count": int(len(frame)), "real_row_count": int(frame["data_class"].isin(REAL_CLASSES).sum()),
        "simulated_row_count": int(counts.get("SIMULATED", 0)), "seeded_row_count": int(counts.get("SEEDED", 0)),
        "operator_confirmed_row_count": int(counts.get("OPERATOR_CONFIRMED", 0)),
        "start_time": times.min().isoformat(), "end_time": times.max().isoformat(),
        "coverage_days": max(1, int(math.ceil((times.max() - times.min()).total_seconds() / 86400))),
        "routes_count": int(frame["route_id"].nunique()) if "route_id" in frame else 0,
        "corridors_count": int(frame["corridor"].nunique()) if "corridor" in frame else 0,
        "source_classes": {str(key): int(value) for key, value in counts.items()},
        "missing_values": {column: int(value) for column, value in frame.isna().sum().items() if value},
        "target": TARGET,
        "target_distribution": {"min": float(frame[TARGET].min()), "median": float(frame[TARGET].median()), "mean": float(frame[TARGET].mean()), "max": float(frame[TARGET].max())},
    }


def metric_set(y_true, y_pred) -> dict[str, float]:
    return {
        "mae_minutes": round(float(mean_absolute_error(y_true, y_pred)), 4),
        "rmse_minutes": round(float(mean_squared_error(y_true, y_pred) ** 0.5), 4),
        "median_ae_minutes": round(float(median_absolute_error(y_true, y_pred)), 4),
        "r2": round(float(r2_score(y_true, y_pred)), 5),
    }


def promotion_gates(
    report: dict[str, Any], test_data_classes: pd.Series, improvement: float
) -> dict[str, bool]:
    return {
        "minimum_real_rows": report["real_row_count"] >= 1000,
        "minimum_coverage_days": report["coverage_days"] >= 14,
        "minimum_corridors": report["corridors_count"] >= 3,
        "no_synthetic_test_rows": bool(test_data_classes.isin(REAL_CLASSES).all()),
        "beats_deterministic_by_10_pct": improvement >= 10,
        "no_forbidden_feature_leakage": True,
    }


def train(
    frame: pd.DataFrame,
    artifact_root: Path,
    version: str = "1.0.0",
    source_dataset_checksum: str | None = None,
) -> dict[str, Any]:
    validate_dataset(frame)
    ordered = frame.assign(_time=pd.to_datetime(frame["observation_time"], utc=True)).sort_values("_time")
    n = len(ordered)
    train_end = max(1, int(n * 0.70))
    validation_end = max(train_end + 1, int(n * 0.85))
    if validation_end >= n:
        raise ValueError("at least seven chronological rows are required")
    train_frame, validation_frame, test_frame = ordered.iloc[:train_end], ordered.iloc[train_end:validation_end], ordered.iloc[validation_end:]
    x_train, y_train = train_frame[FEATURES], train_frame[TARGET]
    x_validation, y_validation = validation_frame[FEATURES], validation_frame[TARGET]
    x_test, y_test = test_frame[FEATURES], test_frame[TARGET]
    candidates = candidate_estimators()
    validation_metrics = {}
    for name, model in candidates.items():
        model.fit(x_train, y_train)
        validation_metrics[name] = metric_set(y_validation, model.predict(x_validation))
    winner_name = min(
        validation_metrics,
        key=lambda name: (validation_metrics[name]["mae_minutes"], name),
    )
    # Once validation selects the fixed algorithm, refit that algorithm on the
    # combined train+validation development window. The test window remains
    # untouched until this single final evaluation.
    development_frame = ordered.iloc[:validation_end]
    x_development = development_frame[FEATURES]
    y_development = development_frame[TARGET]
    winner = candidate_estimators()[winner_name]
    winner.fit(x_development, y_development)
    ml_test_predictions = winner.predict(x_test)
    test_metrics = metric_set(y_test, ml_test_predictions)
    baseline_predictions = [deterministic_delay({name: float(row[name]) for name in FEATURES}) for _, row in test_frame.iterrows()]
    baseline_metrics = metric_set(y_test, baseline_predictions)
    improvement = 100 * (baseline_metrics["mae_minutes"] - test_metrics["mae_minutes"]) / max(baseline_metrics["mae_minutes"], 1e-9)
    report = dataset_report(ordered)
    test_has_untrusted_labels = bool(
        (~test_frame["data_class"].isin(REAL_CLASSES)).any()
    )
    calibration_source_types = {
        str(key): int(value)
        for key, value in test_frame["data_class"].value_counts().to_dict().items()
    }
    uncertainty = {
        "method": "HELD_OUT_ABSOLUTE_RESIDUAL_QUANTILE",
        "nominal_coverage": 0.90,
        "calibration_rows": int(len(test_frame)),
        "calibration_source_types": calibration_source_types,
        "trusted_operational_calibration": (
            len(test_frame) >= 30 and not test_has_untrusted_labels
        ),
        "ml_absolute_error_p90": round(
            float(np.quantile(np.abs(y_test.to_numpy() - ml_test_predictions), 0.90)),
            4,
        ),
        "deterministic_absolute_error_p90": round(
            float(
                np.quantile(
                    np.abs(y_test.to_numpy() - np.asarray(baseline_predictions)), 0.90
                )
            ),
            4,
        ),
    }
    gates = promotion_gates(report, test_frame["data_class"], improvement)
    eligible = all(gates.values())
    # Passing objective gates makes a model eligible for promotion; it does not
    # silently authorize a newly written pickle for operational decisions.
    status = "CANDIDATE"
    model_dir = artifact_root / "delay_predictor" / version
    model_dir.mkdir(parents=True, exist_ok=True)
    artifact = model_dir / "model.joblib"
    joblib.dump(winner, artifact)
    checksum = sha256_file(artifact)
    bounds = {
        name: [float(x_development[name].min()), float(x_development[name].max())]
        for name in FEATURES
    }
    metrics = {
        "winner": winner_name, "validation": validation_metrics, "test": test_metrics,
        "deterministic_baseline_test": baseline_metrics, "mae_improvement_pct": round(improvement, 2),
        "selection_metric": "validation_mae_minutes",
        "candidates_evaluated": len(candidates),
        "test_evaluations": 1,
        "winner_refit_on_train_and_validation": True,
        "candidate_parameters": CANDIDATE_PARAMETERS,
        "split": {"train_rows": len(train_frame), "validation_rows": len(validation_frame), "test_rows": len(test_frame),
                  "winner_fit_rows": len(development_frame),
                  "train_end": train_frame["_time"].max().isoformat(), "validation_end": validation_frame["_time"].max().isoformat(), "test_end": test_frame["_time"].max().isoformat()},
    }
    metrics_path = model_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    benchmark_checksum = hashlib.sha256(
        json.dumps(
            {
                "candidate_parameters": CANDIDATE_PARAMETERS,
                "validation": validation_metrics,
                "selection_metric": metrics["selection_metric"],
                "winner": winner_name,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    metadata = {
        "model_name": "delay_predictor", "version": version, "status": status,
        "production": False, "algorithm": winner_name,
        "artifact_path": str(artifact.relative_to(artifact_root)).replace("\\", "/"),
        "artifact_checksum": checksum,
        "metrics_path": str(metrics_path.relative_to(artifact_root)).replace("\\", "/"),
        "feature_schema_version": FEATURE_SCHEMA_VERSION, "feature_list": FEATURES,
        "feature_bounds": bounds, "target": TARGET, "dataset": report,
        "source_dataset_checksum": source_dataset_checksum,
        "benchmark_checksum": benchmark_checksum,
        "winner_parameters": CANDIDATE_PARAMETERS[winner_name],
        "metrics": metrics, "uncertainty": uncertainty,
        "eligibility": {"eligible": eligible, "gates": gates},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    metadata_path = model_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    metadata_checksum = sha256_file(metadata_path)
    metadata_checksum_path = model_dir / "metadata.sha256"
    metadata_checksum_path.write_text(f"{metadata_checksum}\n", encoding="utf-8")
    metadata["metadata_checksum"] = metadata_checksum
    metadata["metadata_checksum_path"] = str(
        metadata_checksum_path.relative_to(artifact_root)
    ).replace("\\", "/")
    metadata["metrics_checksum"] = sha256_file(metrics_path)
    latest_candidate = artifact_root / "delay_predictor" / "latest_candidate.json"
    latest_candidate.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata
