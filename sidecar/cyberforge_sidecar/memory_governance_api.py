from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from .memory_governance import (
    GovernanceError,
    apply_retention,
    create_compaction_record,
    provenance_graph,
    queue_full_weaviate_rebuild,
    retention_plan,
    verify_integrity,
)
from .storage import STORAGE, StorageError, bearer_token


router = APIRouter(prefix="/v1/memory", tags=["memory-governance"])


class RetentionRequest(BaseModel):
    policy_days: dict[str, int] = Field(default_factory=dict)
    confirmation: Optional[str] = Field(default=None, max_length=96)


class RebuildRequest(BaseModel):
    confirmation: str = Field(min_length=1, max_length=96)
    sync_limit: int = Field(default=500, ge=1, le=1000)


class CompactionRequest(BaseModel):
    record_ids: list[str] = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=240)


def _session(authorization: Optional[str]) -> str:
    try:
        return bearer_token(authorization)
    except StorageError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/integrity")
async def integrity_report(
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    token = _session(authorization)
    try:
        return await __import__("asyncio").to_thread(verify_integrity, token)
    except (GovernanceError, StorageError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/retention/plan")
async def plan_retention(
    body: RetentionRequest,
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    token = _session(authorization)
    try:
        return await __import__("asyncio").to_thread(
            retention_plan,
            token,
            overrides=body.policy_days,
        )
    except (GovernanceError, StorageError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/retention/apply")
async def enforce_retention(
    body: RetentionRequest,
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    token = _session(authorization)
    try:
        return await __import__("asyncio").to_thread(
            apply_retention,
            token,
            confirmation=body.confirmation or "",
            overrides=body.policy_days,
        )
    except (GovernanceError, StorageError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/provenance/{record_id}")
async def record_provenance(
    record_id: str,
    max_depth: int = Query(default=3, ge=0, le=8),
    max_nodes: int = Query(default=128, ge=1, le=512),
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    token = _session(authorization)
    try:
        return await __import__("asyncio").to_thread(
            provenance_graph,
            token,
            record_id,
            max_depth=max_depth,
            max_nodes=max_nodes,
        )
    except GovernanceError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except StorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/compact")
async def compact_memory(
    body: CompactionRequest,
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    token = _session(authorization)
    try:
        record = await __import__("asyncio").to_thread(
            create_compaction_record,
            token,
            body.record_ids,
            title=body.title,
        )
        if STORAGE.weaviate.client is not None:
            try:
                await __import__("asyncio").to_thread(STORAGE.weaviate.upsert, record)
                await __import__("asyncio").to_thread(
                    STORAGE.sqlite.mark_synced, record.record_id
                )
            except Exception as exc:
                await __import__("asyncio").to_thread(
                    STORAGE.sqlite.mark_sync_failed, record.record_id, exc
                )
        return {
            "record": record.to_dict(include_payload=False),
            "sourceCount": len(body.record_ids),
            "truthLabel": "provenance-preserving deterministic compaction record",
        }
    except (GovernanceError, StorageError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/weaviate/rebuild")
async def rebuild_weaviate(
    body: RebuildRequest,
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    token = _session(authorization)
    try:
        queued = await __import__("asyncio").to_thread(
            queue_full_weaviate_rebuild,
            token,
            confirmation=body.confirmation,
        )
        sync = await STORAGE.sync(token, limit=body.sync_limit)
        return {"rebuild": queued, "sync": sync}
    except (GovernanceError, StorageError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
