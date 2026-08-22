from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml_pipeline import sha256_file, train  # noqa: E402
from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.models.ml import MLDataset, MLModelVersion, MLTrainingRun  # noqa: E402


async def register(metadata: dict, dataset_version: str) -> None:
    try:
        async with AsyncSessionLocal() as db:
            dataset = await db.scalar(
                select(MLDataset).where(MLDataset.dataset_version == dataset_version)
            )
            if dataset is None:
                raise RuntimeError("Dataset must be registered before the training run")
            existing = await db.scalar(
                select(MLModelVersion).where(
                    MLModelVersion.model_name == metadata["model_name"],
                    MLModelVersion.version == metadata["version"],
                )
            )
            if existing is not None:
                return
            now = datetime.now(timezone.utc)
            run = MLTrainingRun(
                model_name=metadata["model_name"],
                training_started_at=now,
                training_finished_at=now,
                dataset_id=dataset.id,
                algorithm=metadata["algorithm"],
                parameters=metadata.get("winner_parameters", {}),
                feature_list=metadata["feature_list"],
                target=metadata["target"],
                training_metrics={
                    "benchmark_checksum": metadata.get("benchmark_checksum"),
                    "selection_metric": metadata["metrics"].get("selection_metric"),
                    "candidates_evaluated": metadata["metrics"].get(
                        "candidates_evaluated"
                    ),
                },
                validation_metrics=metadata["metrics"]["validation"],
                test_metrics=metadata["metrics"]["test"],
                deterministic_baseline_metrics=metadata["metrics"][
                    "deterministic_baseline_test"
                ],
                artifact_path=metadata["artifact_path"],
                artifact_checksum=metadata["artifact_checksum"],
                status="COMPLETED",
                promotion_status=metadata["status"],
            )
            db.add(run)
            await db.flush()
            db.add(
                MLModelVersion(
                    id=uuid.uuid4(),
                    model_name=metadata["model_name"],
                    version=metadata["version"],
                    algorithm=metadata["algorithm"],
                    training_run_id=run.id,
                    status=metadata["status"],
                    artifact_path=metadata["artifact_path"],
                    artifact_checksum=metadata["artifact_checksum"],
                    metadata_path=f"delay_predictor/{metadata['version']}/metadata.json",
                    feature_schema_version=metadata["feature_schema_version"],
                    production=metadata["production"],
                )
            )
            await db.commit()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="artifacts/datasets/delay_dataset_v1.csv")
    parser.add_argument("--artifact-root", default="artifacts/models")
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--dataset-version", default="delay_dataset_v1")
    parser.add_argument("--register", action="store_true")
    args = parser.parse_args()
    dataset_path = Path(args.dataset).resolve()
    metadata = train(
        pd.read_csv(dataset_path),
        Path(args.artifact_root).resolve(),
        args.version,
        source_dataset_checksum=sha256_file(dataset_path),
    )
    if args.register:
        asyncio.run(register(metadata, args.dataset_version))
    print(json.dumps(metadata, indent=2))
