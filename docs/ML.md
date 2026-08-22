# Delay / ETA predictive intelligence

The v5.3 target is `remaining_delay_minutes`. It is a tabular, time-aware regression problem; no LLM is trained or treated as an operational fact source.

## Features and leakage controls

The v1 schema uses only information available at inference time: route distance, segment count, departure time fields, current delay, journey progress, weather score, rainfall, temperature, wind, visibility, congestion, station pressure, historical delay, schedule conflicts, port pressure, loading-window delta, and cargo weight.

The builder rejects missing numeric inputs and ambiguous timestamps. `remaining_delay_minutes`, final arrival delay, known actual outcome, and stored prediction error are forbidden as features. Splitting is chronological: oldest 70% train, next 15% validation, newest 15% untouched test.

## Reproducible pipeline

1. `scripts/build_ml_dataset.py` builds research observations from owner-confirmed prediction outcomes. Corridor identity is joined from the prediction's route only when the generated route has the same owner; it is otherwise `unassigned`. `--include-simulated` adds clearly labelled deterministic development rows.
2. `scripts/train_delay_model.py` benchmarks fixed CPU-safe configurations of `HistGradientBoostingRegressor`, `RandomForestRegressor`, `ExtraTreesRegressor`, and `GradientBoostingRegressor`. It selects only on validation MAE, evaluates the winner exactly once on the temporal test set, and compares it with the deterministic predictor.
3. `scripts/evaluate_delay_model.py` prints stored metrics.
4. `scripts/promote_model.py` refuses promotion when any gate fails or the artifact checksum/path is invalid. Training writes `latest_candidate.json`; only explicit promotion writes the production-only `latest.json` manifest.

Artifacts live below `backend/artifacts/models/`. Each model version contains `model.joblib`, `metadata.json`, `metadata.sha256`, and `metrics.json`. Metadata records the source-dataset, benchmark, metrics, and winner-artifact SHA-256 checksums. The API loads only artifacts beneath the configured trusted root and verifies the artifact checksum and feature-schema version before deserializing.

The checked-in prepared-dataset benchmark is documented in `docs/ML_BENCHMARK_1_1.md`. It remains a non-production candidate because all 600 labels are simulated and its winning regressor performs worse than the deterministic baseline on the untouched test split.

## Promotion gate

Production requires all of:

- at least 1,000 curated `REAL_LIVE` or `REAL_HISTORICAL` labelled rows admitted through a future admin-controlled path;
- at least 14 days coverage;
- at least three corridors;
- no seeded/simulated rows in the final test set;
- no forbidden leakage;
- at least 10% test MAE improvement over the deterministic baseline.

These are initial engineering gates, not a claim of statistical sufficiency. A successful training run remains `CANDIDATE` when any gate fails. Candidate output is displayed for comparison but does not become the operational ETA.

`OPERATOR_CONFIRMED` labels submitted through the owner API are retained for audit, drift monitoring, and candidate research. They do not increment `real_row_count`, cannot satisfy the production-row gate, and make the held-out-data gate fail. There is currently no curated/admin label-approval endpoint, so user assertions cannot promote a model.

## Inference and SourceLine

`POST /api/v1/predictions/delay` validates the feature schema, loads the checksummed artifact, detects simple out-of-distribution inputs, records the feature snapshot/model version/checksum, persists a prediction, and creates a SourceLine feature-vector → prediction edge.

If the artifact is absent, corrupt, outside the trusted root, schema-incompatible, out of distribution, or raises an inference error, the service returns the deterministic result. Physical clearance and ComplianceGuard decisions remain separate hard gates and are never overridden by ML.

Outcome labels are owner-scoped through `POST /api/v1/predictions/{prediction_id}/outcome`. This creates the future real learning loop without automatic retraining.

## Confidence and local explanation

Inference returns an exact `DETERMINISTIC_DECOMPOSITION_V1` contribution list. When deterministic fallback is operational, the contributions explain the operational value. When an approved ML model is operational, they are explicitly labelled as explaining only the deterministic comparison baseline; they are not presented as SHAP values or as an explanation of the model.

Training stores the 90th percentile absolute residual from the untouched chronological test split for both the ML candidate and deterministic baseline. A numerical interval is returned only when at least 30 held-out labels are entirely curated `REAL_LIVE`/`REAL_HISTORICAL` records. Operator-confirmed, simulated, or missing calibration produces `available: false` with the reason instead of a fabricated confidence range. The interval is an empirical engineering interval, not a probabilistic guarantee.

## Drift and retraining readiness

- `GET /api/v1/models/{model_name}/drift` compares owner-scoped, operator-confirmed outcome MAE with the matching held-out reference MAE. Fewer than 20 labels or missing reference evidence returns `INSUFFICIENT_DATA`.
- `GET /api/v1/models/{model_name}/retraining-readiness` evaluates transparent gates for label count, time coverage, route coverage, trusted classification, and drift. `READY_FOR_MANUAL_REVIEW` authorizes no action by itself.

Both responses expose their calculation method and input classification in a SourceLine-shaped evidence object. There is no automatic training or promotion. A qualified human must deliberately build a versioned dataset, train a candidate, review evaluation evidence, and separately run the promotion gate.
