# Delay benchmark 1.1.0

Run date: 22 August 2026

This is a reproducible development benchmark, not production-model evidence.

## Dataset truth

- Dataset: `backend/artifacts/datasets/delay_dataset_v1.csv`
- Rows: 600
- Classification: 600 `SIMULATED`, 0 curated real, 0 operator-confirmed
- Coverage: 23 days, 9 route identifiers, 3 corridors
- Source dataset SHA-256: `d90d5374fc364204c122f069029e1469c2fbab56b9f1ee8f6b7e52821ed930a3`
- Chronological split: 420 train, 90 validation, 90 untouched test

## Validation-only selection

Four fixed, single-process/CPU-safe candidates were fitted on the training split. The winner was selected only by validation MAE:

- GradientBoostingRegressor: 7.1403 minutes MAE
- HistGradientBoostingRegressor: 7.3320 minutes MAE
- ExtraTreesRegressor: 9.1574 minutes MAE
- RandomForestRegressor: 9.9241 minutes MAE

`GradientBoostingRegressor` won the validation comparison. Its fixed parameters are 180 estimators, learning rate 0.05, depth 3, minimum leaf size 3, Huber loss, and random seed 520.

## One-time test result

After validation selection, the winner was refitted on the combined 510-row train+validation development window. It was then evaluated once on the untouched test split:

- Candidate test MAE: 7.4394 minutes
- Candidate test RMSE: 10.0794 minutes
- Candidate test R²: 0.87909
- Deterministic baseline test MAE: 4.3341 minutes
- Deterministic baseline test RMSE: 5.4330 minutes
- Deterministic baseline test R²: 0.96487
- Candidate MAE improvement versus deterministic baseline: -71.65%

The deterministic engine is materially better on this synthetic dataset. The result is retained instead of tuning against the test set or hiding the unfavorable comparison.

## Artifact evidence

- Candidate version: `1.1.0-benchmark`
- Status: `CANDIDATE`
- Model artifact SHA-256: `114566c0e3be140b9d38ff9bb95d514a0a46bec92de98811271e1faa872eb0d1`
- Benchmark SHA-256: `a354f12543a1595c291a2c7178ab5d771d0b4e42fdbecf4d174cc1ee013c9a48`
- Metrics SHA-256: `4dc00fbd602b04348675d5cf92d86ce3ece7b89d67940c9be66c85e4c8aafe96`
- Metadata SHA-256: `17281eafc8b7570cd1a5e22d74c098a9df1c4c494d8f6151b71dbd2a1e56b022`

## Why it cannot be promoted

The candidate fails three required gates:

- no curated `REAL_LIVE`/`REAL_HISTORICAL` training rows;
- simulated rows are present in the test split;
- it does not beat the deterministic baseline by 10% (it is worse).

Its 90-row residual calibration is also simulated, so no operational confidence interval is claimed. The deterministic predictor remains the operational fallback. Promotion stays manual and the promotion script will reject this candidate.
