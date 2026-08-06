import asyncio
from copy import deepcopy

from cyberforge_sidecar.research import REPORT_SIGNER, analyze_research
from cyberforge_sidecar.scanner import default_packet


def _packet():
    packet = deepcopy(default_packet())
    packet["worlds"] = 1000
    packet["includeRemoteModels"] = False
    packet["research"] = {
        "coarseWorlds": 1000,
        "sensitivityWorlds": 1000,
        "hotspotLimit": 1,
        "debateRounds": 2,
        "sensitivityDelta": 0.08,
    }
    return packet


def test_research_analysis_is_bounded_and_reproducible():
    first = asyncio.run(analyze_research(_packet()))
    second = asyncio.run(analyze_research(_packet()))

    assert first["schema"] == "cyberforge-research-analysis-v1"
    assert 0.0 <= first["multiResolution"]["deep"]["overallRisk"] <= 1.0
    assert first["sensitivity"]
    assert first["paretoControlFrontier"]
    assert first["councilDebate"]["rounds"]
    assert REPORT_SIGNER.verify(first["certificate"])

    assert (
        first["multiResolution"]["deep"]["overallRisk"]
        == second["multiResolution"]["deep"]["overallRisk"]
    )
    assert first["sensitivity"] == second["sensitivity"]
    assert first["paretoControlFrontier"] == second["paretoControlFrontier"]


def test_certificate_rejects_tampering():
    result = asyncio.run(analyze_research(_packet()))
    certificate = deepcopy(result["certificate"])
    assert REPORT_SIGNER.verify(certificate)

    certificate["core"]["seed"] += 1
    assert not REPORT_SIGNER.verify(certificate)


def test_research_truth_labels_do_not_claim_incident_probability():
    result = asyncio.run(analyze_research(_packet()))
    assert "not measured breach probability" in result["interpretation"]["pressure"]
    assert result["multiResolution"]["truthLabel"] == "seeded counterfactual simulation outputs"
    assert (
        result["councilDebate"]["truthLabel"]
        == "model opinions and deterministic disagreement metrics"
    )
