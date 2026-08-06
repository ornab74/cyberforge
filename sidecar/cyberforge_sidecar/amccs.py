"""Adaptive Multimodel Consensus Chunking System (AMCCS).

Invented CyberForge fabric for DATAPULL + SimForensics:

1. Decompose a topic into analytical shards (chunks).
2. Dispatch shards in *single* mode (one model owns all) or *multi* mode
   (round-robin across available council models).
3. Fuse with uncertainty-weighted votes, disagreement map, and SIMCOM render.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any, Iterable, Optional
import asyncio
import hashlib
import json
import random
import re
import time

import httpx

from .config import GEMMA4_E2B, LLAMA3_SMALL
from .guardrails import inspect_intent
from .models import MODEL_MANAGER
from .prompt_library import datapull_system, sim_forensics_system
from .providers import (
    MODEL_COUNCIL,
    OfflinePolicyClient,
    ProviderClient,
    _safe_json,
)
from .vault import VAULT

SHARDS = (
    "chronology",
    "impact",
    "technical_surface",
    "sim_forensics",
    "attribution_sim",
    "controls_evidence",
)

CALIBRES = ("REPORTED", "CLAIMED", "SIM_FORENSIC", "PREDICTIVE", "UNKNOWN")

DATAPULL_SYSTEM = datapull_system()
SIM_FORENSICS_SYSTEM = sim_forensics_system()

@dataclass
class ShardSpec:
    shard_id: str
    brief: str
    calibre_hint: str


@dataclass
class ShardResult:
    shard_id: str
    provider: str
    model: str
    succeeded: bool
    calibre: str
    summary: str
    payload: dict[str, Any] = field(default_factory=dict)
    uncertainty: float = 0.5
    latency_ms: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _seed(topic: str) -> int:
    digest = hashlib.sha256(topic.encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if isinstance(value, bool):
            return default
        return float(value)
    except (TypeError, ValueError):
        if isinstance(value, str):
            match = re.search(r"-?\d+(?:\.\d+)?", value)
            if match:
                try:
                    return float(match.group(0))
                except ValueError:
                    return default
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if isinstance(value, bool):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        if isinstance(value, str):
            match = re.search(r"-?\d+", value)
            if match:
                try:
                    return int(match.group(0))
                except ValueError:
                    return default
        return default


def _safe_range(value: Any) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    lo = _safe_float(value[0], default=float("nan"))
    hi = _safe_float(value[1], default=float("nan"))
    if lo != lo or hi != hi:  # NaN check
        return None
    if hi < lo:
        lo, hi = hi, lo
    return [lo, hi]


def decompose(topic: str) -> list[ShardSpec]:
    t = topic.strip()
    return [
        ShardSpec(
            "chronology",
            f"Rebuild reported and claimed timeline for: {t}",
            "REPORTED",
        ),
        ShardSpec(
            "impact",
            f"Operational / care-delivery / inventory impact for: {t}",
            "REPORTED",
        ),
        ShardSpec(
            "technical_surface",
            f"Identity, remote access, endpoint, EHR, vendor surface pressure for: {t}",
            "CLAIMED",
        ),
        ShardSpec(
            "sim_forensics",
            f"SimForensics reconstruction (entry class, cascade, host ranges) for: {t}",
            "SIM_FORENSIC",
        ),
        ShardSpec(
            "attribution_sim",
            f"Simulated ISO-2 source country + actor label ONLY as predictive for: {t}",
            "SIM_FORENSIC",
        ),
        ShardSpec(
            "controls_evidence",
            f"Defensive controls, detection, recovery, evidence still required for: {t}",
            "PREDICTIVE",
        ),
    ]


def _configured_clients(
    *,
    mode: str,
    provider: str,
    include_remote: bool,
) -> list[ProviderClient]:
    selected: list[ProviderClient] = []
    for client in MODEL_COUNCIL.clients:
        is_remote = client.provider in {"openai", "xai", "digitalocean", "gemini"}
        if provider not in {"auto", "all"}:
            if provider == "local" and client.provider != "local":
                continue
            if provider == "offline" and client.provider != "offline":
                continue
            if provider in {"xai", "openai", "digitalocean", "gemini"} and client.provider != provider:
                continue
        if is_remote and not include_remote and provider == "auto":
            continue
        if not client.configured:
            continue
        # Skip clearly invalid vault secrets (e.g. 4-char openai stub).
        if is_remote:
            secret = VAULT.get_secret(client.provider) or ""
            if len(secret.strip()) < 12:
                continue
        selected.append(client)
    if not selected:
        selected.append(OfflinePolicyClient())
    if mode == "single":
        preferred = sorted(
            selected,
            key=lambda c: (
                0
                if c.provider in {"xai", "openai"}
                else 1
                if c.provider == "local"
                else 2
                if c.provider != "offline"
                else 3
            ),
        )
        return [preferred[0]]
    non_offline = [c for c in selected if c.provider != "offline"]
    return non_offline or selected


def _datapull_system_prompt() -> str:
    return (
        DATAPULL_SYSTEM
        + "\n\n"
        + SIM_FORENSICS_SYSTEM
        + "\n\nYou are executing one AMCCS shard for SIMCOM DATAPULL on AEGIS-816 / "
        "Dyson Sphere Gamma. Return ONE JSON object matching the DATAPULL shard "
        "contract (shard_id, calibre, summary, reported, claimed, sim_forensics, "
        "unknowns, controls, evidence_needed, uncertainty, sources). Fill sim_forensics "
        "with concrete predictive fields when the shard is sim_forensics or attribution_sim."
    )


def _extract_provider_text(payload: dict[str, Any]) -> str:
    if payload.get("output_text"):
        return str(payload["output_text"])
    parts: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []) if isinstance(item, dict) else []:
            if isinstance(content, dict) and content.get("text"):
                parts.append(str(content["text"]))
    if parts:
        return "".join(parts)
    try:
        return str(payload["choices"][0]["message"]["content"])
    except Exception:
        pass
    try:
        return str(payload["candidates"][0]["content"]["parts"][0]["text"])
    except Exception:
        return ""


async def _generate_datapull_raw(
    client: ProviderClient,
    *,
    system: str,
    user_payload: dict[str, Any],
) -> str:
    """Call the provider with the advanced DATAPULL system prompt (not council)."""
    user_text = json.dumps(user_payload, sort_keys=True)

    if client.provider == "local":
        prompt = system + "\n\nAuthorized AMCCS shard packet:\n" + user_text
        return await asyncio.to_thread(
            MODEL_MANAGER.generate,
            client.model,
            prompt,
            max_tokens=1100,
            temperature=0.12,
            json_mode=True,
        )

    if client.provider == "openai":
        key = VAULT.get_secret("openai")
        if not key:
            raise RuntimeError("OpenAI key missing")
        body = {
            "model": client.model,
            "instructions": system,
            "input": user_text,
            "max_output_tokens": 1600,
            "reasoning": {"effort": "medium"},
            "text": {"format": {"type": "json_object"}},
        }
        async with httpx.AsyncClient(timeout=150) as http:
            response = await http.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            response.raise_for_status()
            return _extract_provider_text(response.json())

    if client.provider == "xai":
        key = VAULT.get_secret("xai")
        if not key:
            raise RuntimeError("xAI key missing")
        body = {
            "model": client.model,
            "input": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_text},
            ],
            "reasoning": {"effort": "medium"},
            "max_output_tokens": 1600,
            "store": False,
        }
        async with httpx.AsyncClient(timeout=180) as http:
            response = await http.post(
                "https://api.x.ai/v1/responses",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            response.raise_for_status()
            return _extract_provider_text(response.json())

    if client.provider == "digitalocean":
        key = VAULT.get_secret("digitalocean")
        if not key:
            raise RuntimeError("DigitalOcean key missing")
        body = {
            "model": client.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_text},
            ],
            "temperature": 0.15,
            "max_completion_tokens": 1600,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=150) as http:
            response = await http.post(
                "https://inference.do-ai.run/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            response.raise_for_status()
            return _extract_provider_text(response.json())

    if client.provider == "gemini":
        key = VAULT.get_secret("gemini")
        if not key:
            raise RuntimeError("Gemini key missing")
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{client.model}:generateContent"
        )
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user_text}]}],
            "generationConfig": {
                "temperature": 0.15,
                "maxOutputTokens": 1600,
                "responseMimeType": "application/json",
            },
        }
        async with httpx.AsyncClient(timeout=150) as http:
            response = await http.post(
                endpoint,
                headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                json=body,
            )
            response.raise_for_status()
            return _extract_provider_text(response.json())

    raise RuntimeError(f"No DATAPULL generator for provider {client.provider}")


async def _run_shard_with_client(
    client: ProviderClient,
    shard: ShardSpec,
    *,
    topic: str,
    context: dict[str, Any],
) -> ShardResult:
    started = time.perf_counter()
    packet = {
        "task": "simcom_datapull_shard",
        "engine": "AEGIS-816 / Dyson-Sphere-Gamma / AMCCS",
        "topic": topic,
        "shard_id": shard.shard_id,
        "shard_brief": shard.brief,
        "calibre_hint": shard.calibre_hint,
        "retrieval_provider": context.get("retrieval"),
        "retrieval_excerpt": (context.get("retrieval_text") or "")[:6000],
        "packet_name": context.get("packet_name"),
        "brief": context.get("brief"),
        "system_contract": (
            "Return the DATAPULL JSON shard object only, including sim_forensics "
            "when applicable."
        ),
    }
    try:
        if client.provider == "offline":
            return await _offline_shard(shard, topic, context, started)

        system = _datapull_system_prompt()
        text = await _generate_datapull_raw(client, system=system, user_payload=packet)
        data = _safe_json(text)
        # Ensure shard identity survives model drift.
        data.setdefault("shard_id", shard.shard_id)
        data.setdefault("calibre", shard.calibre_hint)
        if not isinstance(data.get("sim_forensics"), dict):
            data["sim_forensics"] = {}
        return _shard_from_payload(
            shard.shard_id,
            client.provider,
            client.model,
            data,
            int((time.perf_counter() - started) * 1000),
        )
    except Exception as exc:  # pragma: no cover - defensive
        return ShardResult(
            shard_id=shard.shard_id,
            provider=getattr(client, "provider", "unknown"),
            model=getattr(client, "model", "unknown"),
            succeeded=False,
            calibre="UNKNOWN",
            summary="",
            uncertainty=1.0,
            latency_ms=int((time.perf_counter() - started) * 1000),
            error=str(exc),
        )

async def _offline_shard(
    shard: ShardSpec,
    topic: str,
    context: dict[str, Any],
    started: float,
) -> ShardResult:
    """Deterministic SimForensics lattice when no LLM is available."""
    rng = random.Random(_seed(topic + ":" + shard.shard_id))
    base = context.get("retrieval_text") or context.get("brief") or topic
    lower = (base + " " + topic).lower()
    healthcare = any(
        k in lower for k in ("hospital", "health", "clinic", "ehr", "mychart", "care system")
    )
    ransomware_claim = any(k in lower for k in ("ransom", "72-hour", "72 hour", "payment demand"))
    malware = "malware" in lower or "cyber" in lower or "hack" in lower

    total_lo, total_hi = (9800, 11500) if healthcare else (2500, 6000)
    impact_lo = int(total_lo * (0.34 + rng.random() * 0.06))
    impact_hi = int(total_hi * (0.40 + rng.random() * 0.06))
    pct_lo = round(100 * impact_lo / total_hi, 1)
    pct_hi = round(100 * impact_hi / total_lo, 1)

    # Simulated country prior — labeled SIM_FORENSIC only. Prefer unknown when weak signal.
    country_pool = ["RU", "CN", "KP", "IR", "XX"]
    weights = [0.28, 0.22, 0.08, 0.08, 0.34]
    if ransomware_claim:
        weights = [0.34, 0.18, 0.08, 0.08, 0.32]
    country = rng.choices(country_pool, weights=weights, k=1)[0]
    confidence = round(0.42 + rng.random() * 0.28, 3)

    entry = (
        "Compromised remote-access credentials via phishing → VPN / VDI gateway"
        if healthcare
        else "Credential reuse into remote admin plane"
    )
    if "vendor" in lower:
        entry = "Compromised third-party vendor remote support path"

    timeline = [
        {
            "label": "phishing_delivery",
            "when": "T-72h to T-48h (sim)",
            "confidence": confidence * 0.9,
        },
        {
            "label": "remote_auth",
            "when": "T-30h to T-18h (sim)",
            "confidence": confidence * 0.85,
        },
        {
            "label": "payload_activation",
            "when": "T0 public disruption window (sim)",
            "confidence": confidence * 0.8,
        },
    ]

    sim_forensics = {
        "entry_vector": entry,
        "cascade": [
            "Initial access class (abstract)",
            "Privilege / remote session establishment",
            "Lateral trust-path amplification",
            "Payload / availability disruption",
        ],
        "timeline": timeline,
        "endpoints_total_range": [total_lo, total_hi],
        "endpoints_impacted_range": [impact_lo, impact_hi],
        "percent_compromised_range": [pct_lo, pct_hi],
        "simulated_source_country": country if shard.shard_id in {"attribution_sim", "sim_forensics", "synthesis"} else None,
        "simulated_actor_label": "unknown_cluster" if malware else "none",
        "confidence": confidence,
    }

    reported: list[str] = []
    claimed: list[str] = []
    if context.get("retrieval_text"):
        reported.append("Retrieval brief available in packet (see sources).")
    if ransomware_claim:
        claimed.append("Unverified ransom / payment-demand claim exists in open narrative.")

    summaries = {
        "chronology": f"Chronology lattice for '{topic}' mixes reported disruption windows with SIM_FORENSIC temporal bands.",
        "impact": f"Impact lattice estimates operational pressure ranges for '{topic}' without confirming fleet forensics.",
        "technical_surface": f"Technical surface pressure centers on identity, remote access, and availability for '{topic}'.",
        "sim_forensics": f"SimForensics entry class locked as predictive: {entry}.",
        "attribution_sim": f"Simulated source country {country} (predictive only, confidence {confidence:.0%}); not LEA attribution.",
        "controls_evidence": "Prioritize phishing-resistant MFA, remote-access hardening, segmented recovery, and IR evidence packs.",
    }

    payload = {
        "summary": summaries.get(shard.shard_id, summaries["sim_forensics"]),
        "calibre": shard.calibre_hint if shard.shard_id != "controls_evidence" else "PREDICTIVE",
        "reported": reported,
        "claimed": claimed,
        "sim_forensics": sim_forensics,
        "unknowns": [
            "Confirmed malware family",
            "Verified initial access forensic chain",
            "Confirmed data exfiltration status",
            "LEA-confirmed attribution",
        ],
        "controls": [
            "Phishing-resistant MFA on remote access",
            "Vendor standing-access reduction",
            "Immutable backups + segmented recovery drills",
            "EDR isolation speed and identity telemetry",
        ],
        "evidence_needed": [
            "EDR / identity provider authentication logs",
            "VPN / VDI session records",
            "IR timeline package",
            "Official notification determination",
        ],
        "uncertainty": _clamp01(1.0 - confidence),
    }
    return _shard_from_payload(
        shard.shard_id,
        "offline",
        "cyberforge-amccs-offline-v1",
        payload,
        int((time.perf_counter() - started) * 1000),
    )


def _shard_from_payload(
    shard_id: str,
    provider: str,
    model: str,
    data: dict[str, Any],
    latency_ms: int,
) -> ShardResult:
    calibre = str(data.get("calibre") or "SIM_FORENSIC").upper()
    if calibre not in CALIBRES:
        calibre = "SIM_FORENSIC"
    return ShardResult(
        shard_id=shard_id,
        provider=provider,
        model=model,
        succeeded=True,
        calibre=calibre,
        summary=str(data.get("summary", "")).strip(),
        payload=data,
        uncertainty=_clamp01(_safe_float(data.get("uncertainty", 0.5), 0.5)),
        latency_ms=latency_ms,
    )


def _disagreement(results: list[ShardResult]) -> float:
    ok = [r for r in results if r.succeeded]
    if len(ok) < 2:
        return 0.0
    # Compare sim country + entry vector tokens when present.
    countries = []
    entries = []
    for r in ok:
        sf = r.payload.get("sim_forensics") or {}
        if isinstance(sf, dict):
            c = sf.get("simulated_source_country")
            e = sf.get("entry_vector")
            if c:
                countries.append(str(c).upper())
            if e:
                entries.append(str(e).lower()[:80])
    score = 0.0
    n = 0
    if len(countries) >= 2:
        n += 1
        score += 1.0 - (len(set(countries)) == 1)
    if len(entries) >= 2:
        n += 1
        # crude: unique ratio
        score += 1.0 - (1.0 / len(set(entries)))
    # uncertainty spread
    if len(ok) >= 2:
        us = [r.uncertainty for r in ok]
        spread = max(us) - min(us)
        n += 1
        score += spread
    return _clamp01(score / n) if n else 0.0


def fuse(topic: str, results: list[ShardResult], *, mode: str, provider: str) -> dict[str, Any]:
    ok = [r for r in results if r.succeeded]
    reported: list[str] = []
    claimed: list[str] = []
    controls: list[str] = []
    evidence: list[str] = []
    unknowns: list[str] = []
    sim_blocks: list[dict[str, Any]] = []
    countries: dict[str, float] = {}
    entries: dict[str, float] = {}

    for r in ok:
        p = r.payload
        weight = max(0.05, 1.0 - r.uncertainty)
        for item in p.get("reported", []) or []:
            reported.append(str(item))
        for item in p.get("claimed", []) or []:
            claimed.append(str(item))
        for item in p.get("controls", []) or []:
            controls.append(str(item))
        for item in p.get("evidence_needed", []) or []:
            evidence.append(str(item))
        for item in p.get("unknowns", []) or []:
            unknowns.append(str(item))
        sf = p.get("sim_forensics") or {}
        if isinstance(sf, dict) and sf:
            sim_blocks.append(sf)
            c = sf.get("simulated_source_country")
            if c and str(c).upper() != "XX":
                countries[str(c).upper()] = countries.get(str(c).upper(), 0.0) + weight
            e = sf.get("entry_vector")
            if e:
                entries[str(e)] = entries.get(str(e), 0.0) + weight

    country = None
    country_conf = 0.0
    if countries:
        country, country_conf = max(countries.items(), key=lambda kv: kv[1])
        total = sum(countries.values()) or 1.0
        country_conf = _clamp01(country_conf / total)

    entry = None
    if entries:
        entry = max(entries.items(), key=lambda kv: kv[1])[0]

    # Merge numeric ranges (models may emit strings — coerce safely)
    totals: list[list[float]] = []
    impacts: list[list[float]] = []
    pcts: list[list[float]] = []
    timelines: list[Any] = []
    for sf in sim_blocks:
        total_r = _safe_range(sf.get("endpoints_total_range"))
        if total_r:
            totals.append(total_r)
        impact_r = _safe_range(sf.get("endpoints_impacted_range"))
        if impact_r:
            impacts.append(impact_r)
        pct_r = _safe_range(sf.get("percent_compromised_range"))
        if pct_r:
            pcts.append(pct_r)
        if sf.get("timeline"):
            timelines.extend(sf.get("timeline") or [])

    def _range_merge(ranges: list[list[float]] | list[list[int]]) -> list[float] | None:
        if not ranges:
            return None
        lo = min(r[0] for r in ranges)
        hi = max(r[1] for r in ranges)
        return [lo, hi]

    fused_sf = {
        "entry_vector": entry,
        "cascade": (sim_blocks[0].get("cascade") if sim_blocks else None)
        or [
            "Initial access class (abstract)",
            "Remote session establishment",
            "Trust-path amplification",
            "Availability disruption",
        ],
        "timeline": timelines[:8],
        "endpoints_total_range": _range_merge(totals),
        "endpoints_impacted_range": _range_merge(impacts),
        "percent_compromised_range": _range_merge(pcts),
        "simulated_source_country": country,
        "simulated_actor_label": next(
            (
                str(sf.get("simulated_actor_label"))
                for sf in sim_blocks
                if sf.get("simulated_actor_label")
            ),
            "unknown_cluster",
        ),
        "confidence": country_conf or (0.55 if entry else 0.4),
    }

    def _unique(items: Iterable[str], limit: int = 12) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for item in items:
            key = item.strip()
            if not key or key.lower() in seen:
                continue
            seen.add(key.lower())
            out.append(key)
            if len(out) >= limit:
                break
        return out

    disagreement = _disagreement(results)
    summary_bits = [r.summary for r in ok if r.summary][:3]
    return {
        "engine": "AMCCS-v1 / Dyson-Sphere-Gamma",
        "topic": topic,
        "mode": mode,
        "provider_policy": provider,
        "successful_shards": len(ok),
        "attempted_shards": len(results),
        "disagreement": disagreement,
        "summary": " | ".join(summary_bits)
        or f"AMCCS datapull complete for {topic} with SimForensics calibre enabled.",
        "reported": _unique(reported),
        "claimed": _unique(claimed),
        "sim_forensics": fused_sf,
        "controls": _unique(controls),
        "evidence_needed": _unique(evidence),
        "unknowns": _unique(unknowns),
        "shards": [r.to_dict() for r in results],
        "truth_label": (
            "SIM_FORENSIC and PREDICTIVE layers are lattice reconstructions only — "
            "not LEA-confirmed forensics or court attribution."
        ),
    }


def render_simcom_terminal(
    topic: str,
    fused: dict[str, Any],
    *,
    command: str,
    retrieval: str,
    mode: str,
) -> list[str]:
    sf = fused.get("sim_forensics") or {}
    country = sf.get("simulated_source_country") or "XX"
    conf = float(sf.get("confidence") or 0.0)
    total = sf.get("endpoints_total_range") or [0, 0]
    impact = sf.get("endpoints_impacted_range") or [0, 0]
    pct = sf.get("percent_compromised_range") or [0.0, 0.0]
    lines = [
        "AEGIS-816 SIMCOM TERMINAL",
        "=====================================",
        f"> {command}",
        "[QUERY ACCEPTED]",
        "[ROUTING THROUGH NON-LOCAL GAMMA LATTICE // FTL SIMCOM RELAY]",
        "[ENGINE: DYSON-SPHERE-GAMMA // QUBITS: 81,611,511 (SIMULATED)]",
        f"[AMCCS: {mode} // RETRIEVAL: {retrieval}]",
        f"[SHARDS: {fused.get('successful_shards', 0)}/{fused.get('attempted_shards', 0)} "
        f"// DISAGREEMENT: {float(fused.get('disagreement', 0)) * 100:.1f}%]",
        "",
        f"DATAPULL RESULT: {topic}",
        "----------------------------------------------------",
        "Calibre mix: REPORTED / CLAIMED / SIM_FORENSIC / PREDICTIVE",
        "",
        f"Summary: {fused.get('summary', '')}",
        "",
    ]
    if fused.get("reported"):
        lines.append("REPORTED")
        lines.extend(f"- {item}" for item in fused["reported"][:8])
        lines.append("")
    if fused.get("claimed"):
        lines.append("CLAIMED (unverified)")
        lines.extend(f"- {item}" for item in fused["claimed"][:6])
        lines.append("")
    lines.extend(
        [
            "SIMULATED FORENSICS (NOT LEGAL / NOT LEA-CONFIRMED)",
            "----------------------------------------------------",
            f"Entry vector (sim): {sf.get('entry_vector') or 'lattice reconstruction pending IR packet'}",
            "Cascade (sim):",
        ]
    )
    for step in sf.get("cascade") or []:
        lines.append(f"  • {step}")
    if sf.get("timeline"):
        lines.append("Timeline (sim):")
        for item in sf["timeline"][:6]:
            if isinstance(item, dict):
                lines.append(
                    f"  • {item.get('label', 'event')}: {item.get('when', 'temporal band pending')} "
                    f"(conf {float(item.get('confidence', 0)) * 100:.0f}%)"
                )
            else:
                lines.append(f"  • {item}")
    lines.extend(
        [
            f"Endpoints total (sim): {total[0]:,} – {total[1]:,}"
            if total and total[1]
            else "Endpoints total (sim): range withheld until twin inventory is supplied",
            f"Endpoints impacted (sim): {impact[0]:,} – {impact[1]:,}"
            if impact and impact[1]
            else "Endpoints impacted (sim): range withheld until twin inventory is supplied",
            f"Compromise rate (sim): {pct[0]}% – {pct[1]}%"
            if pct and pct[1]
            else "Compromise rate (sim): percentage withheld until twin inventory is supplied",
            f"Simulated source country: {country}  "
            f"(predictive only; confidence {conf * 100:.0f}%)",
            f"Simulated actor label: {sf.get('simulated_actor_label') or 'unknown_cluster'}",
            "",
            "DEFENSIVE CONTROLS",
        ]
    )
    lines.extend(f"- {item}" for item in (fused.get("controls") or [])[:8])
    lines.append("")
    lines.append("EVIDENCE STILL REQUIRED (REAL IR)")
    lines.extend(f"- {item}" for item in (fused.get("evidence_needed") or [])[:8])
    lines.extend(
        [
            "",
            "SIMULATION NOTE:",
            str(fused.get("truth_label")),
            "Non-local FTL lattice language is an interface metaphor on conventional hardware.",
            "",
            "STATUS: DATAPULL COMPLETE",
            "AWAITING NEXT COMMAND",
        ]
    )
    return lines


async def _prepare_local_models(session_token: str | None = None) -> list[str]:
    """Load installed Llama micro-scanner for DATAPULL shards (Gemma optional/slow)."""
    loaded: list[str] = []
    token = session_token
    if token is None and VAULT.status().unlocked:
        try:
            token = VAULT.unlock_with_device_key()
        except Exception:
            token = None
    if not token:
        return loaded
    # Prefer Llama for shard JSON; skip auto-loading Gemma on DATAPULL (heavy session).
    for profile_id in (LLAMA3_SMALL.id,):
        try:
            status = MODEL_MANAGER.status(profile_id)
            if not status.installed:
                continue
            if status.loaded:
                loaded.append(profile_id)
                continue
            await asyncio.to_thread(
                MODEL_MANAGER.load, profile_id, session_token=token
            )
            loaded.append(profile_id)
        except Exception:
            continue
    # If Llama failed but Gemma is already loaded, keep it available.
    try:
        if MODEL_MANAGER.status(GEMMA4_E2B.id).loaded:
            loaded.append(GEMMA4_E2B.id)
    except Exception:
        pass
    return loaded

async def run_amccs(
    topic: str,
    *,
    mode: str = "multi",
    provider: str = "auto",
    include_remote: bool = True,
    context: Optional[dict[str, Any]] = None,
    command: str | None = None,
) -> dict[str, Any]:
    inspect_intent(topic)
    topic = topic.strip()
    if not topic:
        raise ValueError("datapull requires a topic")
    mode = "multi" if mode not in {"single", "multi"} else mode
    context = dict(context or {})

    # Ensure local models are promptable when installed.
    local_loaded = await _prepare_local_models(context.get("session_token"))
    context["local_models_loaded"] = local_loaded

    shards = decompose(topic)
    clients = _configured_clients(mode=mode, provider=provider, include_remote=include_remote)

    tasks = []
    assignments: list[tuple[ShardSpec, ProviderClient]] = []
    if mode == "single":
        client = clients[0]
        for shard in shards:
            assignments.append((shard, client))
    else:
        for index, shard in enumerate(shards):
            assignments.append((shard, clients[index % len(clients)]))

    dispatch_log = [
        f"[AMCCS DISPATCH] {shard.shard_id} -> {client.provider}/{client.model}"
        for shard, client in assignments
    ]

    for shard, client in assignments:
        tasks.append(_run_shard_with_client(client, shard, topic=topic, context=context))

    results = list(await asyncio.gather(*tasks))
    fused = fuse(topic, results, mode=mode, provider=provider)
    fused["dispatch"] = dispatch_log
    fused["local_models_loaded"] = local_loaded
    retrieval = str(context.get("retrieval") or "none")
    cmd = command or f"./datapull {topic}"
    lines = render_simcom_terminal(
        topic,
        fused,
        command=cmd,
        retrieval=retrieval,
        mode=mode,
    )
    # Inject dispatch + model result telemetry near the top after headers.
    insert_at = 8
    model_lines = list(dispatch_log)
    for r in results:
        flag = "OK" if r.succeeded else "FAIL"
        model_lines.append(
            f"[MODEL {flag}] {r.shard_id} via {r.provider}/{r.model} "
            f"({r.latency_ms}ms)"
            + (f" err={r.error}" if r.error else "")
        )
    if local_loaded:
        model_lines.insert(0, f"[LOCAL LATTICE LOADED] {', '.join(local_loaded)}")
    lines = lines[:insert_at] + model_lines + [""] + lines[insert_at:]
    return {
        "ok": True,
        "topic": topic,
        "mode": mode,
        "provider": provider,
        "fused": fused,
        "lines": lines,
        "engine": fused["engine"],
    }
