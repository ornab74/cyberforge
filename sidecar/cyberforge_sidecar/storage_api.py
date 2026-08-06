from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Body, Header, HTTPException, Query
from pydantic import BaseModel, Field

from .storage import STORAGE, StorageError, bearer_token


router = APIRouter(prefix="/v1/storage", tags=["storage"])


class PutRecordRequest(BaseModel):
    record_type: str = Field(min_length=1, max_length=96)
    payload: Any
    record_id: Optional[str] = Field(default=None, max_length=128)
    scope: str = Field(default="default", max_length=240)
    truth_label: str = Field(
        default="operator-provided encrypted record", max_length=160
    )
    validation_status: str = Field(default="unverified", max_length=64)
    title: Optional[str] = Field(default=None, max_length=240)
    summary: Optional[str] = Field(default=None, max_length=8000)
    tags: list[str] = Field(default_factory=list, max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    limit: int = Field(default=8, ge=1, le=50)
    record_type: Optional[str] = Field(default=None, max_length=96)
    temporal_radius: int = Field(default=1, ge=0, le=10)


class ContextRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    limit: int = Field(default=6, ge=1, le=24)
    record_type: Optional[str] = Field(default=None, max_length=96)


def _session(authorization: Optional[str]) -> str:
    try:
        return bearer_token(authorization)
    except StorageError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/status")
async def storage_status(
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _session(authorization)
    return STORAGE.status()


@router.post("/records")
async def put_record(
    body: PutRecordRequest,
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    token = _session(authorization)
    try:
        record = await STORAGE.put(
            token,
            body.record_type,
            body.payload,
            record_id=body.record_id,
            scope=body.scope,
            truth_label=body.truth_label,
            validation_status=body.validation_status,
            title=body.title,
            summary=body.summary,
            tags=body.tags,
            metadata=body.metadata,
        )
        return {
            "record": record.to_dict(include_payload=False),
            "storage": STORAGE.status(),
        }
    except (StorageError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/records")
async def list_records(
    limit: int = Query(default=100, ge=1, le=500),
    record_type: Optional[str] = Query(default=None, max_length=96),
    include_payload: bool = Query(default=False),
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    token = _session(authorization)
    try:
        records = await __import__("asyncio").to_thread(
            STORAGE.sqlite.list_records,
            token,
            limit=limit,
            record_type=record_type,
            include_payload=include_payload,
        )
        return {"records": records, "count": len(records)}
    except StorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/records/{record_id}")
async def get_record(
    record_id: str,
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    token = _session(authorization)
    try:
        record = await __import__("asyncio").to_thread(
            STORAGE.sqlite.get, token, record_id
        )
    except StorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Encrypted record was not found.")
    return {"record": record.to_dict(include_payload=True)}


@router.delete("/records/{record_id}")
async def delete_record(
    record_id: str,
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    token = _session(authorization)
    try:
        deleted = await STORAGE.delete(token, record_id)
        return {"deleted": deleted, "recordId": record_id}
    except StorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/search")
async def search_records(
    body: SearchRequest,
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    token = _session(authorization)
    try:
        hits = await STORAGE.search(
            token,
            body.query,
            limit=body.limit,
            record_type=body.record_type,
            temporal_radius=body.temporal_radius,
        )
        return {
            "hits": hits,
            "count": len(hits),
            "retrieval": "encrypted SQLite blind search + optional Weaviate hybrid + RRF + MMR",
        }
    except StorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/context")
async def context_packet(
    body: ContextRequest,
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    token = _session(authorization)
    try:
        return await STORAGE.context_packet(
            token,
            body.query,
            limit=body.limit,
            record_type=body.record_type,
        )
    except StorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sync-weaviate")
async def sync_weaviate(
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    token = _session(authorization)
    try:
        return await STORAGE.sync(token)
    except StorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
