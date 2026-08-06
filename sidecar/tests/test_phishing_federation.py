from __future__ import annotations

from pathlib import Path

from cyberforge_sidecar.phishing_federation import EvidenceSigner, ReviewQuorum


def signer(tmp_path: Path, name: str) -> EvidenceSigner:
    return EvidenceSigner(tmp_path / f"{name}.pem")


def test_signed_vote_verifies_and_tamper_fails(tmp_path: Path) -> None:
    service = signer(tmp_path, "one")
    vote = service.sign_vote(
        reviewer_id="reviewer-1",
        organization_class="hospital",
        verdict="PHISHING",
        confidence=0.94,
        evidence_digest="a" * 64,
    )
    assert service.verify(vote) is True
    changed = vote.__dict__ | {"confidence": 0.2}
    assert service.verify(changed) is False


def test_quorum_requires_identity_and_class_diversity(tmp_path: Path) -> None:
    digest = "b" * 64
    services = [signer(tmp_path, f"reviewer-{index}") for index in range(3)]
    votes = [
        services[0].sign_vote(
            reviewer_id="r1",
            organization_class="school",
            verdict="PHISHING",
            confidence=0.95,
            evidence_digest=digest,
        ).__dict__,
        services[1].sign_vote(
            reviewer_id="r2",
            organization_class="hospital",
            verdict="PHISHING",
            confidence=0.92,
            evidence_digest=digest,
        ).__dict__,
        services[2].sign_vote(
            reviewer_id="r3",
            organization_class="government",
            verdict="PHISHING",
            confidence=0.90,
            evidence_digest=digest,
        ).__dict__,
    ]
    result = ReviewQuorum.decide(digest, votes)
    assert result["eligible"] is True
    assert result["verdict"] == "PHISHING"
    assert result["acceptedVotes"] == 3
    assert len(result["organizationClasses"]) == 3


def test_duplicate_key_cannot_amplify_vote(tmp_path: Path) -> None:
    digest = "c" * 64
    service = signer(tmp_path, "duplicate")
    vote = service.sign_vote(
        reviewer_id="same-key",
        organization_class="corporation",
        verdict="PHISHING",
        confidence=1.0,
        evidence_digest=digest,
    ).__dict__
    result = ReviewQuorum.decide(digest, [vote, vote, vote])
    assert result["acceptedVotes"] == 1
    assert result["rejectedVotes"] == 2
    assert result["eligible"] is False
    assert result["verdict"] == "REVIEW"


def test_votes_are_bound_to_one_evidence_digest(tmp_path: Path) -> None:
    service = signer(tmp_path, "bound")
    vote = service.sign_vote(
        reviewer_id="bound",
        organization_class="power-grid",
        verdict="SAFE",
        confidence=0.99,
        evidence_digest="d" * 64,
    ).__dict__
    result = ReviewQuorum.decide("e" * 64, [vote])
    assert result["acceptedVotes"] == 0
    assert result["verdict"] == "REVIEW"
