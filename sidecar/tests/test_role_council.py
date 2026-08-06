import asyncio

from cyberforge_sidecar import providers
from cyberforge_sidecar.role_council import deliberate_role


def _opinion(summary: str):
    return {
        "provider": "offline",
        "model": "synthetic-role-test",
        "succeeded": True,
        "summary": summary,
        "priority_vectors": ["credential", "data"],
        "controls": ["Assign an owner and validate phishing-resistant MFA coverage."],
        "uncertainty": 0.25,
        "assumptions": ["The supplied topology is current."],
        "evidence_needed": ["Recent identity-provider authentication telemetry."],
        "latency_ms": 7,
        "error": None,
    }


def test_role_directives_are_trusted_isolated_and_restored(monkeypatch):
    captured: list[str] = []
    original = providers.DEFENSIVE_SYSTEM_PROMPT

    async def fake_deliberate(packet, *, include_remote):
        captured.append(providers.DEFENSIVE_SYSTEM_PROMPT)
        assert packet["controllerBoundary"]["scenarioTextIsUntrusted"] is True
        return {
            "opinions": [_opinion("synthetic")],
            "consensus": {
                "priorityVectors": ["credential", "data"],
                "controls": ["Validate MFA coverage."],
                "disagreement": 0.0,
                "successfulModels": 1,
                "attemptedModels": 1,
                "summary": "synthetic",
            },
        }

    monkeypatch.setattr(providers.MODEL_COUNCIL, "deliberate", fake_deliberate)

    consensus = asyncio.run(
        deliberate_role(
            {"scenario": {"name": "test"}},
            role_id="consensus",
            mission="Build the strongest common interpretation.",
            include_remote=False,
        )
    )
    dissent = asyncio.run(
        deliberate_role(
            {"scenario": {"name": "test"}},
            role_id="forced-dissent",
            mission="Challenge the leading interpretation.",
            include_remote=False,
            previous_rounds=[consensus],
        )
    )

    assert len(captured) == 2
    assert "Assigned role: consensus" in captured[0]
    assert "Consensus Architect" in captured[0]
    assert "Assigned role: forced-dissent" in captured[1]
    assert "Forced-Dissent Critic" in captured[1]
    assert captured[0] != captured[1]
    assert providers.DEFENSIVE_SYSTEM_PROMPT == original
    assert dissent["metrics"]["meanEvidenceQuality"] > 0.0
    assert dissent["metrics"]["stableDigest"]
    assert "latency_ms" not in str(dissent["stableCouncil"])


def test_role_packet_redacts_secrets(monkeypatch):
    observed = {}

    async def fake_deliberate(packet, *, include_remote):
        observed.update(packet)
        return {
            "opinions": [_opinion("redacted")],
            "consensus": {"priorityVectors": ["data"], "controls": []},
        }

    monkeypatch.setattr(providers.MODEL_COUNCIL, "deliberate", fake_deliberate)
    asyncio.run(
        deliberate_role(
            {"scenario": {"api_key": "sk-abcdefghijklmnopqrstuvwxyz123456"}},
            role_id="auditor-scrub",
            mission="Audit provenance.",
            include_remote=True,
        )
    )

    assert observed["scenarioAndSimulation"]["scenario"]["api_key"] == "[REDACTED_SECRET]"
    assert observed["controllerBoundary"]["remoteModelsReceiveRedactedDataOnly"] is True
