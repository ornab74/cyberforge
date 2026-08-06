from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body, Header, HTTPException
from pydantic import BaseModel

from .config import SETTINGS
from .research import REPORT_SIGNER, ResearchError, analyze_research
from .scanner import ScannerError
from .storage import STORAGE, StorageError, bearer_token


router = APIRouter(prefix="/v1/research", tags=["research"])


class CertificateEnvelope(BaseModel):
    certificate: dict[str, Any]


@router.post("/analyze")
async def research_analysis(
    packet: dict[str, Any] = Body(...),
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    """Run and optionally persist CyberForge's defensive research analysis.

    A valid unlocked-vault bearer token causes the full run to be stored in the
    encrypted SQLite source of truth and its redacted projection to be queued for
    Weaviate. Without a token, the analysis remains ephemeral.
    """

    try:
        result = await analyze_research(packet)
        persistence: dict[str, Any] = {
            "persisted": False,
            "reason": "no unlocked-vault bearer session supplied",
        }
        if SETTINGS.auto_persist_research and authorization:
            token = bearer_token(authorization)
            record = await STORAGE.put(
                token,
                "research-run",
                {
                    "scenario": packet,
                    "result": result,
                },
                scope=str(packet.get("authorization", {}).get("scope", "research")),
                truth_label="encrypted research run with signed simulation certificate",
                validation_status="signed",
                title=str(packet.get("name", "CyberForge research run")),
                tags=[
                    "research",
                    "multi-resolution",
                    "sensitivity",
                    "pareto",
                    "council-debate",
                    "signed-certificate",
                ],
                metadata={
                    "runFingerprint": result.get("certificate", {}).get("runFingerprint"),
                    "schema": result.get("schema"),
                    "remoteModelsIncluded": bool(packet.get("includeRemoteModels", False)),
                },
            )
            persistence = {
                "persisted": True,
                "recordId": record.record_id,
                "digest": record.digest,
                "storageBoundary": (
                    "full encrypted payload in SQLite; redacted reconstructible projection in Weaviate"
                ),
            }
        result["persistence"] = persistence
        return result
    except (ResearchError, ScannerError, StorageError, ValueError, TypeError) as exc:
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
