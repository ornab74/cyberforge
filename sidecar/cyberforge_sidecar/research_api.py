from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from .research import REPORT_SIGNER, ResearchError, analyze_research
from .scanner import ScannerError


router = APIRouter(prefix="/v1/research", tags=["research"])


class CertificateEnvelope(BaseModel):
    certificate: dict[str, Any]


@router.post("/analyze")
async def research_analysis(packet: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Run CyberForge's reproducible multi-resolution defensive analysis.

    The endpoint is passive and simulation-only. It performs no discovery,
    probing, exploitation, credential use, or actor attribution.
    """

    try:
        return await analyze_research(packet)
    except (ResearchError, ScannerError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/verify-certificate")
async def verify_certificate(body: CertificateEnvelope) -> dict[str, Any]:
    valid = REPORT_SIGNER.verify(body.certificate)
    return {
        "valid": valid,
        "runFingerprint": body.certificate.get("runFingerprint"),
        "schema": body.certificate.get("schema"),
        "verificationBoundary": (
            "Valid means the Ed25519 signature and canonical run fingerprint match. "
            "It does not independently validate the quality of scenario assumptions."
        ),
    }
