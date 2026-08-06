from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from .phishing_federation import EVIDENCE_SIGNER, REVIEW_QUORUM, FederationError
from .storage import STORAGE, StorageError, bearer_token


router = APIRouter(prefix="/v1/phishing-rod/federation", tags=["phishing-rod-federation"])


class SignVoteRequest(BaseModel):
    reviewer_id: str = Field(min_length=1, max_length=160)
    organization_class: str = Field(min_length=1, max_length=80)
    verdict: str = Field(min_length=1, max_length=16)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_digest: str = Field(min_length=32, max_length=128)
    ttl_hours: int = Field(default=72, ge=1, le=720)


class QuorumRequest(BaseModel):
    evidence_digest: str = Field(min_length=32, max_length=128)
    votes: list[dict[str, Any]] = Field(default_factory=list, max_length=256)
    minimum_reviewers: int = Field(default=3, ge=2, le=25)
    minimum_classes: int = Field(default=2, ge=1, le=12)
    phishing_weight: float = Field(default=2.1, ge=0.5, le=25.0)
    safe_weight: float = Field(default=2.1, ge=0.5, le=25.0)
    consent_to_store: bool = False


def _required_token(authorization: Optional[str]) -> str:
    try:
        return bearer_token(authorization)
    except StorageError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/votes/sign")
async def sign_vote(
    body: SignVoteRequest,
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _required_token(authorization)
    try:
        vote = EVIDENCE_SIGNER.sign_vote(
            reviewer_id=body.reviewer_id,
            organization_class=body.organization_class,
            verdict=body.verdict,
            confidence=body.confidence,
            evidence_digest=body.evidence_digest,
            ttl_hours=body.ttl_hours,
        )
        return {
            "schema": "cyberforge-phishing-review-vote-v1",
            "vote": vote.__dict__,
            "verified": EVIDENCE_SIGNER.verify(vote),
            "boundary": "a signed vote is one review opinion and cannot independently publish a shared block",
        }
    except FederationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/quorum")
async def decide_quorum(
    body: QuorumRequest,
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    token = _required_token(authorization)
    result = REVIEW_QUORUM.decide(
        body.evidence_digest,
        body.votes,
        minimum_reviewers=body.minimum_reviewers,
        minimum_classes=body.minimum_classes,
        phishing_weight=body.phishing_weight,
        safe_weight=body.safe_weight,
    )
    persistence: dict[str, Any] = {"persisted": False}
    if body.consent_to_store:
        record = await STORAGE.put(
            token,
            "phishing-review-quorum",
            result,
            scope="phishing-review-board",
            truth_label="signed multi-party phishing review",
            validation_status="signature-and-quorum-verified",
            title=f"Phishing review quorum: {result['verdict']}",
            summary=(
                f"{result['acceptedVotes']} accepted votes across "
                f"{len(result['organizationClasses'])} organization classes"
            ),
            tags=["phishing-rod", "review-board", "quorum", result["verdict"].lower()],
            metadata={
                "evidenceDigest": body.evidence_digest,
                "decisionDigest": result["decisionDigest"],
                "eligible": result["eligible"],
            },
        )
        persistence = {
            "persisted": True,
            "recordId": record.record_id,
            "digest": record.digest,
        }
    return {**result, "persistence": persistence}
