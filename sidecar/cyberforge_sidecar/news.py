from __future__ import annotations

from typing import Any
import json

import httpx

from .vault import VAULT


class NewsCaptureError(RuntimeError):
    pass


NEWS_PROMPT = """Research the reported cybersecurity incident using public sources only.
Return a concise defensive incident brief. Separate verified reporting, attributed
claims, uncertainty, and unknowns. Do not identify a threat actor from speculation.
Return JSON with keys: summary, verified_facts, uncertainty, unknowns, sources."""


def _text(payload: dict[str, Any]) -> str:
    if payload.get("output_text"):
        return str(payload["output_text"])
    parts: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []) if isinstance(item, dict) else []:
            if isinstance(content, dict) and content.get("text"):
                parts.append(str(content["text"]))
    return "".join(parts)


async def capture_news(query: str, provider: str = "xai") -> dict[str, Any]:
    query = query.strip()
    if not query or len(query) > 1000:
        raise NewsCaptureError("A focused incident query is required.")
    if provider not in {"xai", "openai"}:
        raise NewsCaptureError("News capture currently supports xai or openai.")
    key = VAULT.get_secret(provider)
    if not key:
        raise NewsCaptureError(f"{provider} is not configured in the vault.")
    model = "grok-4.5" if provider == "xai" else "gpt-4o"
    endpoint = "https://api.x.ai/v1/responses" if provider == "xai" else "https://api.openai.com/v1/responses"
    tool = "web_search" if provider == "xai" else "web_search_preview"
    body = {
        "model": model,
        "input": f"{NEWS_PROMPT}\n\nIncident query: {query}",
        "tools": [{"type": tool}],
        "store": False,
    }
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(
            endpoint,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=body,
        )
        response.raise_for_status()
        payload = response.json()
    return {"provider": provider, "model": model, "query": query, "text": _text(payload), "raw": payload}
