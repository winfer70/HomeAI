from __future__ import annotations

import pytest

from homeai.guardrails import AlarmExposureError, assert_no_alarm_exposure, scan_payload, scan_text


def test_scan_text_flags_forbidden_alarm_entity() -> None:
    violations = scan_text("entity_id: alarm_control_panel.satel_integra", source="sample.yaml")

    assert any(violation.rule == "forbidden alarm entity id" for violation in violations)
    assert any(violation.match == "alarm_control_panel.satel_integra" for violation in violations)


def test_scan_payload_flags_satel_and_critical_reference() -> None:
    payload = {
        "exposed_entities": ["light.kitchen", "Satel Integra 32"],
        "automation": {"name": "Critical Life Shield"},
    }

    violations = scan_payload(payload, source="payload")

    assert any("Satel" in violation.match or "Integra" in violation.match for violation in violations)
    assert any(violation.rule == "forbidden Critical Life Shield reference" for violation in violations)


def test_assert_no_alarm_exposure_allows_clean_payload() -> None:
    assert_no_alarm_exposure({"entity_id": "light.kitchen", "name": "Kitchen light"})


def test_assert_no_alarm_exposure_raises_with_details() -> None:
    with pytest.raises(AlarmExposureError) as exc_info:
        assert_no_alarm_exposure({"entity_id": "alarm.kitchen"}, source="payload")

    assert "forbidden alarm entity id" in str(exc_info.value)
