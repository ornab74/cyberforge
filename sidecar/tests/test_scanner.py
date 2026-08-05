import asyncio

from cyberforge_sidecar.scanner import SUPER_SCANNER, default_packet


def test_default_scan_is_defensive_and_bounded():
    report = asyncio.run(SUPER_SCANNER.scan(default_packet()))
    assert 0.0 <= report["overallRisk"] <= 1.0
    assert report["findings"]
    assert report["attackPaths"]
    assert report["forensicBoundary"]["country"] == "not attributed"
    assert report["telemetry"]["truthLabel"] == "quantum-inspired conventional simulation"
    impact = report["impactEstimate"]
    assert impact["affectedEquivalentRange"]["low"] <= impact["affectedEquivalentRange"]["high"]


def test_scan_is_reproducible_for_same_seed():
    first = asyncio.run(SUPER_SCANNER.scan(default_packet()))
    second = asyncio.run(SUPER_SCANNER.scan(default_packet()))
    assert first["overallRisk"] == second["overallRisk"]
    assert first["impactEstimate"] == second["impactEstimate"]
    assert first["attackPaths"] == second["attackPaths"]
