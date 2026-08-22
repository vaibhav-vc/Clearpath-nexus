from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.ml_prediction import REQUIRED_PROMOTION_GATES  # noqa: E402


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Promote only a gate-eligible candidate.")
    parser.add_argument(
        "--manifest", default="artifacts/models/delay_predictor/latest_candidate.json"
    )
    parser.add_argument("--artifact-root", default="artifacts/models")
    args = parser.parse_args()
    path = Path(args.manifest).resolve()
    artifact_root = Path(args.artifact_root).resolve()
    metadata = json.loads(path.read_text(encoding="utf-8"))
    gates = metadata.get("eligibility", {}).get("gates", {})
    missing = sorted(REQUIRED_PROMOTION_GATES - set(gates))
    failed = [name for name, passed in gates.items() if passed is not True]
    if missing or failed:
        reasons = [*(f"missing:{name}" for name in missing), *failed]
        raise SystemExit(f"Promotion denied; failed gates: {', '.join(reasons)}")
    artifact = (artifact_root / metadata["artifact_path"]).resolve()
    if artifact_root != artifact and artifact_root not in artifact.parents:
        raise SystemExit("Promotion denied; artifact is outside the configured root")
    if not artifact.is_file():
        raise SystemExit("Promotion denied; artifact is missing")
    checksum = hashlib.sha256(artifact.read_bytes()).hexdigest()
    if checksum != metadata.get("artifact_checksum"):
        raise SystemExit("Promotion denied; artifact checksum mismatch")
    metadata["status"] = "PRODUCTION"
    metadata["production"] = True
    version_metadata = artifact.parent / "metadata.json"
    version_metadata.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    production_manifest = artifact_root / metadata["model_name"] / "latest.json"
    production_manifest.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print("Model promoted to PRODUCTION")
