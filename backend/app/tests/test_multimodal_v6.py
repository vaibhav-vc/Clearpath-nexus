from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.multimodal import MultimodalLegInput, MultimodalPlanCreate
from app.services.multimodal import _decision


def _leg(**overrides) -> MultimodalLegInput:
    values = {
        "mode": "RAIL",
        "origin": "Nagpur",
        "destination": "JNPT",
        "distance_km": 820,
        "estimated_minutes": 900,
        "cost_amount": 125000,
        "cost_source_type": "OPERATOR_INPUT",
        "risk_score": 42,
        "risk_source_type": "OPERATOR_INPUT",
        "compliance_status": "MANUAL_REVIEW",
    }
    values.update(overrides)
    return MultimodalLegInput(**values)


def test_multimodal_decision_hard_constraint_overrides_good_risk() -> None:
    leg = _leg(
        risk_score=5,
        constraints=[
            {
                "name": "structure gauge",
                "status": "HARD_BLOCKED",
                "detail": "Declared cargo exceeds supplied limit",
            }
        ],
    )

    assert _decision([leg]) == ("HARD_BLOCKED", "HOLD", "BLOCKED")


def test_multimodal_missing_assessment_requires_manual_review() -> None:
    leg = _leg(
        cost_amount=None,
        cost_source_type="UNAVAILABLE",
        risk_score=None,
        risk_source_type="UNAVAILABLE",
        compliance_status="NOT_ASSESSED",
    )

    assert _decision([leg]) == (
        "REVIEW_REQUIRED",
        "MANUAL_REVIEW",
        "MANUAL_REVIEW",
    )


def test_provider_risk_requires_source_evidence() -> None:
    with pytest.raises(ValidationError, match="non-operator risk requires"):
        _leg(risk_source_type="LIVE_PROVIDER")


def test_provider_risk_requires_observation_timestamp() -> None:
    with pytest.raises(ValidationError, match="observation timestamp"):
        _leg(
            risk_source_type="LIVE_PROVIDER",
            source_provider="provider",
            source_dataset="feed",
            source_reference="https://provider.example/observation/1",
        )


def test_asserted_compliance_requires_owned_check_reference() -> None:
    with pytest.raises(ValidationError, match="ComplianceGuard check"):
        _leg(compliance_status="PASSED")


def test_verified_tariff_requires_reference_evidence() -> None:
    with pytest.raises(ValidationError, match="verified tariff requires"):
        _leg(cost_source_type="VERIFIED_TARIFF")


def test_cost_cannot_be_silently_presented_without_source() -> None:
    with pytest.raises(ValidationError, match="cost_amount requires"):
        _leg(cost_source_type="UNAVAILABLE")


def test_multimodal_plan_rejects_discontinuous_leg_chain() -> None:
    road = _leg(
        mode="ROAD", origin="Factory", destination="Rail Terminal", distance_km=25
    )
    rail = _leg(origin="Different Terminal", destination="Port")

    with pytest.raises(ValidationError, match="discontinuous"):
        MultimodalPlanCreate(
            name="Factory to port",
            origin="Factory",
            destination="Port",
            legs=[road, rail],
        )
