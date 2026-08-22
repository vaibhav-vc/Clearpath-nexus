from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.services.live_data import PROVIDERS  # noqa: E402


def result_from_envelope(envelope) -> dict:
    connectivity = "PASS" if envelope.status not in {"UNAVAILABLE", "RATE_LIMITED"} else envelope.status
    return {
        "provider": envelope.provider_label,
        "configured": True,
        "connectivity": connectivity,
        "parsing": "PASS" if envelope.quality.valid else "FAIL",
        "timestamp": "PASS" if envelope.observed_at else "FAIL",
        "freshness": envelope.freshness,
        "cache": "HIT" if envelope.cache_hit else "MISS",
        "sourceline": "PASS" if envelope.provider_key and envelope.request_id else "FAIL",
        "limitations": envelope.limitations,
    }


async def run() -> list[dict]:
    open_meteo, noaa = await asyncio.gather(
        PROVIDERS["open_meteo"].fetch(
            {"location": {"latitude": 21.1458, "longitude": 79.0882}}
        ),
        PROVIDERS["noaa_swpc"].fetch({}),
    )
    results = [result_from_envelope(open_meteo), result_from_envelope(noaa)]
    results.append(
        {
            "provider": "RailRadar",
            "configured": bool(settings.RAILRADAR_API_KEY),
            "connectivity": "NOT_RUN" if settings.RAILRADAR_API_KEY else "SKIPPED_NOT_CONFIGURED",
            "authentication": "CONFIGURED" if settings.RAILRADAR_API_KEY else "AUTH_REQUIRED",
            "authority": "SECONDARY_NON_OFFICIAL_PASSENGER_SIGNAL",
        }
    )
    results.append(
        {
            "provider": "AISstream",
            "configured": bool(settings.AISSTREAM_API_KEY),
            "connectivity": "NOT_RUN" if settings.AISSTREAM_API_KEY else "SKIPPED_NOT_CONFIGURED",
            "authentication": "CONFIGURED" if settings.AISSTREAM_API_KEY else "AUTH_REQUIRED",
            "limitation": "AIS activity is not a verified berth loading schedule.",
        }
    )
    return results


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run()), indent=2))
