from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body, Header, HTTPException
from pydantic import BaseModel, Field

from .infrastructure import (
    InfrastructureError,
    analyze_infrastructure,
    generate_machine_identity,
    to_scanner_packet,
)
from .scanner import SUPER_SCANNER


router = APIRouter(prefix="/v1/infrastructure", tags=["infrastructure"])


class MachineIdentityRequest(BaseModel):
    salt: Optional[str] = Field(default=None, min_length=8, max_length=512)


@router.post("/machine-id")
async def machine_id(body: MachineIdentityRequest) -> dict[str, Any]:
    try:
        return generate_machine_identity(salt=body.salt)
    except InfrastructureError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/review")
async def review_infrastructure(
    packet: dict[str, Any] = Body(...),
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    try:
        review = analyze_infrastructure(packet)
        include_remote = bool(packet.get("includeRemoteModels", False))
        if include_remote and not authorization:
            raise HTTPException(
                status_code=401,
                detail="Unlock the local provider vault before remote model review.",
            )
        scanner_packet = to_scanner_packet(review, include_remote=include_remote)
        simulation = await SUPER_SCANNER.scan(scanner_packet)
        return {
            "topology": review,
            "simulation": simulation,
            "reviewProtocol": {
                "stages": [
                    "schema and authorization validation",
                    "deterministic topology and control analysis",
                    "trust-path and segmentation review",
                    "seeded whole-estate simulation",
                    "local model micro-scans when loaded",
                    "optional redacted model-council critique",
                ],
                "defenseOnly": True,
                "activeProbing": False,
            },
        }
    except InfrastructureError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
