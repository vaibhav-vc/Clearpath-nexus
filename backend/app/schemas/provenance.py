from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TraceabilityCounts(BaseModel):
    traced: int
    total: int
    coverage_pct: float


class FreshnessCounts(BaseModel):
    fresh: int = 0
    aging: int = 0
    stale: int = 0
    unknown: int = 0
    not_applicable: int = 0


class SourceModeCounts(BaseModel):
    live_provider: int = 0
    public_open_data: int = 0
    cached_provider: int = 0
    operator_input: int = 0
    seeded_baseline: int = 0
    derived: int = 0
    simulated: int = 0
    offline_computed: int = 0
    imported_document: int = 0
    unavailable: int = 0


class DecisionUseCounts(BaseModel):
    included: int = 0
    excluded: int = 0
    hard_constraints: int = 0
    fallbacks: int = 0
    informational: int = 0


class ProvenanceSummary(BaseModel):
    decision_record_id: UUID
    traceability: TraceabilityCounts
    freshness: FreshnessCounts
    source_modes: SourceModeCounts
    decision_use: DecisionUseCounts
    warnings: list[str] = Field(default_factory=list)


class SourceBrief(BaseModel):
    id: UUID
    key: str
    label: str
    category: str
    authority_level: str
    official: bool
    free_for_mvp: bool
    requires_key: bool
    reference_url: str | None = None
    license_name: str | None = None
    attribution_text: str | None = None
    limitations: dict = Field(default_factory=dict)
    freshness_policy: dict = Field(default_factory=dict)
    current_status: dict | None = None


class ProvenanceRecordResponse(BaseModel):
    id: UUID
    entity_type: str
    entity_key: str
    decision_input_role: str | None
    canonical_source_type: str
    raw_source_state: str | None
    source: SourceBrief | None
    observed_at: datetime | None
    fetched_at: datetime
    valid_until: datetime | None
    freshness: dict
    cache_hit: bool
    used_in_decision: bool
    excluded_reason: str | None
    quality: dict
    transform: dict
    decision_impact: dict
    request_id: str | None
    checksum: str | None
    value_summary: dict
    metadata: dict


class LineageEdgeResponse(BaseModel):
    id: UUID
    parent_record_id: UUID
    child_record_id: UUID
    relationship: str


class EvidenceComponent(BaseModel):
    role: str
    label: str
    status: str
    record_ids: list[UUID]
    explanation: str


class RouteEvidenceResponse(BaseModel):
    route: dict
    snapshot: dict
    traceability: ProvenanceSummary
    components: list[EvidenceComponent]
    records: list[ProvenanceRecordResponse]
    edges: list[LineageEdgeResponse]
    warnings: list[str]


class RecordNeighborhoodResponse(BaseModel):
    record: ProvenanceRecordResponse
    parents: list[ProvenanceRecordResponse]
    children: list[ProvenanceRecordResponse]
    edges: list[LineageEdgeResponse]


class SourceListResponse(BaseModel):
    items: list[SourceBrief]
    total: int = Field(ge=0)
