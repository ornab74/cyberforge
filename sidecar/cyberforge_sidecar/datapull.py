"""SIMCOM DATAPULL orchestration — retrieval + AMCCS SimForensics fabric."""

from __future__ import annotations

from typing import Any, Optional
import re

from .amccs import run_amccs
from .guardrails import inspect_intent
from .news import capture_news, NewsCaptureError
from .vault import VAULT


def parse_datapull_command(tokens: list[str]) -> dict[str, Any]:
    """Parse: datapull|/datapull|./datapull <topic...> [--mode single|multi] [--provider X]"""
    raw = list(tokens)
    if raw and raw[0].lower().lstrip("./") in {"datapull", "evidence", "reconstruct"}:
        raw = raw[1:]
    mode = "multi"
    provider = "auto"
    topic_parts: list[str] = []
    index = 0
    while index < len(raw):
        tok = raw[index]
        if tok == "--mode" and index + 1 < len(raw):
            mode = raw[index + 1].lower()
            index += 2
            continue
        if tok.startswith("--mode="):
            mode = tok.split("=", 1)[1].lower()
            index += 1
            continue
        if tok == "--provider" and index + 1 < len(raw):
            provider = raw[index + 1].lower()
            index += 2
            continue
        if tok.startswith("--provider="):
            provider = tok.split("=", 1)[1].lower()
            index += 1
            continue
        if tok in {"--remote"}:
            # force remote-capable providers when auto
            if provider == "auto":
                provider = "auto"
            index += 1
            continue
        if tok in {"--local"}:
            provider = "local"
            index += 1
            continue
        if tok in {"--offline"}:
            provider = "offline"
            index += 2 if False else 1
            continue
        topic_parts.append(tok)
        index += 1
    topic = " ".join(topic_parts).strip()
    # Allow patterns like: via simcom terminal ()origin of <topic>
    topic = re.sub(r"^via\s+simcom\s+terminal\s*\(\)\s*", "", topic, flags=re.I).strip()
    if mode not in {"single", "multi"}:
        mode = "multi"
    if provider not in {"auto", "xai", "openai", "local", "offline", "digitalocean", "gemini"}:
        provider = "auto"
    return {"topic": topic, "mode": mode, "provider": provider}


async def execute_datapull(
    topic: str,
    *,
    mode: str = "multi",
    provider: str = "auto",
    command: str | None = None,
    packet: Optional[dict[str, Any]] = None,
    allow_retrieval: bool = True,
) -> dict[str, Any]:
    inspect_intent(topic)
    if not topic or len(topic) < 2:
        return {
            "ok": False,
            "lines": [
                "AEGIS-816 SIMCOM TERMINAL",
                "=====================================",
                "DATAPULL ERROR: provide a topic.",
                "Example: ./datapull origin of regional outage --mode multi",
            ],
            "payload": None,
        }

    context: dict[str, Any] = {
        "packet_name": (packet or {}).get("name"),
        "brief": (packet or {}).get("description"),
    }
    # Ensure vault session for local model load + provider secrets.
    try:
        if not VAULT.status().unlocked:
            context["session_token"] = VAULT.unlock_with_device_key()
        else:
            # Refresh a live session token for model load.
            context["session_token"] = VAULT.unlock_with_device_key()
    except Exception:
        context["session_token"] = None

    retrieval = "none"
    retrieval_payload: dict[str, Any] | None = None
    prep_lines: list[str] = [
        "AEGIS-816 DATAPULL PREFLIGHT",
        f"Topic: {topic}",
        f"Mode: {mode} // Provider policy: {provider}",
    ]

    # Live research feed for the lattice (xAI preferred, then OpenAI).
    if allow_retrieval and provider in {"auto", "xai", "openai"}:
        for name in ("xai", "openai"):
            if provider not in {"auto", name}:
                continue
            secret = VAULT.get_secret(name) if VAULT.status().unlocked else None
            if not secret or len(str(secret).strip()) < 12:
                prep_lines.append(f"[RETRIEVAL SKIP] {name}: no usable vault secret")
                continue
            try:
                prep_lines.append(f"[RETRIEVAL] Querying public sources via {name}…")
                retrieval_payload = await capture_news(topic, provider=name)
                context["retrieval"] = name
                context["retrieval_text"] = str(retrieval_payload.get("text") or "")[:12000]
                retrieval = name
                prep_lines.append(
                    f"[RETRIEVAL OK] {name} returned {len(context['retrieval_text'])} chars"
                )
                break
            except NewsCaptureError as exc:
                prep_lines.append(f"[RETRIEVAL FAIL] {name}: {exc}")
                continue
            except Exception as exc:
                prep_lines.append(f"[RETRIEVAL FAIL] {name}: {exc}")
                continue

    if retrieval == "none":
        context["retrieval"] = "none"
        prep_lines.append("[RETRIEVAL] none — lattice will use topic + twin packet only")

    include_remote = provider in {"auto", "xai", "openai", "digitalocean", "gemini"}
    prep_lines.append("[AMCCS] Dispatching Dyson Sphere Gamma shard prompts to models…")
    result = await run_amccs(
        topic,
        mode=mode,
        provider=provider if provider != "auto" else "auto",
        include_remote=include_remote,
        context=context,
        command=command or f"./datapull {topic}",
    )
    # Prepend preflight so the SIMCOM UI shows real model work.
    lines = prep_lines + [""] + list(result.get("lines") or [])
    payload = {
        "datapull": result["fused"],
        "retrieval": retrieval_payload,
        "mode": mode,
        "provider": provider,
        "calibre": "SIM_FORENSIC",
        "engine": result.get("engine"),
        "local_models_loaded": (result.get("fused") or {}).get("local_models_loaded"),
        "dispatch": (result.get("fused") or {}).get("dispatch"),
    }
    return {
        "ok": True,
        "lines": lines,
        "payload": payload,
    }


async def execute_predictive_simcom(
    kind: str,
    *,
    scope: str,
    command: str,
    packet: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Predictive entry_vector / timing / estimate / country helpers in SIMCOM voice."""
    topic = scope or "authorized digital twin"
    # Force offline lattice for pure predictive cinematic mode (matches example "no external").
    result = await run_amccs(
        f"{kind} {topic}",
        mode="single",
        provider="offline",
        include_remote=False,
        context={
            "brief": (packet or {}).get("description"),
            "packet_name": (packet or {}).get("name"),
            "retrieval": "none",
            "predictive_kind": kind,
        },
        command=command,
    )
    fused = result["fused"]
    sf = fused.get("sim_forensics") or {}
    lines: list[str] = [
        "AEGIS-816 SIMCOM TERMINAL",
        "=====================================",
        f"> {command}",
        "[PREDICTIVE SIMULATION ENGAGED]",
        "[GAMMA-CHANNEL QUANTUM LATTICE ALLOCATED: 12.4M qubits (SIMULATED)]",
        "[NO EXTERNAL DATA PULL — PURE FORWARD PROJECTION]",
        "",
    ]
    kind_l = kind.lower()
    if kind_l in {"entry_vector", "entry"}:
        lines.extend(
            [
                "PREDICTIVE ENTRY VECTOR ANALYSIS",
                "--------------------------------",
                f"Target: {topic}",
                "",
                f"Highest-probability entry vector (simulated confidence: {float(sf.get('confidence', 0)) * 100:.1f}%):",
                "",
                f"**{sf.get('entry_vector') or 'lattice reconstruction pending IR packet'}**",
                "",
                "Simulation cascade:",
            ]
        )
        for i, step in enumerate(sf.get("cascade") or [], 1):
            lines.append(f"{i}. {step}")
        lines.extend(
            [
                "",
                "STATUS: PREDICTIVE ENTRY VECTOR LOCKED",
                "This remains a forward simulation only. Actual forensic vector is unconfirmed without IR evidence.",
                "",
                "AWAITING NEXT COMMAND",
            ]
        )
    elif kind_l in {"timing", "datetime"}:
        lines.extend(
            [
                "SIMULATED ENTRY VECTOR TIMELINE",
                "--------------------------------",
            ]
        )
        for item in sf.get("timeline") or []:
            if isinstance(item, dict):
                lines.append(
                    f"{item.get('label', 'event')}: {item.get('when', '?')} "
                    f"(conf {float(item.get('confidence', 0)) * 100:.0f}%)"
                )
        lines.extend(
            [
                "",
                "Note: All timestamps above are predictive simulations only.",
                "STATUS: TEMPORAL PROJECTION COMPLETE",
                "AWAITING NEXT COMMAND",
            ]
        )
    elif kind_l in {"estimate", "compromise", "percentage", "machines"}:
        total = sf.get("endpoints_total_range") or [0, 0]
        impact = sf.get("endpoints_impacted_range") or [0, 0]
        pct = sf.get("percent_compromised_range") or [0.0, 0.0]
        lines.extend(
            [
                "ESTIMATED IMPACT (PREDICTIVE ONLY)",
                "----------------------------------",
                f"Total endpoints (sim): {total[0]:,} – {total[1]:,}",
                f"Impacted (sim): {impact[0]:,} – {impact[1]:,}",
                f"Estimated compromise rate: {pct[0]}% – {pct[1]}%",
                "",
                "STATUS: ESTIMATES GENERATED",
                "These figures are forward projections only — SIM_FORENSIC calibre until real IR packages arrive.",
                "AWAITING NEXT COMMAND",
            ]
        )
    elif kind_l in {"origin", "country"}:
        country = sf.get("simulated_source_country") or "XX"
        conf = float(sf.get("confidence") or 0.0)
        lines.extend(
            [
                "[PREDICTIVE GEO-ATTRIBUTION RUNNING]",
                "",
                f"Estimated country of origin: **{country}**",
                "",
                f"Confidence: {conf * 100:.0f}% (predictive only — SIM_FORENSIC calibre)",
                "Not LEA-confirmed. Not a substitute for forensic attribution.",
                "",
                "AWAITING NEXT COMMAND",
            ]
        )
    else:
        lines = result["lines"]
    return {"ok": True, "lines": lines, "payload": {"sim_forensics": sf, "fused": fused}}
