from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Iterable, Optional
import asyncio
import json
import re
import time

import httpx

from .config import GEMMA4_E2B, LLAMA3_SMALL
from .models import MODEL_MANAGER, ModelError
from .prompt_library import council_system
from .vault import VAULT, VaultError


# Loaded from prompts/council_system.md — advanced AEGIS-816 council kernel.
DEFENSIVE_SYSTEM_PROMPT = council_system()

@dataclass(frozen=True)
class ProviderOpinion:
    provider: str
    model: str
    succeeded: bool
    summary: str
    priority_vectors: tuple[str, ...]
    controls: tuple[str, ...]
    uncertainty: float
    assumptions: tuple[str, ...]
    evidence_needed: tuple[str, ...]
    latency_ms: int
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProviderError(RuntimeError):
    pass


def _safe_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        payload = json.loads(text[start : end + 1])
        if isinstance(payload, dict):
            return payload
    raise ProviderError("Model did not return a JSON object.")


def _opinion(provider: str, model: str, text: str, latency_ms: int) -> ProviderOpinion:
    payload = _safe_json(text)
    allowed_vectors = {
        "credential",
        "phishing",
        "endpoint",
        "api",
        "cloud",
        "physical",
        "vendor",
        "availability",
        "data",
    }
    vectors = tuple(
        value
        for value in (str(item).lower() for item in payload.get("priority_vectors", []))
        if value in allowed_vectors
    )
    controls = tuple(str(item).strip() for item in payload.get("controls", []) if str(item).strip())
    assumptions = tuple(
        str(item).strip() for item in payload.get("assumptions", []) if str(item).strip()
    )
    evidence = tuple(
        str(item).strip()
        for item in payload.get("evidence_needed", [])
        if str(item).strip()
    )
    uncertainty = max(0.0, min(1.0, float(payload.get("uncertainty", 0.5))))
    return ProviderOpinion(
        provider=provider,
        model=model,
        succeeded=True,
        summary=str(payload.get("summary", "")).strip(),
        priority_vectors=vectors,
        controls=controls,
        uncertainty=uncertainty,
        assumptions=assumptions,
        evidence_needed=evidence,
        latency_ms=latency_ms,
    )


def _failure(provider: str, model: str, started: float, error: Exception) -> ProviderOpinion:
    return ProviderOpinion(
        provider=provider,
        model=model,
        succeeded=False,
        summary="",
        priority_vectors=(),
        controls=(),
        uncertainty=1.0,
        assumptions=(),
        evidence_needed=(),
        latency_ms=int((time.perf_counter() - started) * 1000),
        error=str(error),
    )


class ProviderClient:
    provider: str
    model: str

    @property
    def configured(self) -> bool:
        raise NotImplementedError

    async def analyze(self, packet: dict[str, Any]) -> ProviderOpinion:
        raise NotImplementedError


class OpenAIClient(ProviderClient):
    provider = "openai"
    model = "gpt-5.6"
    endpoint = "https://api.openai.com/v1/responses"

    @property
    def configured(self) -> bool:
        return VAULT.provider_configured(self.provider)

    async def analyze(self, packet: dict[str, Any]) -> ProviderOpinion:
        started = time.perf_counter()
        try:
            key = VAULT.get_secret(self.provider)
            if not key:
                raise ProviderError("OpenAI key is not configured.")
            body = {
                "model": self.model,
                "instructions": DEFENSIVE_SYSTEM_PROMPT,
                "input": json.dumps(packet, sort_keys=True),
                "max_output_tokens": 1800,
                "reasoning": {"effort": "medium"},
                "text": {"format": {"type": "json_object"}},
            }
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    self.endpoint,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                response.raise_for_status()
                payload = response.json()
            text = payload.get("output_text")
            if not text:
                parts: list[str] = []
                for item in payload.get("output", []):
                    for content in item.get("content", []) if isinstance(item, dict) else []:
                        if isinstance(content, dict) and content.get("text"):
                            parts.append(str(content["text"]))
                text = "".join(parts)
            return _opinion(
                self.provider,
                self.model,
                str(text or ""),
                int((time.perf_counter() - started) * 1000),
            )
        except Exception as exc:
            return _failure(self.provider, self.model, started, exc)


class XaiGrokClient(ProviderClient):
    provider = "xai"
    model = "grok-4.5"
    endpoint = "https://api.x.ai/v1/responses"

    @property
    def configured(self) -> bool:
        return VAULT.provider_configured(self.provider)

    async def analyze(self, packet: dict[str, Any]) -> ProviderOpinion:
        started = time.perf_counter()
        try:
            key = VAULT.get_secret(self.provider)
            if not key:
                raise ProviderError("xAI key is not configured.")
            body = {
                "model": self.model,
                "input": [
                    {"role": "system", "content": DEFENSIVE_SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(packet, sort_keys=True)},
                ],
                "reasoning": {"effort": "medium"},
                "max_output_tokens": 1800,
                "store": False,
            }
            async with httpx.AsyncClient(timeout=180) as client:
                response = await client.post(
                    self.endpoint,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                response.raise_for_status()
                payload = response.json()
            text = payload.get("output_text")
            if not text:
                parts: list[str] = []
                for item in payload.get("output", []):
                    for content in item.get("content", []) if isinstance(item, dict) else []:
                        if isinstance(content, dict) and content.get("text"):
                            parts.append(str(content["text"]))
                text = "".join(parts)
            return _opinion(
                self.provider,
                self.model,
                str(text or ""),
                int((time.perf_counter() - started) * 1000),
            )
        except Exception as exc:
            return _failure(self.provider, self.model, started, exc)


class DigitalOceanKimiClient(ProviderClient):
    provider = "digitalocean"
    model = "kimi-k3"
    endpoint = "https://inference.do-ai.run/v1/chat/completions"

    @property
    def configured(self) -> bool:
        return VAULT.provider_configured(self.provider)

    async def analyze(self, packet: dict[str, Any]) -> ProviderOpinion:
        started = time.perf_counter()
        try:
            key = VAULT.get_secret(self.provider)
            if not key:
                raise ProviderError("DigitalOcean model access key is not configured.")
            body = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": DEFENSIVE_SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(packet, sort_keys=True)},
                ],
                "temperature": 0.15,
                "max_completion_tokens": 1800,
                "response_format": {"type": "json_object"},
            }
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    self.endpoint,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                response.raise_for_status()
                payload = response.json()
            text = payload["choices"][0]["message"]["content"]
            return _opinion(
                self.provider,
                self.model,
                str(text),
                int((time.perf_counter() - started) * 1000),
            )
        except Exception as exc:
            return _failure(self.provider, self.model, started, exc)


class GeminiClient(ProviderClient):
    provider = "gemini"
    model = "gemini-3.6-flash"

    @property
    def configured(self) -> bool:
        return VAULT.provider_configured(self.provider)

    async def analyze(self, packet: dict[str, Any]) -> ProviderOpinion:
        started = time.perf_counter()
        try:
            key = VAULT.get_secret(self.provider)
            if not key:
                raise ProviderError("Gemini key is not configured.")
            endpoint = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{self.model}:generateContent"
            )
            body = {
                "systemInstruction": {"parts": [{"text": DEFENSIVE_SYSTEM_PROMPT}]},
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": json.dumps(packet, sort_keys=True)}],
                    }
                ],
                "generationConfig": {
                    "temperature": 0.15,
                    "maxOutputTokens": 1800,
                    "responseMimeType": "application/json",
                },
                "safetySettings": [
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_LOW_AND_ABOVE"}
                ],
            }
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    endpoint,
                    headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                    json=body,
                )
                response.raise_for_status()
                payload = response.json()
            text = payload["candidates"][0]["content"]["parts"][0]["text"]
            return _opinion(
                self.provider,
                self.model,
                str(text),
                int((time.perf_counter() - started) * 1000),
            )
        except Exception as exc:
            return _failure(self.provider, self.model, started, exc)


class LocalModelClient(ProviderClient):
    def __init__(self, profile_id: str) -> None:
        self.profile_id = profile_id
        self.provider = "local"
        self.model = profile_id

    @property
    def configured(self) -> bool:
        return MODEL_MANAGER.status(self.profile_id).loaded

    async def analyze(self, packet: dict[str, Any]) -> ProviderOpinion:
        started = time.perf_counter()
        try:
            prompt = (
                DEFENSIVE_SYSTEM_PROMPT
                + "\n\nAuthorized packet:\n"
                + json.dumps(packet, sort_keys=True)
            )
            text = await asyncio.to_thread(
                MODEL_MANAGER.generate,
                self.profile_id,
                prompt,
                max_tokens=1200,
                temperature=0.12,
                json_mode=True,
            )
            return _opinion(
                self.provider,
                self.model,
                text,
                int((time.perf_counter() - started) * 1000),
            )
        except Exception as exc:
            return _failure(self.provider, self.model, started, exc)


class OfflinePolicyClient(ProviderClient):
    provider = "offline"
    model = "cyberforge-policy-calibrator-v3"

    @property
    def configured(self) -> bool:
        return True

    async def analyze(self, packet: dict[str, Any]) -> ProviderOpinion:
        started = time.perf_counter()
        dimensions = dict(packet.get("simulation", {}).get("dimensionScores", {}))
        ranked = sorted(dimensions.items(), key=lambda item: float(item[1]), reverse=True)
        vectors = tuple(str(item[0]) for item in ranked[:4])
        controls = tuple(
            {
                "credential": "Expand phishing-resistant MFA and rotate exposed secrets.",
                "phishing": "Use protected mail workflows and repeatable simulation training.",
                "endpoint": "Increase EDR coverage, isolation speed, and application control.",
                "api": "Enforce scoped tokens, schema validation, and anomaly-aware rate limits.",
                "cloud": "Continuously compare effective IAM to least-privilege baselines.",
                "physical": "Correlate visitor, badge, camera, and after-hours access signals.",
                "vendor": "Reduce standing vendor access and verify support-session approval.",
                "availability": "Exercise segmented recovery and immutable backup restoration.",
                "data": "Apply data-classification-aware egress controls and canary records.",
            }.get(vector, "Improve telemetry and control coverage for this surface.")
            for vector in vectors
        )
        maximum = float(ranked[0][1]) if ranked else 0.0
        return ProviderOpinion(
            provider=self.provider,
            model=self.model,
            succeeded=True,
            summary=(
                "Offline calibration prioritizes the highest modeled defensive surfaces. "
                "The result is a planning signal derived from scenario evidence and seeded "
                "simulation; it is not a forensic attribution."
            ),
            priority_vectors=vectors,
            controls=controls,
            uncertainty=max(0.12, min(0.85, 0.72 - maximum * 0.45)),
            assumptions=("No live exploitation or active probing was performed.",),
            evidence_needed=(
                "Identity-provider authentication telemetry",
                "Endpoint and network detection coverage inventory",
                "Recent backup restoration evidence",
            ),
            latency_ms=int((time.perf_counter() - started) * 1000),
        )


class ModelCouncil:
    def __init__(self) -> None:
        self.clients: list[ProviderClient] = [
            LocalModelClient(LLAMA3_SMALL.id),
            LocalModelClient(GEMMA4_E2B.id),
            OpenAIClient(),
            XaiGrokClient(),
            DigitalOceanKimiClient(),
            GeminiClient(),
            OfflinePolicyClient(),
        ]

    def status(self) -> list[dict[str, Any]]:
        return [
            {"provider": client.provider, "model": client.model, "configured": client.configured}
            for client in self.clients
        ]

    async def deliberate(
        self,
        packet: dict[str, Any],
        *,
        include_remote: bool,
    ) -> dict[str, Any]:
        selected: list[ProviderClient] = []
        for client in self.clients:
            is_remote = client.provider in {"openai", "xai", "digitalocean", "gemini"}
            if is_remote and not include_remote:
                continue
            if client.configured:
                selected.append(client)
        if not any(client.provider == "offline" for client in selected):
            selected.append(OfflinePolicyClient())
        opinions = await asyncio.gather(*(client.analyze(packet) for client in selected))
        successful = [opinion for opinion in opinions if opinion.succeeded]
        vector_votes: dict[str, float] = {}
        control_votes: dict[str, float] = {}
        for opinion in successful:
            weight = max(0.05, 1.0 - opinion.uncertainty)
            for vector in opinion.priority_vectors:
                vector_votes[vector] = vector_votes.get(vector, 0.0) + weight
            for control in opinion.controls:
                control_votes[control] = control_votes.get(control, 0.0) + weight
        vectors = [
            key for key, _ in sorted(vector_votes.items(), key=lambda item: item[1], reverse=True)
        ][:6]
        controls = [
            key for key, _ in sorted(control_votes.items(), key=lambda item: item[1], reverse=True)
        ][:12]
        disagreement = self._disagreement(successful)
        return {
            "opinions": [opinion.to_dict() for opinion in opinions],
            "consensus": {
                "priorityVectors": vectors,
                "controls": controls,
                "disagreement": disagreement,
                "successfulModels": len(successful),
                "attemptedModels": len(opinions),
                "summary": (
                    f"{len(successful)} model perspectives converged on "
                    f"{', '.join(vectors[:3]) or 'telemetry improvement'}. "
                    f"Disagreement is {disagreement * 100:.0f}%; retain human review."
                ),
            },
        }

    @staticmethod
    def _disagreement(opinions: Iterable[ProviderOpinion]) -> float:
        opinions = list(opinions)
        if len(opinions) < 2:
            return 0.0
        similarities: list[float] = []
        for index, left in enumerate(opinions):
            left_set = set(left.priority_vectors)
            for right in opinions[index + 1 :]:
                right_set = set(right.priority_vectors)
                union = left_set | right_set
                similarities.append(1.0 if not union else len(left_set & right_set) / len(union))
        return max(0.0, min(1.0, 1.0 - sum(similarities) / len(similarities)))


MODEL_COUNCIL = ModelCouncil()
