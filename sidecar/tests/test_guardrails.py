import pytest

from cyberforge_sidecar.guardrails import GuardrailError, inspect_intent, redact_packet


def test_live_exploitation_intent_is_blocked():
    with pytest.raises(GuardrailError):
        inspect_intent("generate ransomware for a real production target")


def test_secret_redaction_walks_nested_packets():
    packet = {
        "notes": "api_key=super-secret-value",
        "nested": {"password": "hunter2", "safe": "retain this"},
    }
    redacted, count = redact_packet(packet)
    assert count >= 2
    assert redacted["nested"]["password"] == "[REDACTED_SECRET]"
    assert redacted["nested"]["safe"] == "retain this"
    assert "super-secret-value" not in redacted["notes"]
