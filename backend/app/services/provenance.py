from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provenance import LineageEdge, ProvenanceRecord, RouteDecisionSnapshot
from app.schemas.provenance import (
    DecisionUseCounts,
    FreshnessCounts,
    ProvenanceSummary,
    SourceModeCounts,
    TraceabilityCounts,
)


class CanonicalSourceType(str, Enum):
    LIVE_PROVIDER = "LIVE_PROVIDER"
    PUBLIC_OPEN_DATA = "PUBLIC_OPEN_DATA"
    CACHED_PROVIDER = "CACHED_PROVIDER"
    OPERATOR_INPUT = "OPERATOR_INPUT"
    SEEDED_BASELINE = "SEEDED_BASELINE"
    DERIVED = "DERIVED"
    SIMULATED = "SIMULATED"
    OFFLINE_COMPUTED = "OFFLINE_COMPUTED"
    IMPORTED_DOCUMENT = "IMPORTED_DOCUMENT"
    UNAVAILABLE = "UNAVAILABLE"


class FreshnessState(str, Enum):
    FRESH = "FRESH"
    AGING = "AGING"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class AvailabilityState(str, Enum):
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    UNKNOWN = "UNKNOWN"


class LineageRelationship(str, Enum):
    INPUT_TO = "INPUT_TO"
    DERIVED_FROM = "DERIVED_FROM"
    OVERRIDES = "OVERRIDES"
    EXCLUDED_FROM = "EXCLUDED_FROM"
    VALIDATES = "VALIDATES"
    REFERENCES = "REFERENCES"
    FALLBACK_FOR = "FALLBACK_FOR"


SOURCE_IDS = {
    "open_meteo": uuid.UUID("10000000-0000-0000-0000-000000000001"),
    "openweather": uuid.UUID("10000000-0000-0000-0000-000000000002"),
    "noaa_swpc": uuid.UUID("10000000-0000-0000-0000-000000000003"),
    "operator_input": uuid.UUID("10000000-0000-0000-0000-000000000004"),
    "demo_engineering": uuid.UUID("10000000-0000-0000-0000-000000000005"),
    "route_baseline": uuid.UUID("10000000-0000-0000-0000-000000000006"),
    "railradar": uuid.UUID("10000000-0000-0000-0000-000000000007"),
    "aisstream": uuid.UUID("10000000-0000-0000-0000-000000000008"),
    "maritime_feed": uuid.UUID("10000000-0000-0000-0000-000000000009"),
    "clearpath_derived": uuid.UUID("10000000-0000-0000-0000-000000000010"),
    "ixigo_partner": uuid.UUID("10000000-0000-0000-0000-000000000012"),
}

FRESHNESS_POLICIES = {
    "open_meteo": (900, 1800, 3600),
    "openweather": (900, 1800, 3600),
    "noaa_swpc": (900, 1800, 3600),
    "railradar": (7200, 10800, 21600),
    "aisstream": (300, 600, 1200),
    "maritime_feed": (900, 1800, 3600),
    "ixigo_partner": (300, 900, 1800),
}

DECISION_INPUT_ROLES = {
    "CLEARANCE_DECISION",
    "WEATHER",
    "PORT_ALIGNMENT",
    "CONGESTION",
    "HISTORICAL_DELAY",
}

SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "jwt",
    "password",
    "secret",
    "service_role",
    "api_key",
    "access_token",
    "refresh_token",
    "database_url",
    "connection_string",
}


def normalize_source_state(raw_state: str | None) -> CanonicalSourceType:
    normalized = (raw_state or "").upper()
    if normalized in {"LIVE", "LIVE_AIS", "LIVE_FEED"}:
        return CanonicalSourceType.LIVE_PROVIDER
    if normalized in {"CACHED", "STALE_AIS"}:
        return CanonicalSourceType.CACHED_PROVIDER
    if normalized in {"OPERATOR_INPUT", "OPERATOR_DECLARED"}:
        return CanonicalSourceType.OPERATOR_INPUT
    if normalized in {"SEEDED", "SEEDED_BASELINE", "STATIC_ONLY", "DEMO_SCHEDULED"}:
        return CanonicalSourceType.SEEDED_BASELINE
    if normalized in {"SIMULATED"}:
        return CanonicalSourceType.SIMULATED
    if normalized in {"OFFLINE", "OFFLINE_COMPUTED"}:
        return CanonicalSourceType.OFFLINE_COMPUTED
    if normalized in {"UNAVAILABLE", "NOT_CONFIGURED", "PROVIDER-UNAVAILABLE"}:
        return CanonicalSourceType.UNAVAILABLE
    return CanonicalSourceType.DERIVED


def calculate_freshness(
    source_key: str,
    observed_at: datetime | None,
    fetched_at: datetime,
    now: datetime | None = None,
) -> tuple[FreshnessState, int | None]:
    if source_key in {"operator_input", "demo_engineering", "route_baseline", "clearpath_derived"}:
        return FreshnessState.NOT_APPLICABLE, None
    if observed_at is None:
        return FreshnessState.UNKNOWN, None
    now = now or datetime.now(timezone.utc)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    age = max(0, int((now - observed_at).total_seconds()))
    fresh, aging, stale = FRESHNESS_POLICIES.get(source_key, (900, 1800, 3600))
    if age <= fresh:
        return FreshnessState.FRESH, age
    if age <= aging:
        return FreshnessState.AGING, age
    if age > stale:
        return FreshnessState.STALE, age
    return FreshnessState.AGING, age


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (datetime, uuid.UUID, Decimal, Enum)):
        return str(value.value if isinstance(value, Enum) else value)
    if isinstance(value, float):
        return round(value, 6)
    return value


def redact_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(sensitive in lowered for sensitive in SENSITIVE_KEYS):
                clean[str(key)] = "[REDACTED]"
            else:
                clean[str(key)] = redact_metadata(item)
        return clean
    if isinstance(value, list):
        return [redact_metadata(item) for item in value]
    return _json_safe(value)


def stable_checksum(value: Any) -> str:
    safe = redact_metadata(value)
    canonical = json.dumps(safe, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _record(
    *,
    user_id: str,
    route_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    source_key: str,
    entity_type: str,
    entity_key: str,
    source_type: CanonicalSourceType,
    raw_state: str,
    value: dict,
    request_id: str | None,
    role: str | None = None,
    observed_at: datetime | None = None,
    fetched_at: datetime | None = None,
    used: bool = False,
    excluded_reason: str | None = None,
    availability: AvailabilityState = AvailabilityState.AVAILABLE,
    transform_name: str | None = None,
    transform_version: str | None = None,
    formula_reference: str | None = None,
    metadata: dict | None = None,
) -> ProvenanceRecord:
    fetched_at = fetched_at or datetime.now(timezone.utc)
    freshness, age = calculate_freshness(source_key, observed_at, fetched_at)
    safe_value = redact_metadata(value)
    safe_metadata = redact_metadata(metadata or {})
    return ProvenanceRecord(
        id=uuid.uuid4(),
        user_id=user_id,
        route_id=route_id,
        decision_snapshot_id=snapshot_id,
        source_id=SOURCE_IDS[source_key],
        entity_type=entity_type,
        entity_key=entity_key,
        decision_input_role=role,
        canonical_source_type=source_type.value,
        raw_source_state=raw_state,
        observed_at=observed_at,
        fetched_at=fetched_at,
        freshness_state=freshness.value,
        freshness_seconds=age,
        cache_hit=source_type is CanonicalSourceType.CACHED_PROVIDER,
        used_in_decision=used,
        excluded_reason=excluded_reason,
        availability_state=availability.value,
        completeness=1.0 if safe_value else 0.0,
        transform_name=transform_name,
        transform_version=transform_version,
        formula_reference=formula_reference,
        request_id=request_id,
        checksum=stable_checksum(safe_value),
        value_summary=safe_value,
        metadata_json=safe_metadata,
    )


def calculate_traceability_summary(
    records: list[ProvenanceRecord],
    snapshot_id: uuid.UUID,
    warnings: list[str] | None = None,
) -> ProvenanceSummary:
    traced_roles = {
        record.decision_input_role
        for record in records
        if record.decision_input_role in DECISION_INPUT_ROLES
        and record.fetched_at is not None
        and bool(record.value_summary)
        and (record.source_id is not None or record.canonical_source_type == "UNAVAILABLE")
    }
    total = len(DECISION_INPUT_ROLES)
    traced = len(traced_roles)

    freshness = FreshnessCounts()
    source_modes = SourceModeCounts()
    use = DecisionUseCounts()
    for record in records:
        freshness_key = record.freshness_state.lower()
        if hasattr(freshness, freshness_key):
            setattr(freshness, freshness_key, getattr(freshness, freshness_key) + 1)
        source_key = record.canonical_source_type.lower()
        if hasattr(source_modes, source_key):
            setattr(source_modes, source_key, getattr(source_modes, source_key) + 1)
        decision_use = record.metadata_json.get("decision_use")
        if decision_use and hasattr(use, decision_use):
            setattr(use, decision_use, getattr(use, decision_use) + 1)
        elif record.used_in_decision:
            use.included += 1
        elif record.excluded_reason:
            use.excluded += 1
        else:
            use.informational += 1

    return ProvenanceSummary(
        decision_record_id=snapshot_id,
        traceability=TraceabilityCounts(
            traced=traced,
            total=total,
            coverage_pct=round((traced / total * 100.0) if total else 100.0, 1),
        ),
        freshness=freshness,
        source_modes=source_modes,
        decision_use=use,
        warnings=list(dict.fromkeys(warnings or [])),
    )


async def capture_route_decision(
    db: AsyncSession,
    *,
    route: Any,
    user_id: str,
    request_id: str | None,
    cargo: dict[str, float],
    segments: list[Any],
    clearance: dict[str, Any],
    weather_data: dict[str, Any],
    kp_data: dict[str, Any],
    weather_score: float,
    port_sync: Any,
    congestion: Any,
    historical_score: float,
    reliability: int,
    estimated_hours: float | None,
    applied_weights: dict[str, float],
    alerts: list[str],
) -> ProvenanceSummary:
    """Persist one immutable evidence set in the caller's route transaction."""
    now = datetime.now(timezone.utc)
    snapshot_id = uuid.uuid4()
    route_id = route.id
    key = f"route:{route_id}"
    warnings = [
        "Engineering clearance values are seeded demonstration data and are not certified railway engineering data.",
        "Static congestion and historical-delay values are seeded operational baselines.",
    ]
    records: list[ProvenanceRecord] = []
    edges: list[LineageEdge] = []

    cargo_record = _record(
        user_id=user_id,
        route_id=route_id,
        snapshot_id=snapshot_id,
        source_key="operator_input",
        entity_type="CARGO_DECLARATION",
        entity_key=f"{key}:cargo",
        source_type=CanonicalSourceType.OPERATOR_INPUT,
        raw_state="OPERATOR_INPUT",
        value=cargo,
        request_id=request_id,
        used=True,
        metadata={"decision_use": "hard_constraints"},
    )
    engineering_value = {
        "segments": [
            {
                "id": str(s.id),
                "max_height": float(s.max_height_clearance),
                "max_width": float(s.max_width_clearance),
                "max_weight": float(s.max_weight_capacity),
            }
            for s in segments
        ],
        "certification": "DEMONSTRATION_DATA_NOT_CERTIFIED",
    }
    engineering_record = _record(
        user_id=user_id,
        route_id=route_id,
        snapshot_id=snapshot_id,
        source_key="demo_engineering",
        entity_type="ENGINEERING_LIMITS",
        entity_key=f"{key}:engineering",
        source_type=CanonicalSourceType.SEEDED_BASELINE,
        raw_state="SEEDED_BASELINE",
        value=engineering_value,
        request_id=request_id,
        used=True,
        metadata={"decision_use": "hard_constraints"},
    )
    clearance_record = _record(
        user_id=user_id,
        route_id=route_id,
        snapshot_id=snapshot_id,
        source_key="clearpath_derived",
        entity_type="CLEARANCE_RESULT",
        entity_key=f"{key}:clearance",
        source_type=CanonicalSourceType.DERIVED,
        raw_state="DERIVED",
        value={
            "status": clearance["status"],
            "blocking_segment_id": clearance.get("blocking_segment_id"),
        },
        request_id=request_id,
        role="CLEARANCE_DECISION",
        used=True,
        transform_name="cargo_clearance",
        transform_version="1.0.0",
        formula_reference="CLEARANCE_HEIGHT_WIDTH_WEIGHT_V1",
        metadata={"decision_use": "hard_constraints"},
    )
    records.extend([cargo_record, engineering_record, clearance_record])
    edges.extend(
        [
            LineageEdge(
                parent_record_id=cargo_record.id,
                child_record_id=clearance_record.id,
                relationship="INPUT_TO",
            ),
            LineageEdge(
                parent_record_id=engineering_record.id,
                child_record_id=clearance_record.id,
                relationship="VALIDATES",
            ),
        ]
    )

    weather_meta = weather_data.get("_provenance", {}) if isinstance(weather_data, dict) else {}
    weather_unavailable = weather_data.get("status") == "unavailable"
    weather_provider = weather_meta.get("provider") or (
        "openweather" if weather_meta.get("adapter") == "openweather" else "open_meteo"
    )
    weather_raw_state = weather_meta.get("raw_state") or (
        "UNAVAILABLE" if weather_unavailable else "LIVE"
    )
    weather_type = normalize_source_state(weather_raw_state)
    weather_observed = _parse_time(weather_meta.get("observed_at"))
    weather_fetched = _parse_time(weather_meta.get("fetched_at")) or now
    raw_weather = _record(
        user_id=user_id,
        route_id=route_id,
        snapshot_id=snapshot_id,
        source_key=weather_provider,
        entity_type="WEATHER_OBSERVATION",
        entity_key=f"{key}:weather-observation",
        source_type=weather_type,
        raw_state=weather_raw_state,
        value={k: v for k, v in weather_data.items() if k != "_provenance"},
        request_id=request_id,
        observed_at=weather_observed,
        fetched_at=weather_fetched,
        used=not weather_unavailable,
        excluded_reason="Provider unavailable; deterministic weather fallback used"
        if weather_unavailable
        else None,
        availability=AvailabilityState.UNAVAILABLE
        if weather_unavailable
        else AvailabilityState.AVAILABLE,
        metadata={"decision_use": "excluded" if weather_unavailable else "included"},
    )
    weather_score_record = _record(
        user_id=user_id,
        route_id=route_id,
        snapshot_id=snapshot_id,
        source_key="clearpath_derived",
        entity_type="WEATHER_SCORE",
        entity_key=f"{key}:weather-score",
        source_type=CanonicalSourceType.DERIVED,
        raw_state="FALLBACK" if weather_unavailable else "DERIVED",
        value={
            "score": weather_score,
            "provider_unavailable_fallback": weather_unavailable,
            "weight": applied_weights.get("weather"),
        },
        request_id=request_id,
        role="WEATHER",
        used=True,
        transform_name="weather_to_score",
        transform_version="1.0.0",
        formula_reference="RRI_WEATHER_V1",
        metadata={"decision_use": "fallbacks" if weather_unavailable else "included"},
    )
    records.extend([raw_weather, weather_score_record])
    edges.append(
        LineageEdge(
            parent_record_id=raw_weather.id,
            child_record_id=weather_score_record.id,
            relationship="FALLBACK_FOR" if weather_unavailable else "DERIVED_FROM",
        )
    )
    if weather_unavailable:
        warnings.append(
            "Weather provider unavailable; deterministic 50-point fallback affected RRI."
        )

    kp_unavailable = kp_data.get("status") == "unavailable"
    kp_meta = kp_data.get("_provenance", {}) if isinstance(kp_data, dict) else {}
    kp_record = _record(
        user_id=user_id,
        route_id=route_id,
        snapshot_id=snapshot_id,
        source_key="noaa_swpc",
        entity_type="SPACE_WEATHER_OBSERVATION",
        entity_key=f"{key}:space-weather",
        source_type=normalize_source_state(
            kp_meta.get("raw_state") or ("UNAVAILABLE" if kp_unavailable else "LIVE")
        ),
        raw_state=kp_meta.get("raw_state") or ("UNAVAILABLE" if kp_unavailable else "LIVE"),
        value={"kp_index": kp_data.get("kp_index"), "alert_level": kp_data.get("alert_level")},
        request_id=request_id,
        observed_at=_parse_time(kp_data.get("issue_datetime")),
        fetched_at=_parse_time(kp_meta.get("fetched_at")) or now,
        used=not kp_unavailable,
        excluded_reason="NOAA feed unavailable; telemetry risk unknown" if kp_unavailable else None,
        availability=AvailabilityState.UNAVAILABLE
        if kp_unavailable
        else AvailabilityState.AVAILABLE,
        metadata={"decision_use": "informational" if kp_unavailable else "included"},
    )
    records.append(kp_record)
    edges.append(
        LineageEdge(
            parent_record_id=kp_record.id,
            child_record_id=weather_score_record.id,
            relationship="EXCLUDED_FROM" if kp_unavailable else "INPUT_TO",
        )
    )

    port_source = str(
        port_sync.source.value if hasattr(port_sync.source, "value") else port_sync.source
    )
    port_available = bool(port_sync.available)
    port_source_key = "operator_input" if port_source == "OPERATOR_INPUT" else "maritime_feed"
    port_type = normalize_source_state(port_source if port_available else "UNAVAILABLE")
    port_record = _record(
        user_id=user_id,
        route_id=route_id,
        snapshot_id=snapshot_id,
        source_key=port_source_key,
        entity_type="PORT_ALIGNMENT_SCORE",
        entity_key=f"{key}:port",
        source_type=port_type,
        raw_state=port_source,
        value={
            "score": port_sync.score if port_available else None,
            "available": port_available,
            "aligned": port_sync.aligned,
            "evaluated_at": port_sync.evaluated_at,
            "train_arrival_hours": port_sync.train_arrival_hours,
            "estimated_train_arrival_at": (
                port_sync.evaluated_at
                + timedelta(hours=port_sync.train_arrival_hours)
                if port_sync.evaluated_at is not None
                and port_sync.train_arrival_hours is not None
                else None
            ),
            "loading_window": {
                "start": port_sync.window.start,
                "end": port_sync.window.end,
            }
            if port_sync.window
            else None,
            "berth_id": port_sync.berth_id,
            "vessel_status": port_sync.vessel_status,
            "weight": applied_weights.get("port"),
        },
        request_id=request_id,
        role="PORT_ALIGNMENT",
        used=port_available,
        excluded_reason=None
        if port_available
        else "No verified berth window; factor excluded and weights renormalized",
        availability=AvailabilityState.AVAILABLE
        if port_available
        else AvailabilityState.NOT_CONFIGURED,
        transform_name="port_sync",
        transform_version="1.0.0",
        formula_reference="PORT_ALIGNMENT_V1",
        metadata={"decision_use": "included" if port_available else "excluded"},
    )
    records.append(port_record)
    if not port_available:
        warnings.append(
            "Port alignment was unavailable and excluded; RRI weights were renormalized."
        )

    static_record = _record(
        user_id=user_id,
        route_id=route_id,
        snapshot_id=snapshot_id,
        source_key="route_baseline",
        entity_type="CONGESTION_BASELINE",
        entity_key=f"{key}:congestion-baseline",
        source_type=CanonicalSourceType.SEEDED_BASELINE,
        raw_state="SEEDED_BASELINE",
        value={
            "score": congestion.static_score,
            "segment_factors": [float(s.congestion_factor) for s in segments],
        },
        request_id=request_id,
        used=True,
        metadata={"decision_use": "included"},
    )
    congestion_parents = [static_record]
    if congestion.live_rail_score is not None:
        rail_state = str(congestion.detail.get("rail_source", "LIVE"))
        congestion_parents.append(
            _record(
                user_id=user_id,
                route_id=route_id,
                snapshot_id=snapshot_id,
                source_key="railradar",
                entity_type="RAIL_CONGESTION_SIGNAL",
                entity_key=f"{key}:rail-congestion",
                source_type=normalize_source_state(rail_state),
                raw_state=rail_state,
                value={
                    "score": congestion.live_rail_score,
                    "stations_live": congestion.detail.get("stations_live"),
                    "stations_total": congestion.detail.get("stations_total"),
                },
                request_id=request_id,
                observed_at=_parse_time(congestion.detail.get("rail_observed_at")),
                fetched_at=_parse_time(congestion.detail.get("rail_fetched_at")) or now,
                used=True,
                metadata={
                    "decision_use": "included",
                    "authority": "SECONDARY_NON_OFFICIAL_PASSENGER",
                },
            )
        )
    if congestion.port_congestion_pct is not None:
        ais_state = str(congestion.detail.get("port_source") or "UNAVAILABLE")
        congestion_parents.append(
            _record(
                user_id=user_id,
                route_id=route_id,
                snapshot_id=snapshot_id,
                source_key="aisstream",
                entity_type="AIS_PORT_ACTIVITY",
                entity_key=f"{key}:ais",
                source_type=normalize_source_state(ais_state),
                raw_state=ais_state,
                value={
                    "congestion_pct": congestion.port_congestion_pct,
                    "penalty": congestion.port_penalty,
                },
                request_id=request_id,
                observed_at=_parse_time(congestion.detail.get("port_observed_at")),
                used=True,
                metadata={
                    "decision_use": "included",
                    "limitation": "AIS activity is not a berth schedule",
                },
            )
        )
    congestion_record = _record(
        user_id=user_id,
        route_id=route_id,
        snapshot_id=snapshot_id,
        source_key="clearpath_derived",
        entity_type="CONGESTION_SCORE",
        entity_key=f"{key}:congestion",
        source_type=CanonicalSourceType.DERIVED,
        raw_state=str(congestion.source.value),
        value={
            "score": congestion.score,
            "static_score": congestion.static_score,
            "live_rail_score": congestion.live_rail_score,
            "live_weight": congestion.live_weight,
            "port_penalty": congestion.port_penalty,
            "weight": applied_weights.get("congestion"),
        },
        request_id=request_id,
        role="CONGESTION",
        used=True,
        transform_name="congestion_blend",
        transform_version="1.0.0",
        formula_reference="CONGESTION_BLEND_V1",
        metadata={"decision_use": "included"},
    )
    records.extend(congestion_parents + [congestion_record])
    edges.extend(
        LineageEdge(
            parent_record_id=p.id, child_record_id=congestion_record.id, relationship="DERIVED_FROM"
        )
        for p in congestion_parents
    )

    historical_record = _record(
        user_id=user_id,
        route_id=route_id,
        snapshot_id=snapshot_id,
        source_key="route_baseline",
        entity_type="HISTORICAL_DELAY_SCORE",
        entity_key=f"{key}:historical",
        source_type=CanonicalSourceType.SEEDED_BASELINE,
        raw_state="SEEDED_BASELINE",
        value={
            "score": historical_score,
            "segment_delay_hours": [float(s.historical_delay_hours) for s in segments],
            "weight": applied_weights.get("historical"),
        },
        request_id=request_id,
        role="HISTORICAL_DELAY",
        used=True,
        transform_name="historical_delay_aggregation",
        transform_version="1.0.0",
        formula_reference="HISTORICAL_DELAY_V1",
        metadata={"decision_use": "included"},
    )
    records.append(historical_record)

    rri_record = _record(
        user_id=user_id,
        route_id=route_id,
        snapshot_id=snapshot_id,
        source_key="clearpath_derived",
        entity_type="FINAL_RRI",
        entity_key=f"{key}:rri",
        source_type=CanonicalSourceType.DERIVED,
        raw_state="DERIVED",
        value={
            "score": reliability,
            "applied_weights": applied_weights,
            "clearance_override": clearance["status"] == "HARD_BLOCKED",
        },
        request_id=request_id,
        used=True,
        transform_name="route_reliability_index",
        transform_version="1.0.0",
        formula_reference="RRI_V1",
        metadata={"decision_use": "included"},
    )
    records.append(rri_record)
    for parent in (weather_score_record, congestion_record, historical_record):
        edges.append(
            LineageEdge(
                parent_record_id=parent.id, child_record_id=rri_record.id, relationship="INPUT_TO"
            )
        )
    edges.append(
        LineageEdge(
            parent_record_id=port_record.id,
            child_record_id=rri_record.id,
            relationship="INPUT_TO" if port_available else "EXCLUDED_FROM",
        )
    )
    if clearance["status"] == "HARD_BLOCKED":
        edges.append(
            LineageEdge(
                parent_record_id=clearance_record.id,
                child_record_id=rri_record.id,
                relationship="OVERRIDES",
            )
        )

    summary = calculate_traceability_summary(records, snapshot_id, warnings)
    excluded = ["port"] if not port_available else []
    snapshot = RouteDecisionSnapshot(
        id=snapshot_id,
        route_id=route_id,
        user_id=user_id,
        request_id=request_id,
        decision_engine_version="5.0.0",
        routing_algorithm_version="DIJKSTRA_V1",
        scoring_version="RRI_V1",
        clearance_engine_version="CLEARANCE_V1",
        source_code=route.source_station_code,
        destination_code=route.dest_station_code,
        cargo_request=redact_metadata(cargo),
        route_segment_ids=[str(s.id) for s in segments],
        clearance_state=clearance["status"],
        blocking_segment_id=clearance.get("blocking_segment_id"),
        reliability_score=reliability,
        estimated_hours=estimated_hours,
        score_breakdown={
            "weather": weather_score,
            "port": port_sync.score if port_available else None,
            "congestion": congestion.score,
            "historical": historical_score,
        },
        applied_weights=applied_weights,
        excluded_factors=excluded,
        environmental_alerts=alerts,
        traceability_summary=summary.model_dump(mode="json"),
        final_response_summary={
            "route_id": str(route_id),
            "status": clearance["status"],
            "reliability_score": reliability,
            "estimated_hours": estimated_hours,
        },
    )
    db.add(snapshot)
    db.add_all(records)
    db.add_all(edges)
    await db.flush()
    return summary
