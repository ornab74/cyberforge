from cyberforge_sidecar.infrastructure import (
    analyze_infrastructure,
    generate_machine_identity,
    to_scanner_packet,
)


def _packet():
    return {
        "name": "Home lab",
        "scale": "home",
        "authorization": {
            "authorized": True,
            "statement": "I own and am authorized to review this complete home lab map.",
            "scope": "Home lab",
            "synthetic": True,
        },
        "nodes": [
            {
                "id": "router",
                "label": "Edge router",
                "kind": "router",
                "zone": "edge",
                "internetFacing": True,
                "criticality": 0.9,
                "controls": {"logging": False, "segmented": True},
            },
            {
                "id": "admin",
                "label": "Cloud admin",
                "kind": "iam",
                "zone": "cloud",
                "privileged": True,
                "criticality": 0.95,
                "controls": {"mfa": False, "logging": True},
            },
        ],
        "edges": [
            {
                "source": "router",
                "target": "admin",
                "kind": "trusts",
                "trust": 0.9,
                "controlStrength": 0.2,
            }
        ],
    }


def test_machine_identity_is_stable_with_same_salt_and_private():
    first = generate_machine_identity(salt="test-salt")
    second = generate_machine_identity(salt="test-salt")
    assert first["machineId"] == second["machineId"]
    assert first["machineId"].startswith("cfm_")
    assert first["privacy"]["macAddressIncluded"] is False
    assert first["privacy"]["rawHostnameIncluded"] is False


def test_topology_finds_identity_logging_and_trust_gaps():
    result = analyze_infrastructure(_packet())
    titles = {finding["title"] for finding in result["findings"]}
    assert "Privileged node lacks modeled MFA" in titles
    assert "Internet-facing node lacks modeled logging" in titles
    assert "Strong trust crosses a weakly controlled link" in titles
    assert result["nodeCount"] == 2
    assert result["edgeCount"] == 1
    assert 0 <= result["topologyPressure"] <= 1


def test_review_converts_to_seeded_scanner_packet():
    review = analyze_infrastructure(_packet())
    packet = to_scanner_packet(review)
    assert len(packet["surfaces"]) == 2
    assert len(packet["links"]) == 1
    assert packet["includeRemoteModels"] is False
    assert packet["seed"] > 0
