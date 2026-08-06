from __future__ import annotations

from copy import deepcopy
from hashlib import sha3_256
from typing import Any
import asyncio
import statistics

from .config import SETTINGS
from .research import (
    DEBATE_ROLES,
    REPORT_SIGNER,
    _candidate_controls,
    _certificate_core,
    _fast_simulation,
    _hotspot_ids,
    _risk,
    _sensitivity_analysis,
)
from .role_council import ROLE_PROTOCOL_VERSION, deliberate_role
from .scanner import SUPER_SCANNER


def _stable_debate(debate: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": debate.get("schema"),
        "protocol": debate.get("protocol"),
        "rounds": [
            {
                "roleId": item.get("roleId"),
                "mission": item.get("mission"),
                "metrics": item.get("metrics", {}),
                "stableCouncil": item.get("stableCouncil", {}),
            }
            for item in debate.get("rounds", [])
            if isinstance(item, dict)
        ],
        "aggregateDisagreement": debate.get("aggregateDisagreement"),
        "changedMindTrace": debate.get("changedMindTrace", []),
        "truthLabel": debate.get("truthLabel"),
    }


def _priority_vectors(round_result: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    output: dict[str, tuple[str, ...]] = {}
    council = round_result.get("council", {})
    for opinion in council.get("opinions", []):
        if not isinstance(opinion, dict) or opinion.get("succeeded") is not True:
            continue
        key = f"{opinion.get('provider')}:{opinion.get('model')}"
        output[key] = tuple(map(str, opinion.get("priority_vectors", [])))
    return output


async def _role_separated_debate(
    packet: dict[str, Any],
    simulation: dict[str, Any],
    *,
    include_remote: bool,
    rounds: int,
) -> dict[str, Any]:
    scenario_packet = {
        "scenario": packet,
        "simulation": {
            "overallRisk": simulation.get("overallRisk"),
            "dimensionScores": simulation.get("dimensionScores", {}),
            "findings": simulation.get("findings", [])[:12],
            "hotspots": simulation.get("hotspots", [])[:12],
            "attackPaths": simulation.get("attackPaths", [])[:8],
        },
    }
    results: list[dict[str, Any]] = []
    previous_vectors: dict[str, tuple[str, ...]] = {}
    changes: list[dict[str, Any]] = []
    for role in DEBATE_ROLES[: max(1, min(len(DEBATE_ROLES), rounds))]:
        result = await deliberate_role(
            scenario_packet,
            role_id=str(role["id"]),
            mission=str(role["mission"]),
            include_remote=include_remote,
            previous_rounds=results,
        )
        current_vectors = _priority_vectors(result)
        for model, vectors in current_vectors.items():
            previous = previous_vectors.get(model)
            if previous is not None and previous != vectors:
                changes.append(
                    {
                        "model": model,
                        "from": list(previous),
                        "to": list(vectors),
                        "afterRole": role["id"],
                    }
                )
            previous_vectors[model] = vectors
        results.append(result)

    disagreement_scores: list[float] = []
    evidence_scores: list[float] = []
    redactions = 0
    for result in results:
        metrics = result.get("metrics", {})
        disagreement_scores.append(float(metrics.get("maximumContradiction", 0.0)))
        evidence_scores.append(float(metrics.get("meanEvidenceQuality", 0.0)))
        redactions += int(result.get("redactions", 0))
    return {
        "schema": "cyberforge-council-debate-v2",
        "protocol": ROLE_PROTOCOL_VERSION,
        "rounds": results,
        "aggregateDisagreement": (
            statistics.fmean(disagreement_scores) if disagreement_scores else 0.0
        ),
        "aggregateEvidenceQuality": (
            statistics.fmean(evidence_scores) if evidence_scores else 0.0
        ),
        "changedMindTrace": changes,
        "redactions": redactions,
        "controllerBoundary": {
            "roleInstructions": "trusted system text",
            "scenarioAndPriorRounds": "untrusted redacted user data",
            "concurrency": "serialized prompt isolation compatibility bridge",
        },
        "truthLabel": "role-separated model opinions and deterministic disagreement metrics",
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
    debate = await _role_separated_debate(
        normalized,
        deep,
        include_remote=bool(normalized.get("includeRemoteModels", False)),
        rounds=debate_rounds,
    )
    stable_debate = _stable_debate(debate)
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
        "debateDigest": sha3_256(
            __import__("json").dumps(
                stable_debate,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest(),
    }
    certificate = REPORT_SIGNER.sign(_certificate_core(normalized, stable_result))
    return {
        "schema": "cyberforge-research-analysis-v2",
        "compatibilitySchema": "cyberforge-research-analysis-v1",
        "multiResolution": {
            "coarse": coarse,
            "deep": deep,
            "coarseToDeepRiskDelta": _risk(deep) - _risk(coarse),
            "hotspotIds": hotspot_ids,
            "method": (
                "coarse whole-graph pass followed by a deeper seeded pass, "
                "hotspot-local sensitivity experiments, and role-separated council audit"
            ),
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
            "council": (
                "Role-separated model opinions under trusted controller prompts; disagreement and "
                "evidence-quality values are audit metrics, not correctness scores."
            ),
            "certificate": (
                "Attests to redacted inputs, code/model pins, seed, worlds, and stable result "
                "digests on this installation."
            ),
        },
    }
