from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.schemas.compliance import ComplianceCheckRequest

RULE_SOURCE_ID = uuid.UUID("20000000-0000-0000-0000-000000000001")
RULE_PACK_VERSION = "MVP_OPERATOR_METADATA_V1"
PENALTY_UNVERIFIED = "Potential penalty exposure — amount not verified."
REQUIRED_DOCUMENT_TYPES = {"PERMIT", "INSURANCE", "CARGO_DECLARATION"}


@dataclass(frozen=True)
class RuleResult:
    rule_key: str
    status: str
    explanation: str
    recommended_action: str
    evidence: dict[str, Any]
    penalty_exposure: str | None = None


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def evaluate_compliance_rules(
    *,
    route_status: str,
    estimated_hours: float | None,
    payload: ComplianceCheckRequest,
    checked_at: datetime | None = None,
) -> tuple[str, list[RuleResult], datetime | None]:
    """Evaluate transparent metadata rules; this does not declare legal compliance."""
    checked_at = _utc(checked_at or datetime.now(timezone.utc))
    eta = (
        checked_at + timedelta(hours=float(estimated_hours))
        if estimated_hours is not None
        else None
    )
    supplied_docs = {doc.document_type.strip().upper(): doc for doc in payload.documents}
    docs = {
        doc_type: doc
        for doc_type, doc in supplied_docs.items()
        if doc.document_number or doc.checksum or doc.storage_reference
    }
    items: list[RuleResult] = []

    hard_blocked = route_status == "HARD_BLOCKED"
    items.append(
        RuleResult(
            rule_key="ROUTE_PHYSICAL_CLEARANCE",
            status="BLOCKED" if hard_blocked else "PASS",
            explanation=(
                "The stored route decision is physically blocked; a compliance check cannot override clearance."
                if hard_blocked
                else "The stored route decision did not report a hard physical clearance block."
            ),
            recommended_action=(
                "Reroute or obtain qualified engineering review before dispatch."
                if hard_blocked
                else "Continue with qualified operational review."
            ),
            evidence={"route_status": route_status},
        )
    )

    missing = sorted(REQUIRED_DOCUMENT_TYPES - set(docs))
    unsubstantiated = sorted(set(supplied_docs) - set(docs))
    items.append(
        RuleResult(
            rule_key="REQUIRED_DOCUMENT_METADATA",
            status="MANUAL_REVIEW" if missing else "PASS",
            explanation=(
            f"Required identifiable document metadata is missing: {', '.join(missing)}."
                if missing
                else "Permit, insurance, and cargo-declaration metadata were supplied."
            ),
            recommended_action=(
                "Supply and verify the missing documents with the competent authority before dispatch."
                if missing
                else "Verify authenticity, scope, and jurisdiction with qualified personnel."
            ),
        evidence={
            "required_types": sorted(REQUIRED_DOCUMENT_TYPES),
            "missing_types": missing,
            "unsubstantiated_types": unsubstantiated,
            "identity_requirement": "document_number, checksum, or storage_reference",
        },
            penalty_exposure=PENALTY_UNVERIFIED if missing else None,
        )
    )

    expired: list[str] = []
    expires_during_route: list[str] = []
    unverified: list[str] = []
    for doc_type, doc in supplied_docs.items():
        if doc.verification_state != "VERIFIED":
            unverified.append(doc_type)
        if doc.expires_at:
            expiry = _utc(doc.expires_at)
            if expiry <= checked_at:
                expired.append(doc_type)
            elif eta and expiry < eta:
                expires_during_route.append(doc_type)

    expiry_status = "WARNING" if expired or expires_during_route else "PASS"
    items.append(
        RuleResult(
            rule_key="DOCUMENT_AND_PERMIT_EXPIRY",
            status=expiry_status,
            explanation=(
                "Expired documents: " + ", ".join(sorted(expired)) + "."
                if expired
                else (
                    "Documents may expire before estimated route completion: "
                    + ", ".join(sorted(expires_during_route))
                    + "."
                    if expires_during_route
                    else "No supplied document expiry precedes the estimated route completion."
                )
            ),
            recommended_action=(
                "Renew or extend affected documents and obtain compliance review before dispatch."
                if expiry_status == "WARNING"
                else "Monitor expiry against any ETA change."
            ),
            evidence={
                "checked_at": checked_at.isoformat(),
                "estimated_completion_at": eta.isoformat() if eta else None,
                "expired_types": sorted(expired),
                "expires_during_route": sorted(expires_during_route),
            },
            penalty_exposure=PENALTY_UNVERIFIED if expiry_status == "WARNING" else None,
        )
    )

    items.append(
        RuleResult(
            rule_key="DOCUMENT_VERIFICATION",
            status="MANUAL_REVIEW" if unverified else "PASS",
            explanation=(
                f"Document authenticity remains unverified for: {', '.join(sorted(unverified))}."
                if unverified
                else "All supplied documents were marked verified by the operator workflow."
            ),
            recommended_action=(
                "Verify document authenticity and scope with the issuer or competent authority."
                if unverified
                else "Retain verification evidence in the audit record."
            ),
            evidence={"unverified_types": sorted(unverified)},
        )
    )

    items.append(
        RuleResult(
            rule_key="CARGO_DECLARATION_COMPLETENESS",
            status="PASS" if payload.cargo_declaration_complete else "MANUAL_REVIEW",
            explanation=(
                "The operator marked the cargo declaration complete."
                if payload.cargo_declaration_complete
                else "Cargo declaration completeness has not been confirmed."
            ),
            recommended_action="Review cargo classification, dimensions, weight, and declared contents before dispatch.",
            evidence={"operator_confirmed": payload.cargo_declaration_complete},
            penalty_exposure=None if payload.cargo_declaration_complete else PENALTY_UNVERIFIED,
        )
    )

    items.append(
        RuleResult(
            rule_key="HUMAN_APPROVAL",
            status="PASS" if payload.human_approval_obtained else "MANUAL_REVIEW",
            explanation=(
                "Required human approval was recorded."
                if payload.human_approval_obtained
                else "Required human approval has not been recorded."
            ),
            recommended_action="Obtain approval from an authorized human operator before dispatch.",
            evidence={"operator_confirmed": payload.human_approval_obtained},
        )
    )

    reference_gaps = [
        name
        for name, value in {
            "transporter_reference": payload.transporter_reference,
            "shipment_reference": payload.shipment_reference,
            "eway_bill_reference": payload.eway_bill_reference,
            "port_customs_reference": payload.port_customs_reference,
        }.items()
        if not value
    ]
    items.append(
        RuleResult(
            rule_key="REFERENCE_METADATA",
            status="MANUAL_REVIEW" if reference_gaps else "PASS",
            explanation=(
                "Reference metadata was not supplied for: " + ", ".join(reference_gaps) + "."
                if reference_gaps
                else "All requested operator reference fields were supplied."
            ),
            recommended_action="Confirm which references apply, then verify them through authorized systems.",
            evidence={"missing_reference_fields": reference_gaps},
        )
    )

    statuses = {item.status for item in items}
    overall = (
        "BLOCKED"
        if "BLOCKED" in statuses
        else "MANUAL_REVIEW"
        if "MANUAL_REVIEW" in statuses
        else "WARNING"
        if "WARNING" in statuses
        else "PASS"
    )
    return overall, items, eta
