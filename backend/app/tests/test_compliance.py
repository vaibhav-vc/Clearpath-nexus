from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.v1 import compliance as compliance_api
from app.api.v1.compliance import _owned_check, _owned_route
from app.core.security import CurrentUser

from app.schemas.compliance import (
    ComplianceCheckRequest,
    ComplianceOverrideRequest,
    ShipmentDocumentInput,
)
from app.services.compliance import PENALTY_UNVERIFIED, evaluate_compliance_rules


def _complete_payload(permit_expiry: datetime) -> ComplianceCheckRequest:
    return ComplianceCheckRequest(
        documents=[
            ShipmentDocumentInput(
                document_type="PERMIT",
                document_number="PERMIT-1",
                expires_at=permit_expiry,
                verification_state="VERIFIED",
            ),
            ShipmentDocumentInput(
                document_type="INSURANCE",
                document_number="POLICY-1",
                expires_at=permit_expiry,
                verification_state="VERIFIED",
            ),
            ShipmentDocumentInput(
                document_type="CARGO_DECLARATION",
                document_number="DECL-1",
                verification_state="VERIFIED",
            ),
        ],
        cargo_declaration_complete=True,
        human_approval_obtained=True,
        transporter_reference="TRANS-1",
        shipment_reference="SHIP-1",
        eway_bill_reference="EWAY-OPERATOR-ENTERED",
        port_customs_reference="PORT-OPERATOR-ENTERED",
    )


def test_permit_expiry_before_route_eta_is_warning_without_invented_fine() -> None:
    now = datetime(2026, 8, 22, 12, tzinfo=timezone.utc)
    payload = _complete_payload(now + timedelta(hours=14))
    overall, items, eta = evaluate_compliance_rules(
        route_status="APPROVED", estimated_hours=17, payload=payload, checked_at=now
    )
    expiry = next(item for item in items if item.rule_key == "DOCUMENT_AND_PERMIT_EXPIRY")
    assert overall == "WARNING"
    assert expiry.status == "WARNING"
    assert "PERMIT" in expiry.evidence["expires_during_route"]
    assert expiry.penalty_exposure == PENALTY_UNVERIFIED
    assert eta == now + timedelta(hours=17)


def test_missing_documents_and_approval_require_manual_review() -> None:
    overall, items, _ = evaluate_compliance_rules(
        route_status="APPROVED",
        estimated_hours=10,
        payload=ComplianceCheckRequest(),
    )
    assert overall == "MANUAL_REVIEW"
    assert any(
        item.rule_key == "REQUIRED_DOCUMENT_METADATA" and item.status == "MANUAL_REVIEW"
        for item in items
    )
    assert any(
        item.rule_key == "HUMAN_APPROVAL" and item.status == "MANUAL_REVIEW" for item in items
    )


def test_empty_document_placeholders_do_not_satisfy_required_metadata() -> None:
    payload = ComplianceCheckRequest(
        documents=[
            ShipmentDocumentInput(document_type="PERMIT"),
            ShipmentDocumentInput(document_type="INSURANCE"),
            ShipmentDocumentInput(document_type="CARGO_DECLARATION"),
        ]
    )
    overall, items, _ = evaluate_compliance_rules(
        route_status="APPROVED", estimated_hours=4, payload=payload
    )
    required = next(item for item in items if item.rule_key == "REQUIRED_DOCUMENT_METADATA")
    assert overall == "MANUAL_REVIEW"
    assert required.evidence["missing_types"] == [
        "CARGO_DECLARATION",
        "INSURANCE",
        "PERMIT",
    ]
    assert required.evidence["unsubstantiated_types"] == [
        "CARGO_DECLARATION",
        "INSURANCE",
        "PERMIT",
    ]


def test_physical_block_cannot_be_overridden_by_good_document_metadata() -> None:
    payload = _complete_payload(datetime.now(timezone.utc) + timedelta(days=2))
    overall, items, _ = evaluate_compliance_rules(
        route_status="HARD_BLOCKED", estimated_hours=4, payload=payload
    )
    assert overall == "BLOCKED"
    physical = next(item for item in items if item.rule_key == "ROUTE_PHYSICAL_CLEARANCE")
    assert physical.status == "BLOCKED"


def test_override_requires_an_auditable_reason() -> None:
    with pytest.raises(ValidationError):
        ComplianceOverrideRequest(reason="too short")


@pytest.mark.asyncio
@pytest.mark.parametrize("lookup", [_owned_route, _owned_check])
async def test_compliance_lookups_are_ownership_scoped_and_non_disclosing(lookup) -> None:
    class EmptyResult:
        def scalar_one_or_none(self):
            return None

    class CapturingSession:
        statement = None

        async def execute(self, statement):
            self.statement = statement
            return EmptyResult()

    db = CapturingSession()
    with pytest.raises(HTTPException) as exc:
        await lookup(db, __import__("uuid").uuid4(), "owner-a")
    assert getattr(exc.value, "status_code", None) == 404
    assert "user_id" in str(db.statement)
    assert "owner-a" in db.statement.compile().params.values()


@pytest.mark.asyncio
async def test_override_records_actor_reason_and_timestamp(monkeypatch) -> None:
    check = SimpleNamespace(
        id=uuid4(),
        overridden=False,
        override_reason=None,
        overridden_by=None,
        overridden_at=None,
    )

    async def owned_check(*_args):
        return check

    async def response(_db, value):
        return value

    class Session:
        committed = False
        events = []

        def add(self, value):
            self.events.append(value)

        async def commit(self):
            self.committed = True

        async def refresh(self, _value):
            return None

    monkeypatch.setattr(compliance_api, "_owned_check", owned_check)
    monkeypatch.setattr(compliance_api, "_response", response)
    db = Session()
    user = CurrentUser(id="owner-a", email=None, role="authenticated", claims={})
    result = await compliance_api.override_check(
        uuid4(), ComplianceOverrideRequest(reason="Qualified operator reviewed the evidence."), db, user
    )
    assert result.overridden is True
    assert result.override_reason == "Qualified operator reviewed the evidence."
    assert result.overridden_by == "owner-a"
    assert result.overridden_at.tzinfo is not None
    assert db.committed is True
    assert len(db.events) == 1
    assert db.events[0].reason == "Qualified operator reviewed the evidence."


@pytest.mark.asyncio
async def test_multiple_compliance_responses_are_loaded_in_three_batched_queries() -> None:
    now = datetime.now(timezone.utc)

    def check():
        return SimpleNamespace(
            id=uuid4(),
            route_id=uuid4(),
            user_id="owner-a",
            overall_status="MANUAL_REVIEW",
            rule_pack_version="V1",
            disclaimer="Decision support only",
            overridden=False,
            override_reason=None,
            overridden_by=None,
            overridden_at=None,
            created_at=now,
        )

    class EmptyResult:
        def all(self):
            return []

        def scalars(self):
            return []

    class Session:
        calls = 0

        async def execute(self, _statement):
            self.calls += 1
            return EmptyResult()

    db = Session()
    responses = await compliance_api._responses(db, [check(), check()])
    assert len(responses) == 2
    assert db.calls == 3
