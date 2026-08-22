from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="artifacts/openapi-v6.0.json")
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    output.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output.resolve()),
                "version": schema["info"]["version"],
                "paths": len(schema["paths"]),
            }
        )
    )
