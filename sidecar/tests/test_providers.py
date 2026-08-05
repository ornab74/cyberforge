import asyncio

from cyberforge_sidecar.providers import MODEL_COUNCIL, OfflinePolicyClient, _opinion


def test_provider_json_is_bounded_to_defensive_schema():
    parsed = _opinion(
        "test",
        "test-model",
        '''```json
        {
          "summary": "Prioritize identity and recovery controls.",
          "priority_vectors": ["credential", "data", "unsupported-vector"],
          "controls": ["Require phishing-resistant MFA", "Exercise immutable restore"],
          "uncertainty": 0.31,
          "assumptions": ["Synthetic scenario"],
          "evidence_needed": ["Identity-provider logs"]
        }
        ```''',
        4,
    )
    assert parsed.succeeded
    assert parsed.priority_vectors == ("credential", "data")
    assert "unsupported-vector" not in parsed.priority_vectors
    assert parsed.uncertainty == 0.31


def test_council_contains_full_requested_provider_set():
    models = {(item["provider"], item["model"]) for item in MODEL_COUNCIL.status()}
    assert ("local", "llama3-small-q3") in models
    assert ("local", "gemma4-e2b-litert-4bit") in models
    assert ("openai", "gpt-5.6") in models
    assert ("xai", "grok-4.5") in models
    assert ("digitalocean", "kimi-k3") in models
    assert ("gemini", "gemini-3.6-flash") in models


def test_offline_policy_remains_available_without_cloud_keys():
    opinion = asyncio.run(
        OfflinePolicyClient().analyze(
            {"simulation": {"dimensionScores": {"credential": 0.8, "data": 0.4}}}
        )
    )
    assert opinion.succeeded
    assert opinion.priority_vectors[0] == "credential"
