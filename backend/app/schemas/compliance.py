from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


COMPLIANCE_DISCLAIMER = (
    "ClearPath Nexus provides compliance decision support and source references. "
    "It does not provide legal representation or definitive legal advice. Requirements "
    "must be verified with competent authorities and qualified legal/compliance personnel."
)


class ShipmentDocumentInput(BaseModel):
    document_type: str = Field(min_length=2, max_length=60)
    document_number: str | None = Field(default=None, max_length=160)
    issuing_authority: str | None = Field(default=None, max_length=255)
    issued_at: datetime | None = None
    expires_at: datetime | None = None
    checksum: str | None = Field(default=None, pattern="^[0-9a-fA-F]{64}$")
    storage_reference: str | None = Field(default=None, max_length=500)
    verification_state: str = Field(
        default="UNVERIFIED", pattern="^(UNVERIFIED|OPERATOR_DECLARED|VERIFIED)$"
    )

    @model_validator(mode="after")
    def dates_are_ordered(self) -> "ShipmentDocumentInput":
        if self.issued_at and self.expires_at and self.expires_at <= self.issued_at:
            raise ValueError("expires_at must be after issued_at")
        return self


class ComplianceCheckRequest(BaseModel):
    documents: list[ShipmentDocumentInput] = Field(default_factory=list)
    cargo_declaration_complete: bool = False
    human_approval_obtained: bool = False
    transporter_reference: str | None = Field(default=None, max_length=160)
    shipment_reference: str | None = Field(default=None, max_length=160)
    eway_bill_reference: str | None = Field(default=None, max_length=160)
    port_customs_reference: str | None = Field(default=None, max_length=160)


class ComplianceItemResponse(BaseModel):
    id: UUID
    rule_key: str
    rule_version: str
    status: str
    explanation: str
    recommended_action: str
    penalty_exposure: str | None
    evidence: dict
    rule_source: dict


class ComplianceOverrideEventResponse(BaseModel):
    id: UUID
    user_id: str
    reason: str
    created_at: datetime


class ShipmentDocumentResponse(BaseModel):
    id: UUID
    document_type: str
    document_number: str | None
    issuing_authority: str | None
    issued_at: datetime | None
    expires_at: datetime | None
    checksum: str | None
    verification_state: str


class ComplianceCheckResponse(BaseModel):
    id: UUID
    route_id: UUID
    overall_status: str
    rule_pack_version: str
    disclaimer: str
    overridden: bool
    override_reason: str | None
    overridden_by: str | None
    overridden_at: datetime | None
    created_at: datetime
    items: list[ComplianceItemResponse]
    documents: list[ShipmentDocumentResponse] = Field(default_factory=list)
    overrides: list[ComplianceOverrideEventResponse] = Field(default_factory=list)


class ComplianceOverrideRequest(BaseModel):
    reason: str = Field(min_length=12, max_length=1000)
