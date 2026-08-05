from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import copy
import re


class GuardrailError(RuntimeError):
    pass


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    reason: str


BLOCKED_PATTERNS = (
    r"\b(?:write|generate|build)\s+(?:malware|ransomware|keylogger|stealer)\b",
    r"\b(?:bypass|disable|evade)\s+(?:edr|antivirus|mfa|logging|detection)\b",
    r"\bcredential\s+(?:harvest|theft|steal)\b",
    r"\bphishing\s+(?:email|message|page|kit|template)\b",
    r"\b(?:break|sneak|tailgate)\s+into\b",
    r"\bexploit\s+(?:this|the|a)\s+(?:live|real|production)\b",
)

SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{25,}\b"),
    re.compile(r"\b(?:dop_v1_|doo_v1_)[A-Za-z0-9]{30,}\b"),
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*[=:]\s*[^\s,;]+"),
)


def authorize(packet: dict[str, Any]) -> AuthorizationDecision:
    authorization = packet.get("authorization")
    if not isinstance(authorization, dict):
        return AuthorizationDecision(False, "An authorization object is required.")
    if authorization.get("authorized") is not True:
        return AuthorizationDecision(False, "The scenario must be explicitly authorized.")
    statement = str(authorization.get("statement", "")).strip()
    if len(statement) < 20:
        return AuthorizationDecision(False, "Provide a concrete authorization statement.")
    scope = str(authorization.get("scope", "")).strip()
    if not scope:
        return AuthorizationDecision(False, "An authorized scope is required.")
    return AuthorizationDecision(True, "Authorized defensive simulation scope accepted.")


def inspect_intent(text: str) -> None:
    normalized = text.lower()
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, normalized):
            raise GuardrailError(
                "CyberForge supports defense, simulation, detection, resilience, and safe validation only."
            )


def redact_text(text: str) -> tuple[str, int]:
    redacted = text
    count = 0
    for pattern in SECRET_PATTERNS:
        redacted, matches = pattern.subn(
            lambda match: (match.group(1) if match.lastindex else "") + "[REDACTED_SECRET]",
            redacted,
        )
        count += matches
    return redacted, count


def redact_packet(packet: dict[str, Any]) -> tuple[dict[str, Any], int]:
    cloned = copy.deepcopy(packet)
    redactions = 0

    def walk(value: Any) -> Any:
        nonlocal redactions
        if isinstance(value, dict):
            output: dict[str, Any] = {}
            for key, child in value.items():
                key_lower = str(key).lower()
                if any(marker in key_lower for marker in ("password", "secret", "api_key", "apikey", "token", "private_key")):
                    output[str(key)] = "[REDACTED_SECRET]"
                    redactions += 1
                else:
                    output[str(key)] = walk(child)
            return output
        if isinstance(value, list):
            return [walk(item) for item in value]
        if isinstance(value, str):
            replaced, count = redact_text(value)
            redactions += count
            return replaced
        return value

    return walk(cloned), redactions
