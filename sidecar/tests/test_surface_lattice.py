from cyberforge_sidecar.surface_lattice import (
    build_base_surface_prompt,
    collect_system_metrics,
    entropic_to_risk_bias,
    lattice_tuning_block,
    metrics_to_rgb,
    parse_micro_json,
    pennylane_entropic_score,
    punkd_analyze,
    punkd_apply,
)


def test_metrics_and_entropy_pipeline():
    metrics = collect_system_metrics()
    assert "cpu" in metrics
    rgb = metrics_to_rgb(metrics)
    assert len(rgb) == 3
    score = pennylane_entropic_score(rgb)
    assert 0.0 <= score <= 1.0
    bias = entropic_to_risk_bias(score)
    assert -0.1 <= bias <= 0.1


def test_punkd_markers():
    weights = punkd_analyze("vpn remote credential phishing mfa endpoint vendor api")
    assert weights
    patched, mult = punkd_apply("base prompt", weights, profile="balanced")
    assert "PUNKD_MARKERS" in patched
    assert 0.6 <= mult <= 1.8


def test_build_prompt_any_kind():
    lattice = lattice_tuning_block(include_system_entropy=True)
    for kind in ("identity", "human", "endpoint", "vpn", "api", "facility", "vendor", "data"):
        prompt = build_base_surface_prompt(
            {
                "id": f"{kind}-1",
                "label": f"Test {kind}",
                "kind": kind,
                "criticality": 0.8,
                "exposure": 0.5,
                "controlStrength": 0.6,
                "humanPressure": 0.4,
                "telemetryConfidence": 0.7,
                "signals": ["mixed coverage"],
            },
            lattice=lattice,
        )
        assert "individual-surface" in prompt or "individual" in prompt.lower()
        assert kind in prompt.lower() or "Surface Kind" in prompt


def test_parse_json_and_label_fallback():
    payload = parse_micro_json('{"risk":0.6,"uncertainty":0.2,"vectors":["api"]}')
    assert payload["risk"] == 0.6
    label = parse_micro_json("The overall level is High based on signals")
    assert label["risk"] >= 0.7
