from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256, sha3_256
from pathlib import Path
from typing import Any
import base64
import json
import os

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .config import SETTINGS


class FederationError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ReviewVote:
    reviewer_id: str
    organization_class: str
    verdict: str
    confidence: float
    evidence_digest: str
    issued_at: str
    expires_at: str
    signature: str
    public_key: str

    def core(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("signature", None)
        value.pop("public_key", None)
        return value


class EvidenceSigner:
    def __init__(self, key_path: Path | None = None) -> None:
        self.key_path = key_path or SETTINGS.data_dir / "signing" / "phishing-review-ed25519.pem"

    def _key(self) -> Ed25519PrivateKey:
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        if self.key_path.exists():
            key = serialization.load_pem_private_key(self.key_path.read_bytes(), password=None)
            if not isinstance(key, Ed25519PrivateKey):
                raise FederationError("Phishing review key is not Ed25519.")
            return key
        key = Ed25519PrivateKey.generate()
        raw = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        temporary = self.key_path.with_suffix(".tmp")
        temporary.write_bytes(raw)
        try:
            temporary.chmod(0o600)
        except OSError:
            pass
        os.replace(temporary, self.key_path)
        return key

    def sign_vote(
        self,
        *,
        reviewer_id: str,
        organization_class: str,
        verdict: str,
        confidence: float,
        evidence_digest: str,
        ttl_hours: int = 72,
    ) -> ReviewVote:
        verdict = verdict.upper()
        if verdict not in {"SAFE", "PHISHING", "REVIEW"}:
            raise FederationError("Review verdict is invalid.")
        confidence = max(0.0, min(1.0, float(confidence)))
        issued = _utcnow()
        expires = issued + timedelta(hours=max(1, min(720, int(ttl_hours))))
        core = {
            "reviewer_id": reviewer_id[:160],
            "organization_class": organization_class[:80],
            "verdict": verdict,
            "confidence": confidence,
            "evidence_digest": evidence_digest[:128],
            "issued_at": issued.isoformat(),
            "expires_at": expires.isoformat(),
        }
        key = self._key()
        public = key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return ReviewVote(
            **core,
            signature=base64.b64encode(key.sign(_canonical(core))).decode("ascii"),
            public_key=base64.b64encode(public).decode("ascii"),
        )

    @staticmethod
    def verify(vote: ReviewVote | dict[str, Any]) -> bool:
        try:
            value = vote if isinstance(vote, ReviewVote) else ReviewVote(**vote)
            expires = datetime.fromisoformat(value.expires_at)
            if expires.tzinfo is None or expires <= _utcnow():
                return False
            public = base64.b64decode(value.public_key, validate=True)
            signature = base64.b64decode(value.signature, validate=True)
            Ed25519PublicKey.from_public_bytes(public).verify(signature, _canonical(value.core()))
            return True
        except Exception:
            return False


class ReviewQuorum:
    """Compute a bounded, diversity-aware review outcome.

    A single reviewer, organization class, or model cannot publish a shared block.
    Votes are grouped by public-key fingerprint and organization class. Duplicate
    identities and expired/invalid signatures are discarded.
    """

    @staticmethod
    def decide(
        evidence_digest: str,
        votes: list[dict[str, Any]],
        *,
        minimum_reviewers: int = 3,
        minimum_classes: int = 2,
        phishing_weight: float = 2.1,
        safe_weight: float = 2.1,
    ) -> dict[str, Any]:
        accepted: list[ReviewVote] = []
        seen_keys: set[str] = set()
        rejected = 0
        for raw in votes[:256]:
            try:
                vote = ReviewVote(**raw)
            except Exception:
                rejected += 1
                continue
            fingerprint = sha256(base64.b64decode(vote.public_key)).hexdigest()
            if (
                vote.evidence_digest != evidence_digest
                or fingerprint in seen_keys
                or not EvidenceSigner.verify(vote)
            ):
                rejected += 1
                continue
            seen_keys.add(fingerprint)
            accepted.append(vote)

        classes = {vote.organization_class for vote in accepted}
        phishing = sum(vote.confidence for vote in accepted if vote.verdict == "PHISHING")
        safe = sum(vote.confidence for vote in accepted if vote.verdict == "SAFE")
        review = sum(vote.confidence for vote in accepted if vote.verdict == "REVIEW")
        eligible = len(accepted) >= minimum_reviewers and len(classes) >= minimum_classes
        if eligible and phishing >= phishing_weight and phishing > safe * 1.25:
            verdict = "PHISHING"
        elif eligible and safe >= safe_weight and safe > phishing * 1.25:
            verdict = "SAFE"
        else:
            verdict = "REVIEW"

        core = {
            "schema": "cyberforge-phishing-review-quorum-v1",
            "evidenceDigest": evidence_digest,
            "verdict": verdict,
            "eligible": eligible,
            "acceptedVotes": len(accepted),
            "rejectedVotes": rejected,
            "organizationClasses": sorted(classes),
            "weightedVotes": {
                "PHISHING": round(phishing, 6),
                "SAFE": round(safe, 6),
                "REVIEW": round(review, 6),
            },
            "requirements": {
                "minimumReviewers": minimum_reviewers,
                "minimumOrganizationClasses": minimum_classes,
                "noDuplicatePublicKeys": True,
                "unexpiredSignaturesRequired": True,
            },
            "boundary": "quorum output supports defensive reporting and local blocking only; it does not authorize disruption or takedown",
        }
        return {
            **core,
            "decisionDigest": sha3_256(_canonical(core)).hexdigest(),
            "truthLabel": "cryptographically verified reviewer consensus; not proof beyond submitted evidence",
        }


EVIDENCE_SIGNER = EvidenceSigner()
REVIEW_QUORUM = ReviewQuorum()
