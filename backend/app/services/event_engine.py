from __future__ import annotations

from app.models.live_ops import OperationalEvent, ProviderObservation
from app.schemas.live_ops import LiveDataEnvelope


def events_from_observation(observation: ProviderObservation, envelope: LiveDataEnvelope) -> list[OperationalEvent]:
    events: list[OperationalEvent] = []
    base = {"source_observation_id": observation.id, "provenance_record_id": observation.provenance_record_id, "observed_at": envelope.observed_at or envelope.fetched_at}
    if envelope.status in {"STALE", "UNAVAILABLE", "INVALID", "RATE_LIMITED"}:
        event_type = "PROVIDER_STALE" if envelope.status == "STALE" else "PROVIDER_UNAVAILABLE"
        events.append(OperationalEvent(event_type=event_type, severity="MEDIUM", state="OPEN", title=f"{envelope.provider_label} {envelope.status.lower()}", detail="; ".join(envelope.quality.validation_errors) or "Live provider data cannot currently be used.", **base))
    if envelope.provider_key == "open_meteo" and envelope.quality.valid:
        rain = float(envelope.data.get("rain") or 0)
        visibility = float(envelope.data.get("visibility") or 10000)
        gust = float(envelope.data.get("wind_gusts_10m") or 0)
        if rain >= 7.5:
            events.append(OperationalEvent(event_type="HEAVY_RAIN", severity="HIGH", state="OPEN", title="Heavy rain observed", detail=f"Open-Meteo reported {rain:.1f} mm rain at the monitored point.", **base))
        if 0 < visibility < 2000:
            events.append(OperationalEvent(event_type="LOW_VISIBILITY", severity="HIGH", state="OPEN", title="Low visibility observed", detail=f"Visibility is {visibility / 1000:.1f} km at the monitored point.", **base))
        if gust >= 50:
            events.append(OperationalEvent(event_type="HIGH_WIND", severity="HIGH", state="OPEN", title="High wind gust observed", detail=f"Wind gust is {gust:.1f} km/h at the monitored point.", **base))
    return events
