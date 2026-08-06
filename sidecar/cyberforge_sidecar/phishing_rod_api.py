from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body, Header, HTTPException
from pydantic import BaseModel, Field

from .phishing_rod import PhishingRodError, analyze, simulate_prompt_chain
from .storage import STORAGE, StorageError, bearer_token


router = APIRouter(prefix="/v1/phishing-rod", tags=["phishing-rod"])


class AnalyzeRequest(BaseModel):
    url: str = Field(min_length=1, max_length=4096)
    title: str = Field(default="", max_length=1000)
    visible_text: str = Field(default="", max_length=20000)
    claimed_brand: str = Field(default="", max_length=160)
    redirect_count: int = Field(default=0, ge=0, le=64)
    url_reputation: str = Field(default="unknown", max_length=64)
    forms: list[dict[str, Any]] = Field(default_factory=list, max_length=32)
    screenshot_data_url: Optional[str] = None
    consent_to_store: bool = False


class PromptChainRequest(BaseModel):
    chain: list[dict[str, Any]] = Field(default_factory=list, max_length=128)
    consent_to_store: bool = False


def _optional_token(authorization: Optional[str]) -> str | None:
    if not authorization:
        return None
    try:
        return bearer_token(authorization)
    except StorageError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/analyze")
async def analyze_page(
    body: AnalyzeRequest,
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    token = _optional_token(authorization)
    packet = body.model_dump()
    try:
        decision = await analyze(packet)
        result = decision.to_dict()
        persistence: dict[str, Any] = {
            "persisted": False,
            "reason": "local verdicts are ephemeral unless consent_to_store and an unlocked vault are provided",
        }
        if body.consent_to_store and token:
            record = await STORAGE.put(
                token,
                "phishing-rod-verdict",
                {
                    "packet": {
                        "url": body.url,
                        "title": body.title,
                        "claimed_brand": body.claimed_brand,
                        "redirect_count": body.redirect_count,
                        "url_reputation": body.url_reputation,
                        "forms": body.forms,
                    },
                    "decision": result,
                },
                scope="phishing-rod",
                truth_label="local defensive phishing classification",
                validation_status="machine-reviewed",
                title=f"Phishing Rod: {decision.verdict}",
                summary=f"{body.url} classified {decision.verdict} with risk {decision.risk_score:.3f}",
                tags=["phishing-rod", decision.verdict.lower(), *[signal.code for signal in decision.signals]],
                metadata={
                    "evidenceDigest": decision.evidence_digest,
                    "visibleVerdict": decision.visible_verdict,
                    "requiresReview": decision.requires_review,
                    "screenshotStored": False,
                },
            )
            persistence = {
                "persisted": True,
                "recordId": record.record_id,
                "digest": record.digest,
                "boundary": "screenshot bytes and visible text were not stored",
            }
        result["persistence"] = persistence
        return result
    except (PhishingRodError, StorageError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/prompt-chain/simulate")
async def prompt_chain_simulation(
    body: PromptChainRequest,
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    token = _optional_token(authorization)
    result = simulate_prompt_chain(body.chain)
    persistence: dict[str, Any] = {"persisted": False}
    if body.consent_to_store and token:
        record = await STORAGE.put(
            token,
            "phishing-prompt-chain-simulation",
            result,
            scope="phishing-rod-lab",
            truth_label="symbolic blue-team prompt-chain simulation",
            validation_status="deterministic",
            title="Phishing Rod prompt-chain simulation",
            summary=f"Maximum symbolic taint {result['maximumTaint']:.3f}",
            tags=["phishing-rod", "prompt-injection", "blue-team", "symbolic"],
            metadata={"maximumTaint": result["maximumTaint"]},
        )
        persistence = {"persisted": True, "recordId": record.record_id, "digest": record.digest}
    result["persistence"] = persistence
    return result
