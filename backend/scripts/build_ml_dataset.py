from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import and_, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.ml_pipeline import FEATURES, TARGET, dataset_report, simulated_rows, validate_dataset  # noqa: E402
from app.models.ml import MLDataset, MLPrediction  # noqa: E402
from app.models.route import GeneratedRoute  # noqa: E402


def corridor_for_prediction(prediction, route) -> str:
    if (
        route is None
        or route.id != prediction.route_id
        or route.user_id != prediction.user_id
        or not route.source_station_code
        or not route.dest_station_code
    ):
        return "unassigned"
    return f"{route.source_station_code.upper()}-{route.dest_station_code.upper()}"


async def labeled_research_rows() -> list[dict]:
    rows: list[dict] = []
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(MLPrediction, GeneratedRoute)
            .outerjoin(
                GeneratedRoute,
                and_(
                    GeneratedRoute.id == MLPrediction.route_id,
                    GeneratedRoute.user_id == MLPrediction.user_id,
                ),
            )
            .where(MLPrediction.actual_value_when_known.is_not(None))
        )
        for prediction, route in result.all():
            if not all(name in prediction.feature_snapshot for name in FEATURES):
                continue
            rows.append(
                {
                    "observation_time": prediction.predicted_at.isoformat(),
                    "data_class": prediction.feature_snapshot.get(
                        "outcome_data_class", "OPERATOR_CONFIRMED"
                    ),
                    "route_id": str(prediction.route_id or "unassigned"),
                    "corridor": corridor_for_prediction(prediction, route),
                    **{name: prediction.feature_snapshot[name] for name in FEATURES},
                    TARGET: prediction.actual_value_when_known,
                }
            )
    return rows


async def run(args) -> None:
    collected = await labeled_research_rows()
    if args.include_simulated:
        collected.extend(simulated_rows(args.simulated_rows))
    frame = pd.DataFrame(collected)
    validate_dataset(frame)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)
    checksum = hashlib.sha256(output.read_bytes()).hexdigest()
    report = dataset_report(frame)
    report.update({"dataset_version": args.version, "checksum": checksum, "file_reference": str(output)})
    report_path = output.with_suffix(".report.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.register:
        async with AsyncSessionLocal() as db:
            existing = await db.scalar(select(MLDataset).where(MLDataset.dataset_version == args.version))
            if existing is None:
                db.add(MLDataset(
                    dataset_version=args.version,
                    start_time=datetime.fromisoformat(report["start_time"]), end_time=datetime.fromisoformat(report["end_time"]),
                    row_count=report["row_count"], real_row_count=report["real_row_count"],
                    simulated_row_count=report["simulated_row_count"], seeded_row_count=report["seeded_row_count"],
                    routes_count=report["routes_count"], corridors_count=report["corridors_count"],
                    feature_schema={"version": "delay_features_v1", "features": FEATURES}, target=TARGET,
                    source_summary=report["source_classes"], checksum=checksum,
                    file_reference=str(output), status="READY",
                ))
                await db.commit()
    print(json.dumps(report, indent=2))
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="artifacts/datasets/delay_dataset_v1.csv")
    parser.add_argument("--version", default="delay_dataset_v1")
    parser.add_argument("--include-simulated", action="store_true")
    parser.add_argument("--simulated-rows", type=int, default=600)
    parser.add_argument("--register", action="store_true")
    asyncio.run(run(parser.parse_args()))
