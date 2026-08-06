"""AEGIS-816 individual-surface lattice for Llama micro-scans.

Ported and generalized from the NAZA vpnscanner lattice pattern
(psutil host metrics → RGB → PennyLane entropic score → PUNKD attention →
chunked llama generation), expanded from VPN-only to **any individual**:

identity, human, endpoint, server, network/vpn, api, cloud, facility, route,
vendor, credential, data, collective, …

Optional GPT-5.6 (OpenAI Responses) rewrites the Llama prompt per surface
context when an OpenAI vault key is available.
"""

from __future__ import annotations

from typing import Any, Callable, Optional
import json
import math
import os
import random
import re
import time

import httpx

from .config import LLAMA3_SMALL
from .models import MODEL_MANAGER
from .prompt_library import surface_scanner_system
from .vault import VAULT

try:
    import psutil
except Exception:  # pragma: no cover
    psutil = None

try:
    import pennylane as qml
    from pennylane import numpy as pnp
except Exception:  # pragma: no cover
    qml = None
    pnp = None

DIMENSIONS = (
    "credential",
    "phishing",
    "endpoint",
    "api",
    "cloud",
    "physical",
    "vendor",
    "availability",
    "data",
)

# Kind → focus hints for specialized individual scanning (not VPN-only).
KIND_FOCUS: dict[str, str] = {
    "identity": "workforce/service identity plane, MFA coverage, reset volume, federation",
    "credential": "privileged and break-glass credentials, standing roles, automation identities",
    "human": "role aggregate human pressure, training load, social engineering surface",
    "endpoint": "managed endpoint fleet, EDR coverage, local admin, travel devices",
    "server": "server and virtualization estate, patch lag, management plane",
    "network": "network edge, DNS integrity, connectivity stability, remote-access paths",
    "vpn": "remote access / VPN / VDI gateways, DNS, session trust, split-tunnel pressure",
    "api": "API edge, token scope, schema validation, rate limits, partner traffic",
    "cloud": "cloud control plane, IAM drift, public exposure, workload identity",
    "facility": "physical facility zones, visitor paths, badge telemetry, after-hours access",
    "route": "route / logistics corridors, remote site connectivity, OT/IT adjacency",
    "vendor": "third-party support mesh, standing access, shared channels",
    "data": "data classes, egress controls, canaries, recovery copies",
    "collective": "multi-domain aggregate surface spanning people, systems, and vendors",
    "api-edge": "internet-facing API edge and conditional access exceptions",
}


def collect_system_metrics() -> dict[str, float]:
    """Host metrics for lattice tuning (psutil when available)."""
    if psutil is None:
        return {"cpu": 0.25, "mem": 0.35, "load1": 0.2, "temp": 0.15, "source": 0.0}
    try:
        cpu = psutil.cpu_percent(interval=0.05) / 100.0
        mem = psutil.virtual_memory().percent / 100.0
        try:
            load_raw = os.getloadavg()[0]
            cpu_cnt = psutil.cpu_count(logical=True) or 1
            load1 = max(0.0, min(1.0, load_raw / max(1.0, float(cpu_cnt))))
        except Exception:
            load1 = cpu
        try:
            temps_map = psutil.sensors_temperatures() or {}
            if temps_map:
                first = next(iter(temps_map.values()))[0].current
                temp = max(0.0, min(1.0, (first - 20.0) / 70.0))
            else:
                temp = 0.15
        except Exception:
            temp = 0.15
        return {
            "cpu": float(max(0.0, min(1.0, cpu))),
            "mem": float(max(0.0, min(1.0, mem))),
            "load1": float(max(0.0, min(1.0, load1))),
            "temp": float(max(0.0, min(1.0, temp))),
            "source": 1.0,
        }
    except Exception:
        return {"cpu": 0.3, "mem": 0.3, "load1": 0.25, "temp": 0.2, "source": 0.0}


def metrics_to_rgb(metrics: dict[str, float]) -> tuple[float, float, float]:
    cpu = metrics.get("cpu", 0.1)
    mem = metrics.get("mem", 0.1)
    temp = metrics.get("temp", 0.1)
    load1 = metrics.get("load1", 0.0)
    r = cpu * (1.0 + load1)
    g = mem * (1.0 + load1 * 0.5)
    b = temp * (0.5 + cpu * 0.5)
    maxi = max(r, g, b, 1.0)
    r, g, b = r / maxi, g / maxi, b / maxi
    return (
        float(max(0.0, min(1.0, r))),
        float(max(0.0, min(1.0, g))),
        float(max(0.0, min(1.0, b))),
    )


def pennylane_entropic_score(rgb: tuple[float, float, float], shots: int = 256) -> float:
    """Quantum-inspired entropic score; classical fallback without PennyLane."""
    if qml is None or pnp is None:
        r, g, b = rgb
        ri = max(0, min(255, int(r * 255)))
        gi = max(0, min(255, int(g * 255)))
        bi = max(0, min(255, int(b * 255)))
        seed = (ri << 16) | (gi << 8) | bi
        random.seed(seed)
        base = 0.3 * r + 0.4 * g + 0.3 * b
        noise = (random.random() - 0.5) * 0.08
        return max(0.0, min(1.0, base + noise))

    dev = qml.device("default.qubit", wires=2, shots=shots)

    @qml.qnode(dev)
    def circuit(a, b, c):  # type: ignore[no-untyped-def]
        qml.RX(a * math.pi, wires=0)
        qml.RY(b * math.pi, wires=1)
        qml.CNOT(wires=[0, 1])
        qml.RZ(c * math.pi, wires=1)
        qml.RX((a + b) * math.pi / 2, wires=0)
        qml.RY((b + c) * math.pi / 2, wires=1)
        return qml.expval(qml.PauliZ(0)), qml.expval(qml.PauliZ(1))

    a, b, c = float(rgb[0]), float(rgb[1]), float(rgb[2])
    try:
        ev0, ev1 = circuit(a, b, c)
        combined = ((ev0 + 1.0) / 2.0 * 0.6) + ((ev1 + 1.0) / 2.0 * 0.4)
        score = 1.0 / (1.0 + math.exp(-6.0 * (combined - 0.5)))
        return float(max(0.0, min(1.0, score)))
    except Exception:
        return float(0.5 * (a + b + c) / 3.0)


def entropic_summary_text(score: float) -> str:
    if score >= 0.75:
        level = "high"
    elif score >= 0.45:
        level = "medium"
    else:
        level = "low"
    return f"entropic_score={score:.3f} (level={level})"


def entropic_to_risk_bias(score: float) -> float:
    """Map entropic score to a small risk bias in [-0.08, +0.08]."""
    return (score - 0.5) * 0.16


def _simple_tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_\-]+", text.lower())


def punkd_analyze(prompt_text: str, top_n: int = 12) -> dict[str, float]:
    toks = _simple_tokenize(prompt_text)
    freq: dict[str, int] = {}
    for token in toks:
        freq[token] = freq.get(token, 0) + 1
    boost = {
        "credential": 2.0,
        "phishing": 2.0,
        "mfa": 1.8,
        "vpn": 1.9,
        "remote": 1.7,
        "api": 1.6,
        "vendor": 1.7,
        "privilege": 1.8,
        "admin": 1.7,
        "exfil": 1.9,
        "ransom": 2.0,
        "malware": 1.8,
        "endpoint": 1.5,
        "identity": 1.6,
        "dns": 1.8,
        "failover": 1.4,
        "backup": 1.5,
        "physical": 1.5,
        "facility": 1.5,
        "human": 1.5,
    }
    scored = {t: c * boost.get(t, 1.0) for t, c in freq.items()}
    items = sorted(scored.items(), key=lambda x: -x[1])[:top_n]
    if not items:
        return {}
    maxv = items[0][1] or 1.0
    return {k: float(v / maxv) for k, v in items}


def punkd_apply(
    prompt_text: str,
    token_weights: dict[str, float],
    profile: str = "balanced",
) -> tuple[str, float]:
    if not token_weights:
        return prompt_text, 1.0
    mean_weight = sum(token_weights.values()) / len(token_weights)
    profile_map = {"conservative": 0.6, "balanced": 1.0, "aggressive": 1.4}
    base = profile_map.get(profile, 1.0)
    multiplier = 1.0 + (mean_weight - 0.5) * 0.8 * (base if base > 1.0 else 1.0)
    multiplier = max(0.6, min(1.8, multiplier))
    sorted_tokens = sorted(token_weights.items(), key=lambda x: -x[1])[:6]
    markers = " ".join(f"<ATTN:{t}:{round(w, 2)}>" for t, w in sorted_tokens)
    patched = prompt_text + "\n\n[PUNKD_MARKERS] " + markers
    return patched, multiplier


def chunked_generate(
    generate_fn: Callable[..., str],
    prompt: str,
    *,
    max_total_tokens: int = 256,
    chunk_tokens: int = 64,
    base_temperature: float = 0.12,
    punkd_profile: str = "balanced",
    json_mode: bool = True,
) -> str:
    """Chunked llama generation with PUNKD temperature modulation (vpnscanner pattern)."""
    assembled = ""
    cur_prompt = prompt
    token_weights = punkd_analyze(prompt, top_n=16)
    iterations = max(1, (max_total_tokens + chunk_tokens - 1) // chunk_tokens)
    prev_tail = ""
    for _ in range(iterations):
        patched_prompt, mult = punkd_apply(cur_prompt, token_weights, profile=punkd_profile)
        temp = max(0.01, min(1.2, base_temperature * mult))
        text = (generate_fn(patched_prompt, max_tokens=chunk_tokens, temperature=temp) or "").strip()
        if not text:
            break
        overlap = 0
        max_ol = min(30, len(prev_tail), len(text))
        for olen in range(max_ol, 0, -1):
            if prev_tail.endswith(text[:olen]):
                overlap = olen
                break
        append_text = text[overlap:] if overlap else text
        assembled += append_text
        prev_tail = assembled[-120:] if len(assembled) > 120 else assembled
        # Early stop when JSON object closes
        if json_mode and assembled.count("{") and assembled.count("}") >= assembled.count("{"):
            break
        if len(text.split()) < max(4, chunk_tokens // 8):
            break
        cur_prompt = prompt + "\n\nAssistant so far:\n" + assembled + "\n\nContinue JSON only:"
    return assembled.strip()


def lattice_tuning_block(include_system_entropy: bool = True) -> dict[str, Any]:
    metrics = collect_system_metrics() if include_system_entropy else {
        "cpu": 0.0, "mem": 0.0, "load1": 0.0, "temp": 0.0, "source": 0.0
    }
    rgb = metrics_to_rgb(metrics)
    score = pennylane_entropic_score(rgb) if include_system_entropy else 0.5
    return {
        "metrics": metrics,
        "rgb": rgb,
        "entropic_score": score,
        "entropic_text": entropic_summary_text(score),
        "risk_bias": entropic_to_risk_bias(score),
        "pennylane": qml is not None,
        "psutil": psutil is not None and metrics.get("source", 0) > 0,
    }


def build_base_surface_prompt(
    surface: dict[str, Any],
    *,
    lattice: dict[str, Any],
    specialized_body: str | None = None,
) -> str:
    """Generalized individual-surface scanner prompt (vpnscanner-style structure)."""
    kind = str(surface.get("kind") or "collective").lower()
    focus = KIND_FOCUS.get(kind, KIND_FOCUS["collective"])
    metrics = lattice.get("metrics") or {}
    metrics_line = (
        "sys_metrics: cpu={cpu:.2f},mem={mem:.2f},load={load1:.2f},temp={temp:.2f}".format(
            cpu=float(metrics.get("cpu", 0)),
            mem=float(metrics.get("mem", 0)),
            load1=float(metrics.get("load1", 0)),
            temp=float(metrics.get("temp", 0)),
        )
        if lattice.get("psutil")
        else "sys_metrics: estimated"
    )
    body = specialized_body or surface_scanner_system()
    identifier = (
        str(surface.get("label") or surface.get("id") or kind).strip() or kind
    )
    packet = json.dumps(surface, sort_keys=True)
    return f"""{body}

You are the AEGIS-816 Llama individual-surface micro-scanner (generalized lattice).
Scan this single authorized individual — kind focus: {focus}.

Your reply is one JSON object only (no markdown fences).

[tuning]
Surface Identifier: {identifier}
Surface Kind: {kind}
{metrics_line}
Quantum State: {lattice.get('entropic_text', 'entropic_score=0.500 (level=medium)')}
PennyLane active: {bool(lattice.get('pennylane'))}
[/tuning]

[action]
1) Normalize surface signals for this individual kind.
2) Evaluate exposure, control strength, human pressure, telemetry confidence.
3) Map discrete defensive pressure into risk/uncertainty in [0,1].
4) Optionally use the system entropic signal as a slight confidence bias only.
5) PUNKD: attend to high-weight tokens for this kind.
6) Emit JSON with risk, uncertainty, vectors, observations, controls, evidence_needed.
[/action]

Allowed vectors: {', '.join(DIMENSIONS)}

Authorized individual surface packet:
{packet}
"""


async def compose_prompt_with_gpt56(
    surface: dict[str, Any],
    *,
    lattice: dict[str, Any],
    timeout: float = 45.0,
) -> tuple[str, str]:
    """Use GPT-5.6 (OpenAI) to rewrite the Llama scanner prompt for this context.

    Returns (prompt, composer) where composer is 'gpt-5.6' or 'local-template'.
    """
    base = build_base_surface_prompt(surface, lattice=lattice)
    if not VAULT.provider_configured("openai"):
        return base, "local-template"
    key = VAULT.get_secret("openai")
    if not key or len(str(key)) < 12:
        return base, "local-template"

    kind = str(surface.get("kind") or "collective")
    instructions = (
        "You are the AEGIS-816 prompt composer for the local Llama-3 individual-surface "
        "micro-scanner. Given a surface kind and packet, rewrite a tight system+user "
        "prompt the small local model will execute. Output ONLY the final prompt text "
        "the Llama model should see. Require JSON output with keys risk, uncertainty, "
        "vectors, observations, controls, evidence_needed. Tailor evaluation criteria "
        "to this individual kind (identity, human, endpoint, server, network/vpn, api, "
        "cloud, facility, route, vendor, credential, data, collective). Include a "
        "[tuning] block with the supplied entropic/system metrics. Keep under 900 words."
    )
    user = {
        "kind": kind,
        "focus": KIND_FOCUS.get(kind.lower(), KIND_FOCUS["collective"]),
        "lattice": {
            "entropic_text": lattice.get("entropic_text"),
            "metrics": lattice.get("metrics"),
            "pennylane": lattice.get("pennylane"),
        },
        "surface": surface,
        "seed_prompt": base[:3500],
        "allowed_vectors": list(DIMENSIONS),
    }
    try:
        body = {
            "model": "gpt-5.6",
            "instructions": instructions,
            "input": json.dumps(user, sort_keys=True),
            "max_output_tokens": 1200,
            "reasoning": {"effort": "medium"},
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
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
        text = (text or "").strip()
        if len(text) < 80:
            return base, "local-template"
        # Ensure packet and tuning survive rewrites
        if "Authorized individual surface packet" not in text and "surface" not in text.lower():
            text = text + "\n\nAuthorized individual surface packet:\n" + json.dumps(
                surface, sort_keys=True
            )
        return text, "gpt-5.6"
    except Exception:
        return base, "local-template"


def parse_micro_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        # Low/Medium/High fallback from vpnscanner heritage
        lowered = text.lower()
        if "high" in lowered:
            return {"risk": 0.78, "uncertainty": 0.35, "vectors": ["endpoint"], "observations": [text[:200]], "controls": [], "evidence_needed": []}
        if "low" in lowered:
            return {"risk": 0.28, "uncertainty": 0.3, "vectors": ["endpoint"], "observations": [text[:200]], "controls": [], "evidence_needed": []}
        if "medium" in lowered:
            return {"risk": 0.52, "uncertainty": 0.4, "vectors": ["endpoint"], "observations": [text[:200]], "controls": [], "evidence_needed": []}
        raise ValueError("no JSON in micro-scan output")
    payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("micro-scan payload is not an object")
    return payload


async def scan_individual_surface(
    surface: dict[str, Any],
    *,
    use_gpt_composer: bool = True,
    use_chunked: bool = True,
    include_system_entropy: bool = True,
) -> dict[str, Any]:
    """Run lattice-tuned Llama micro-scan for one individual surface."""
    if not MODEL_MANAGER.status(LLAMA3_SMALL.id).loaded:
        raise RuntimeError("llama3-small-q3 is not loaded")

    lattice = lattice_tuning_block(include_system_entropy=include_system_entropy)
    if use_gpt_composer:
        prompt, composer = await compose_prompt_with_gpt56(surface, lattice=lattice)
    else:
        prompt = build_base_surface_prompt(surface, lattice=lattice)
        composer = "local-template"

    def _gen(p: str, max_tokens: int = 220, temperature: float = 0.1) -> str:
        return MODEL_MANAGER.generate(
            LLAMA3_SMALL.id,
            p,
            max_tokens=max_tokens,
            temperature=temperature,
            json_mode=True,
        )

    started = time.perf_counter()
    if use_chunked:
        text = chunked_generate(
            _gen,
            prompt,
            max_total_tokens=280,
            chunk_tokens=72,
            base_temperature=0.1,
            punkd_profile="balanced",
            json_mode=True,
        )
    else:
        text = _gen(prompt, max_tokens=220, temperature=0.08)

    payload = parse_micro_json(text)
    bias = float(lattice.get("risk_bias") or 0.0)
    risk = max(0.0, min(1.0, float(payload.get("risk", 0.5)) + bias))
    uncertainty = max(0.0, min(1.0, float(payload.get("uncertainty", 0.5))))
    vectors = [
        str(item)
        for item in payload.get("vectors", [])
        if str(item) in DIMENSIONS
    ][:4]
    return {
        "risk": risk,
        "uncertainty": uncertainty,
        "vectors": vectors,
        "observations": [str(item)[:240] for item in payload.get("observations", [])][:4],
        "controls": [str(item)[:280] for item in payload.get("controls", [])][:4],
        "evidence_needed": [str(item)[:240] for item in payload.get("evidence_needed", [])][:4],
        "lattice": {
            "entropic_score": lattice.get("entropic_score"),
            "entropic_text": lattice.get("entropic_text"),
            "risk_bias": bias,
            "pennylane": lattice.get("pennylane"),
            "psutil": lattice.get("psutil"),
            "composer": composer,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        },
    }
