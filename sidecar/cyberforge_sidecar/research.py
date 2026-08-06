from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256, sha3_256
from pathlib import Path
from typing import Any
import asyncio
import base64
import json
import math
import os
import statistics

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from . import __version__
from .config import GEMMA4_E2B, LLAMA3_SMALL, SETTINGS
from .guardrails import redact_packet
from .providers import MODEL_COUNCIL
from .scanner import SUPER_SCANNER


class ResearchError(RuntimeError):
    pass


SENSITIVITY_FIELDS = (
    "controlStrength",
    "exposure",
    "telemetryConfidence",
    "humanPressure",
    "criticality",
)

DEBATE_ROLES = (
    {
        "id": "consensus",
        "mission": "Construct the strongest common defensive interpretation supported across the evidence and simulation outputs.",
    },
    {
        "id": "forced-dissent",
        "mission": "Challenge the leading interpretation, identify fragile assumptions, and surface plausible alternative control priorities.",
    },
    {
        "id": "auditor-scrub",
        "mission": "Audit truth labels, provenance, double counting, reproducibility, control ownership, validation evidence, and rollback conditions.",
    },
)

CONTROL_ACTIONS = (
    {
        "field": "controlStrength",
        "direction": 1.0,
        "amount": 0.15,
        "label": "Strengthen preventive and enforcement controls",
        "defaultCost": 2.0,
    },
    {
        "field": "exposure",
        "direction": -1.0,
        "amount": 0.15,
        "label": "Reduce reachable exposure and standing access",
        "defaultCost": 3.0,
    },
    {
        "field": "telemetryConfidence",
        "direction": 1.0,
        "amount": 0.15,
        "label": "Improve telemetry coverage and validation evidence",
        "defaultCost": 1.5,
    },
    {
        "field": "humanPressure",
        "direction": -1.0,
        "amount": 0.15,
        "label": "Reduce workflow and human-pressure concentration",
        "defaultCost": 2.5,
    },
)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _risk(report: dict[str, Any]) -> float:
    return float(report.get("overallRisk", 0.0))


def _fast_simulation(packet: dict[str, Any], *, worlds: int, seed: int) -> dict[str, Any]:
    validated = SUPER_SCANNER.validate(deepcopy(packet))
    validated["worlds"] = max(1000, min(SETTINGS.max_worlds, int(worlds)))
    validated["seed"] = int(seed)
    return SUPER_SCANNER._simulate(  # noqa: SLF001 - internal deterministic research path
        validated["surfaces"],
        validated.get("links", []),
        validated["worlds"],
        validated["seed"],
        {},
    )


def _hotspot_ids(report: dict[str, Any], limit: int) -> list[str]:
    findings = report.get("findings", [])
    ids: list[str] = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        value = str(finding.get("id", ""))
        if value and value not in ids:
            ids.append(value)
        if len(ids) >= limit:
            break
    return ids


def _find_surface(packet: dict[str, Any], surface_id: str) -> dict[str, Any] | None:
    for surface in packet.get("surfaces", []):
        if isinstance(surface, dict) and str(surface.get("id")) == surface_id:
            return surface
    return None


def _sensitivity_analysis(
    packet: dict[str, Any],
    baseline: dict[str, Any],
    hotspot_ids: list[str],
    *,
    worlds: int,
    seed: int,
    delta: float,
) -> list[dict[str, Any]]:
    baseline_risk = _risk(baseline)
    entries: list[dict[str, Any]] = []
    for surface_id in hotspot_ids:
        original_surface = _find_surface(packet, surface_id)
        if original_surface is None:
            continue
        for field in SENSITIVITY_FIELDS:
            original = float(original_surface.get(field, 0.5))
            low_packet = deepcopy(packet)
            high_packet = deepcopy(packet)
            low_surface = _find_surface(low_packet, surface_id)
            high_surface = _find_surface(high_packet, surface_id)
            if low_surface is None or high_surface is None:
                continue
            low_surface[field] = _clamp(original - delta)
            high_surface[field] = _clamp(original + delta)
            low_report = _fast_simulation(low_packet, worlds=worlds, seed=seed)
            high_report = _fast_simulation(high_packet, worlds=worlds, seed=seed)
            low_risk = _risk(low_report)
            high_risk = _risk(high_report)
            influence = abs(high_risk - low_risk) / max(2.0 * delta, 1e-9)
            entries.append(
                {
                    "surfaceId": surface_id,
                    "surfaceLabel": str(original_surface.get("label", surface_id)),
                    "parameter": field,
                    "baselineValue": original,
                    "lowValue": _clamp(original - delta),
                    "highValue": _clamp(original + delta),
                    "lowRisk": low_risk,
                    "baselineRisk": baseline_risk,
                    "highRisk": high_risk,
                    "signedDelta": high_risk - low_risk,
                    "influence": influence,
                    "truthLabel": "counterfactual simulation sensitivity",
                }
            )
    entries.sort(key=lambda item: float(item["influence"]), reverse=True)
    return entries


def _candidate_controls(
    packet: dict[str, Any],
    baseline: dict[str, Any],
    hotspot_ids: list[str],
    *,
    worlds: int,
    seed: int,
) -> list[dict[str, Any]]:
    baseline_risk = _risk(baseline)
    configured_costs = packet.get("controlCosts") if isinstance(packet.get("controlCosts"), dict) else {}
    candidates: list[dict[str, Any]] = []
    for surface_id in hotspot_ids:
        original_surface = _find_surface(packet, surface_id)
        if original_surface is None:
            continue
        for action in CONTROL_ACTIONS:
            field = str(action["field"])
            changed = deepcopy(packet)
            target = _find_surface(changed, surface_id)
            if target is None:
                continue
            before = float(target.get(field, 0.5))
            after = _clamp(before + float(action["direction"]) * float(action["amount"]))
            if math.isclose(before, after, abs_tol=1e-9):
                continue
            target[field] = after
            report = _fast_simulation(changed, worlds=worlds, seed=seed)
            residual = _risk(report)
            reduction = max(0.0, baseline_risk - residual)
            cost_key = f"{surface_id}:{field}"
            cost = float(configured_costs.get(cost_key, action["defaultCost"]))
            candidates.append(
                {
                    "id": cost_key,
                    "surfaceId": surface_id,
                    "surfaceLabel": str(original_surface.get("label", surface_id)),
                    "action": str(action["label"]),
                    "parameter": field,
                    "before": before,
                    "after": after,
                    "estimatedCost": max(0.1, cost),
                    "estimatedRiskReduction": reduction,
                    "residualRisk": residual,
                    "efficiency": reduction / max(0.1, cost),
                    "truthLabel": "counterfactual control estimate",
                }
            )

    candidates.sort(
        key=lambda item: (
            -float(item["estimatedRiskReduction"]),
            float(item["estimatedCost"]),
        )
    )
    frontier: list[dict[str, Any]] = []
    for candidate in candidates:
        dominated = any(
            float(other["estimatedCost"]) <= float(candidate["estimatedCost"])
            and float(other["estimatedRiskReduction"])
            >= float(candidate["estimatedRiskReduction"])
            and (
                float(other["estimatedCost"]) < float(candidate["estimatedCost"])
                or float(other["estimatedRiskReduction"]) > float(candidate["estimatedRiskReduction"])
            )
            for other in candidates
        )
        if not dominated:
            frontier.append(candidate)
    frontier.sort(key=lambda item: float(item["estimatedCost"]))
    return frontier[:24]


def _round_disagreement(council: dict[str, Any]) -> dict[str, Any]:
    opinions = [
        item
        for item in council.get("opinions", [])
        if isinstance(item, dict) and item.get("succeeded") is True
    ]
    if not opinions:
        return {
            "score": 1.0,
            "vectorDiversity": 1.0,
            "uncertaintySpread": 1.0,
            "opinionCount": 0,
        }
    vector_sets = [set(map(str, item.get("priority_vectors", []))) for item in opinions]
    universe = set().union(*vector_sets) if vector_sets else set()
    agreement = 0.0
    if universe:
        frequencies = Counter(vector for vectors in vector_sets for vector in vectors)
        agreement = sum(count / len(vector_sets) for count in frequencies.values()) / len(universe)
    uncertainties = [float(item.get("uncertainty", 1.0)) for item in opinions]
    uncertainty_spread = statistics.pstdev(uncertainties) if len(uncertainties) > 1 else 0.0
    vector_diversity = 1.0 - agreement
    score = _clamp(vector_diversity * 0.72 + min(1.0, uncertainty_spread * 2.0) * 0.28)
    return {
        "score": score,
        "vectorDiversity": vector_diversity,
        "uncertaintySpread": uncertainty_spread,
        "opinionCount": len(opinions),
    }


async def _debate(
    packet: dict[str, Any],
    simulation: dict[str, Any],
    *,
    include_remote: bool,
    rounds: int,
) -> dict[str, Any]:
    redacted_packet, redactions = redact_packet(packet)
    results: list[dict[str, Any]] = []
    previous_by_model: dict[str, tuple[str, ...]] = {}
    change_trace: list[dict[str, Any]] = []
    for role in DEBATE_ROLES[: max(1, min(len(DEBATE_ROLES), rounds))]:
        council_packet = {
            "scenario": redacted_packet,
            "simulation": {
                "overallRisk": simulation.get("overallRisk"),
                "dimensionScores": simulation.get("dimensionScores", {}),
                "findings": simulation.get("findings", [])[:12],
                "hotspots": simulation.get("hotspots", [])[:12],
                "attackPaths": simulation.get("attackPaths", [])[:8],
            },
            "councilProtocol": {
                "assignedRole": role["id"],
                "mission": role["mission"],
                "controllerMetadata": True,
                "defenseOnly": True,
            },
        }
        council = await MODEL_COUNCIL.deliberate(
            council_packet,
            include_remote=include_remote,
        )
        disagreement = _round_disagreement(council)
        for opinion in council.get("opinions", []):
            if not isinstance(opinion, dict) or opinion.get("succeeded") is not True:
                continue
            model_key = f"{opinion.get('provider')}:{opinion.get('model')}"
            vectors = tuple(map(str, opinion.get("priority_vectors", [])))
            previous = previous_by_model.get(model_key)
            if previous is not None and previous != vectors:
                change_trace.append(
                    {
                        "model": model_key,
                        "from": list(previous),
                        "to": list(vectors),
                        "afterRole": role["id"],
                    }
                )
            previous_by_model[model_key] = vectors
        results.append(
            {
                "role": role,
                "council": council,
                "disagreement": disagreement,
            }
        )
    scores = [float(item["disagreement"]["score"]) for item in results]
    return {
        "schema": "cyberforge-council-debate-v1",
        "rounds": results,
        "aggregateDisagreement": statistics.fmean(scores) if scores else 1.0,
        "changedMindTrace": change_trace,
        "redactions": redactions,
        "truthLabel": "model opinions and deterministic disagreement metrics",
    }


class ReportSigner:
    def __init__(self, key_path: Path | None = None) -> None:
        self.key_path = key_path or SETTINGS.data_dir / "signing" / "report-ed25519.pem"

    def _private_key(self) -> Ed25519PrivateKey:
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        if self.key_path.is_file():
            try:
                raw = self.key_path.read_bytes()
                key = serialization.load_pem_private_key(raw, password=None)
                if isinstance(key, Ed25519PrivateKey):
                    return key
            except Exception as exc:
                raise ResearchError(f"Unable to load report signing key: {exc}") from exc
        key = Ed25519PrivateKey.generate()
        raw = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        temporary = self.key_path.with_suffix(".tmp")
        temporary.write_bytes(raw)
        try:
            temporary.chmod(0o600)
        except OSError:
            pass
        os.replace(temporary, self.key_path)
        try:
            self.key_path.chmod(0o600)
        except OSError:
            pass
        return key

    def sign(self, core: dict[str, Any]) -> dict[str, Any]:
        key = self._private_key()
        public = key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        canonical = _canonical(core)
        signature = key.sign(canonical)
        return {
            "schema": "cyberforge-reproducibility-certificate-v1",
            "issuedAt": datetime.now(timezone.utc).isoformat(),
            "core": core,
            "runFingerprint": sha3_256(canonical).hexdigest(),
            "signing": {
                "algorithm": "Ed25519",
                "publicKey": base64.b64encode(public).decode("ascii"),
                "publicKeyFingerprint": sha256(public).hexdigest(),
                "signature": base64.b64encode(signature).decode("ascii"),
                "keyStorage": "local sidecar data directory; file mode 0600 when supported",
            },
        }

    @staticmethod
    def verify(certificate: dict[str, Any]) -> bool:
        try:
            core = certificate["core"]
            signing = certificate["signing"]
            public = base64.b64decode(signing["publicKey"])
            signature = base64.b64decode(signing["signature"])
            fingerprint = sha3_256(_canonical(core)).hexdigest()
            if fingerprint != certificate.get("runFingerprint"):
                return False
            Ed25519PublicKey.from_public_bytes(public).verify(signature, _canonical(core))
            return True
        except Exception:
            return False


REPORT_SIGNER = ReportSigner()


def _certificate_core(packet: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    redacted, redactions = redact_packet(packet)
    packet_digest = sha3_256(_canonical(redacted)).hexdigest()
    result_digest = sha3_256(_canonical(result)).hexdigest()
    graph_digest = sha3_256(
        _canonical({"surfaces": redacted.get("surfaces", []), "links": redacted.get("links", [])})
    ).hexdigest()
    return {
        "packetDigest": packet_digest,
        "graphDigest": graph_digest,
        "resultDigest": result_digest,
        "seed": int(packet.get("seed", 3923929)),
        "worlds": int(packet.get("worlds", SETTINGS.default_worlds)),
        "codeVersion": __version__,
        "engine": "AEGIS-816 multi-resolution conventional simulation",
        "modelPins": {
            LLAMA3_SMALL.id: LLAMA3_SMALL.sha256,
            GEMMA4_E2B.id: GEMMA4_E2B.sha256,
        },
        "remoteModelsIncluded": bool(packet.get("includeRemoteModels", False)),
        "redactions": redactions,
        "truthLabel": "reproducibility metadata and cryptographic attestation",
    }


async def analyze_research(packet: dict[str, Any]) -> dict[str, Any]:
    normalized = SUPER_SCANNER.validate(deepcopy(packet))
    seed = int(normalized["seed"])
    requested_worlds = int(normalized["worlds"])
    options = normalized.get("research") if isinstance(normalized.get("research"), dict) else {}
    coarse_worlds = max(1000, min(4000, int(options.get("coarseWorlds", 1500))))
    sensitivity_worlds = max(1000, min(4000, int(options.get("sensitivityWorlds", 1200))))
    hotspot_limit = max(1, min(6, int(options.get("hotspotLimit", 3))))
    debate_rounds = max(1, min(3, int(options.get("debateRounds", 3))))
    delta = max(0.02, min(0.2, float(options.get("sensitivityDelta", 0.08))))

    coarse = await asyncio.to_thread(
        _fast_simulation,
        normalized,
        worlds=coarse_worlds,
        seed=seed,
    )
    hotspot_ids = _hotspot_ids(coarse, hotspot_limit)
    deep = await asyncio.to_thread(
        _fast_simulation,
        normalized,
        worlds=requested_worlds,
        seed=seed,
    )
    sensitivity = await asyncio.to_thread(
        _sensitivity_analysis,
        normalized,
        deep,
        hotspot_ids,
        worlds=sensitivity_worlds,
        seed=seed,
        delta=delta,
    )
    frontier = await asyncio.to_thread(
        _candidate_controls,
        normalized,
        deep,
        hotspot_ids,
        worlds=sensitivity_worlds,
        seed=seed,
    )
    debate = await _debate(
        normalized,
        deep,
        include_remote=bool(normalized.get("includeRemoteModels", False)),
        rounds=debate_rounds,
    )
    stable_result = {
        "coarse": {
            "worlds": coarse_worlds,
            "overallRisk": coarse.get("overallRisk"),
            "dimensionScores": coarse.get("dimensionScores", {}),
            "hotspotIds": hotspot_ids,
        },
        "deep": {
            "worlds": requested_worlds,
            "overallRisk": deep.get("overallRisk"),
            "dimensionScores": deep.get("dimensionScores", {}),
            "impactEstimate": deep.get("impactEstimate", {}),
        },
        "sensitivity": sensitivity,
        "paretoControlFrontier": frontier,
        "debateDigest": sha3_256(_canonical(debate)).hexdigest(),
    }
    certificate = REPORT_SIGNER.sign(_certificate_core(normalized, stable_result))
    return {
        "schema": "cyberforge-research-analysis-v1",
        "multiResolution": {
            "coarse": coarse,
            "deep": deep,
            "coarseToDeepRiskDelta": _risk(deep) - _risk(coarse),
            "hotspotIds": hotspot_ids,
            "method": "coarse whole-graph pass followed by a deeper seeded pass and hotspot-local sensitivity experiments",
            "truthLabel": "seeded counterfactual simulation outputs",
        },
        "sensitivity": sensitivity,
        "paretoControlFrontier": frontier,
        "councilDebate": debate,
        "certificate": certificate,
        "interpretation": {
            "pressure": "Relative planning pressure, not measured breach probability.",
            "sensitivity": "Influence under bounded parameter perturbation; it does not prove causality.",
            "pareto": "Non-dominated modeled options by estimated effort and simulated pressure reduction.",
            "certificate": "Attests to redacted inputs, code/model pins, seed, worlds, and stable result digests on this installation.",
        },
    }
