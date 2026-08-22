from __future__ import annotations

import argparse
import json
from pathlib import Path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", default="artifacts/models/delay_predictor/1.0.0/metrics.json")
    args = parser.parse_args()
    metrics = json.loads(Path(args.metrics).read_text(encoding="utf-8"))
    print(json.dumps(metrics, indent=2))
