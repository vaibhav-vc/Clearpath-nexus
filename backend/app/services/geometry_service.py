from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.space_weather import space_weather_service

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


async def fetch_railway_geometry_from_overpass(
    min_lat: float, min_lon: float, max_lat: float, max_lon: float
) -> list[dict[str, Any]]:
    cache_key = f"osm_geometry:{min_lat:.2f}:{min_lon:.2f}:{max_lat:.2f}:{max_lon:.2f}"
    cached = await space_weather_service._cache_get(cache_key)
    if cached:
        return cached

    pad = 0.05
    bbox = f"{min_lat - pad:.4f},{min_lon - pad:.4f},{max_lat + pad:.4f},{max_lon + pad:.4f}"
    query = f"""
[out:json][timeout:25];
(
  way["railway"="rail"]({bbox});
  way["railway"="narrow_gauge"]({bbox});
);
out body;
>;
out skel qt;
    """.strip()

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                OVERPASS_URL,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                content=f"data={httpx.QueryParams({'data': query})['data']}",
            )
            resp.raise_for_status()
            json_data = resp.json()

            elements = json_data.get("elements", [])
            nodes_map: dict[int, list[float]] = {}
            ways: list[dict[str, Any]] = []

            for el in elements:
                if el.get("type") == "node":
                    nodes_map[el["id"]] = [el["lat"], el["lon"]]
                elif el.get("type") == "way":
                    ways.append(el)

            tracks: list[dict[str, Any]] = []
            for w in ways:
                coords = [nodes_map[nid] for nid in w.get("nodes", []) if nid in nodes_map]
                if len(coords) >= 2:
                    tracks.append({"way_id": w["id"], "coordinates": coords})

            await space_weather_service._cache_set(cache_key, tracks, ttl=86400)
            return tracks
    except Exception as exc:
        logger.warning("Overpass geometry fetch failed: %s", exc)
        return []
