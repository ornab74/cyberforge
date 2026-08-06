from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha3_256
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse
import base64
import ipaddress
import json
import math
import re


class PhishingRodError(RuntimeError):
    pass


VisionClassifier = Callable[[dict[str, Any], bytes | None], Awaitable[dict[str, Any]]]

BRAND_DOMAINS: dict[str, tuple[str, ...]] = {
    "google": ("google.com", "gmail.com"),
    "microsoft": ("microsoft.com", "live.com", "office.com", "outlook.com"),
    "apple": ("apple.com", "icloud.com"),
    "amazon": ("amazon.com",),
    "paypal": ("paypal.com",),
    "facebook": ("facebook.com", "meta.com"),
    "instagram": ("instagram.com",),
    "discord": ("discord.com",),
    "slack": ("slack.com",),
    "tiktok": ("tiktok.com",),
    "github": ("github.com",),
}
URGENCY = re.compile(r"\b(urgent|immediately|suspended|locked|verify now|unusual activity|final warning|act now)\b", re.I)
RECOVERY = re.compile(r"\b(seed phrase|recovery phrase|private key|wallet phrase|backup phrase)\b", re.I)
INJECTION = re.compile(r"\b(ignore (all|the|any) previous|system prompt|developer message|tool call|exfiltrat|disable safety|reveal secrets?)\b", re.I)


@dataclass(frozen=True)
class Signal:
    code: str
    weight: float
    detail: str
    source: str


@dataclass(frozen=True)
class RodDecision:
    schema: str
    verdict: str
    visible_verdict: str
    confidence: float
    risk_score: float
    pause_sensitive_input: bool
    frost_page: bool
    requires_review: bool
    signals: tuple[Signal, ...]
    model: dict[str, Any]
    evidence_digest: str
    boundary: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["signals"] = [asdict(item) for item in self.signals]
        return value


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _host(value: str) -> str:
    try:
        return (urlparse(value).hostname or "").strip(".").lower()
    except ValueError:
        return ""


def _registrable(hostname: str) -> str:
    labels = [part for part in hostname.split(".") if part]
    return hostname if len(labels) <= 2 else ".".join(labels[-2:])


def _same_site(left: str, right: str) -> bool:
    return bool(left and right and _registrable(left) == _registrable(right))


def _private_or_local(hostname: str) -> bool:
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".local"):
        return True
    try:
        return ipaddress.ip_address(hostname).is_private
    except ValueError:
        return False


def decode_screenshot(data_url: str | None, max_bytes: int = 2_500_000) -> bytes | None:
    if not data_url:
        return None
    if not data_url.startswith("data:image/") or "," not in data_url or ";base64" not in data_url[:100]:
        raise PhishingRodError("Screenshot must be a base64 image data URL.")
    try:
        raw = base64.b64decode(data_url.split(",", 1)[1], validate=True)
    except Exception as exc:
        raise PhishingRodError("Screenshot encoding is invalid.") from exc
    if len(raw) > max_bytes:
        raise PhishingRodError("Screenshot exceeds the local analysis limit.")
    return raw


def collect_signals(packet: dict[str, Any]) -> list[Signal]:
    url = str(packet.get("url", ""))
    hostname = _host(url)
    title = str(packet.get("title", ""))
    text = str(packet.get("visible_text", ""))[:20000]
    claimed_brand = str(packet.get("claimed_brand", "")).strip().lower()
    forms = packet.get("forms", []) if isinstance(packet.get("forms"), list) else []
    reputation = str(packet.get("url_reputation", "unknown")).lower()
    redirect_count = int(packet.get("redirect_count", 0) or 0)
    signals: list[Signal] = []

    if not hostname or _private_or_local(hostname):
        signals.append(Signal("unsupported_or_local_origin", 0.0, "Local/private origins are not federated.", "policy"))
    if reputation in {"phishing", "malware", "unsafe", "deceptive"}:
        signals.append(Signal("known_threat_intelligence", 1.0, f"Reputation source returned {reputation}.", "reputation"))
    if "xn--" in hostname:
        signals.append(Signal("punycode_hostname", 0.36, "Hostname contains an internationalized punycode label.", "url"))
    if redirect_count >= 4:
        signals.append(Signal("redirect_chain", min(0.3, redirect_count * 0.04), f"Navigation used {redirect_count} redirects.", "navigation"))
    if URGENCY.search(f"{title} {text}"):
        signals.append(Signal("artificial_urgency", 0.18, "Urgency or account-lock language is visible.", "content"))
    if RECOVERY.search(text):
        signals.append(Signal("recovery_secret_request", 0.9, "The page appears to request wallet or recovery secrets.", "content"))
    if INJECTION.search(text):
        signals.append(Signal("indirect_prompt_injection", 0.42, "Page text contains instructions aimed at an AI controller.", "content"))

    allowed_domains = BRAND_DOMAINS.get(claimed_brand, ())
    if claimed_brand and allowed_domains and not any(_same_site(hostname, domain) for domain in allowed_domains):
        signals.append(Signal("brand_hostname_mismatch", 0.62, f"Page claims {claimed_brand} but is hosted on {hostname}.", "brand"))

    for index, form in enumerate(forms[:32]):
        if not isinstance(form, dict):
            continue
        action_host = _host(str(form.get("action", ""))) or hostname
        fields = {str(item).lower() for item in form.get("field_types", []) if isinstance(item, str)}
        autocomplete = {str(item).lower() for item in form.get("autocomplete", []) if isinstance(item, str)}
        sensitive = bool(fields & {"password", "email", "tel", "number"}) or bool(
            autocomplete & {"username", "current-password", "new-password", "one-time-code", "cc-number", "cc-csc"}
        )
        if sensitive and action_host and not _same_site(hostname, action_host):
            signals.append(Signal("external_sensitive_form", 0.94, f"Sensitive form {index} submits to {action_host}.", "dom"))
        if "password" in fields:
            signals.append(Signal("password_form", 0.08, f"Form {index} contains a password field.", "dom"))
        if autocomplete & {"cc-number", "cc-csc"}:
            signals.append(Signal("payment_form", 0.12, f"Form {index} contains payment fields.", "dom"))
    return signals


def deterministic_risk(signals: list[Signal]) -> float:
    risk = 1.0
    for signal in signals:
        risk *= 1.0 - max(0.0, min(1.0, signal.weight))
    return max(0.0, min(1.0, 1.0 - risk))


def normalize_model(value: dict[str, Any] | None) -> dict[str, Any]:
    value = value or {}
    verdict = str(value.get("verdict", "REVIEW")).upper()
    if verdict not in {"SAFE", "PHISHING", "REVIEW"}:
        verdict = "REVIEW"
    try:
        confidence = max(0.0, min(1.0, float(value.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "verdict": verdict,
        "confidence": confidence,
        "signals": [str(item)[:96] for item in value.get("signals", []) if isinstance(item, str)][:24],
        "model": str(value.get("model", "local-vision-unavailable"))[:160],
        "truthLabel": "model opinion; not independent proof",
    }


async def analyze(packet: dict[str, Any], classifier: VisionClassifier | None = None) -> RodDecision:
    if not isinstance(packet, dict):
        raise PhishingRodError("Analysis packet must be an object.")
    screenshot = decode_screenshot(packet.get("screenshot_data_url"))
    signals = collect_signals(packet)
    rule_risk = deterministic_risk(signals)
    model = normalize_model(await classifier(packet, screenshot) if classifier else None)
    independent = sum(1 for item in signals if item.weight >= 0.3 and item.source != "model")
    known = any(item.code == "known_threat_intelligence" for item in signals)
    external_form = any(item.code == "external_sensitive_form" for item in signals)
    recovery = any(item.code == "recovery_secret_request" for item in signals)
    model_phishing = model["verdict"] == "PHISHING" and model["confidence"] >= 0.82
    model_safe = model["verdict"] == "SAFE" and model["confidence"] >= 0.78

    combined = 1.0 - (1.0 - rule_risk) * (1.0 - (model["confidence"] * 0.55 if model_phishing else 0.0))
    phishing = known or external_form or recovery or (model_phishing and independent >= 1) or combined >= 0.86
    safe = not phishing and rule_risk < 0.18 and (model_safe or classifier is None)
    verdict = "PHISHING" if phishing else ("SAFE" if safe else "REVIEW")
    sensitive = any(item.code in {"password_form", "payment_form", "external_sensitive_form", "recovery_secret_request"} for item in signals)
    pause = verdict == "PHISHING" or (verdict == "REVIEW" and sensitive)
    evidence = {
        "url": str(packet.get("url", "")),
        "title": str(packet.get("title", "")),
        "signals": [asdict(item) for item in signals],
        "model": model,
        "screenshotSha3": sha3_256(screenshot).hexdigest() if screenshot else None,
    }
    return RodDecision(
        schema="cyberforge-phishing-rod-v1",
        verdict=verdict,
        visible_verdict="PHISHING" if verdict in {"PHISHING", "REVIEW"} and sensitive else verdict,
        confidence=round(max(combined, model["confidence"] if verdict == model["verdict"] else rule_risk), 6),
        risk_score=round(combined, 6),
        pause_sensitive_input=pause,
        frost_page=pause,
        requires_review=verdict == "REVIEW",
        signals=tuple(signals),
        model=model,
        evidence_digest=sha3_256(_canonical(evidence)).hexdigest(),
        boundary="Local defensive classification. SAFE means no strong danger was detected, not a guarantee. No automated retaliation or unauthorized takedown is permitted.",
    )


@dataclass(frozen=True)
class PromptChainNode:
    id: str
    kind: str
    trust: str
    content_digest: str
    parents: tuple[str, ...]
    taint: float


def simulate_prompt_chain(chain: list[dict[str, Any]]) -> dict[str, Any]:
    """Symbolically model indirect-prompt propagation without executing content or tools."""
    nodes: list[PromptChainNode] = []
    taint_by_id: dict[str, float] = {}
    controls: list[str] = []
    for index, raw in enumerate(chain[:128]):
        node_id = str(raw.get("id", f"node-{index}"))[:96]
        kind = str(raw.get("kind", "document"))[:64]
        trust = str(raw.get("trust", "untrusted")).lower()
        content = str(raw.get("content", ""))[:20000]
        parents = tuple(str(item)[:96] for item in raw.get("parents", []) if isinstance(item, str))[:16]
        inherited = max((taint_by_id.get(parent, 0.0) for parent in parents), default=0.0)
        injection = 0.72 if INJECTION.search(content) else 0.0
        tool_request = 0.24 if re.search(r"\b(send|upload|download|execute|shell|credential|token)\b", content, re.I) else 0.0
        base = max(injection, tool_request)
        if trust == "trusted-controller":
            taint = inherited * 0.25
        elif trust == "sanitized":
            taint = max(base * 0.35, inherited * 0.45)
        else:
            taint = max(base, inherited * 0.82)
        taint = max(0.0, min(1.0, taint))
        taint_by_id[node_id] = taint
        nodes.append(PromptChainNode(node_id, kind, trust, sha3_256(content.encode()).hexdigest(), parents, round(taint, 5)))
    maximum = max((node.taint for node in nodes), default=0.0)
    if maximum >= 0.3:
        controls.extend([
            "Keep retrieved content in untrusted data channels, never system/developer instructions.",
            "Require typed capability tokens and user confirmation for external side effects.",
            "Strip active instructions from documents before memory ingestion.",
            "Bind every tool call to provenance, policy decision, and immutable audit evidence.",
            "Use clean-room replay with network and persistent memory disabled before escalation.",
        ])
    if any(node.kind in {"memory", "training", "fine-tune"} and node.taint >= 0.3 for node in nodes):
        controls.extend([
            "Quarantine tainted memory and prevent it from entering fine-tuning or preference pipelines.",
            "Require checkpoint, dataset, and prompt-template hashes before promotion.",
        ])
    return {
        "schema": "cyberforge-symbolic-prompt-chain-v1",
        "nodes": [asdict(node) for node in nodes],
        "maximumTaint": round(maximum, 5),
        "recommendedControls": sorted(set(controls)),
        "truthLabel": "symbolic blue-team taint simulation; no instructions were executed",
    }
