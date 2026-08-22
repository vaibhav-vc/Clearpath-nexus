from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class OperationsOverview(BaseModel):
    generated_at: datetime
    product_version: str
    routes_total: int
    shipments_by_status: dict[str, int]
    schedules_by_status: dict[str, int]
    open_events_by_severity: dict[str, int]
    compliance_by_status: dict[str, int]
    multimodal_by_status: dict[str, int]
    train_sync_by_status: dict[str, int]
    prediction_count: int
    traceability: dict
    provider_health: list[dict]
    notices: list[str]


class ShipmentTwin(BaseModel):
    shipment_id: UUID
    reference: str
    status: str
    tracking_enabled: bool
    route_id: UUID | None
    latest_position: dict | None
    open_event_count: int
    state_source: str


class OperationsTwin(BaseModel):
    generated_at: datetime
    model_type: str
    shipments: list[ShipmentTwin]
    disclaimer: str


class AuditExport(BaseModel):
    generated_at: datetime
    format_version: str
    owner_scope: str
    records: list[dict]
    limitations: list[str]
