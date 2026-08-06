from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Iterable
import asyncio
import hashlib
import json
import math
import os
import random
import statistics
import time

try:
    import numpy as np
except Exception:  # pragma: no cover - scalar fallback remains available
    np = None

from .config import GEMMA4_E2B, LLAMA3_SMALL, SETTINGS
from .guardrails import GuardrailError, authorize, inspect_intent, redact_packet
from .models import MODEL_MANAGER
from .providers import MODEL_COUNCIL

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

KIND_DIMENSIONS: dict[str, tuple[str, ...]] = {
    "identity": ("credential", "phishing"),
    "credential": ("credential",),
    "endpoint": ("endpoint", "credential", "data"),
    "server": ("endpoint", "availability", "data"),
    "api": ("api", "credential", "data"),
    "cloud": ("cloud", "credential", "data"),
    "facility": ("physical", "availability"),
    "route": ("physical", "availability"),
    "vendor": ("vendor", "credential", "availability"),
    "collective": DIMENSIONS,
    "human": ("phishing", "credential", "physical"),
    "data": ("data", "credential"),
    "network": ("endpoint", "availability", "data"),
}


class ScannerError(RuntimeError):
    pass


@dataclass(frozen=True)
class SurfaceFinding:
    id: str
    label: str
    kind: str
    location: str
    risk: float
    probability: float
    impact: float
    confidence: float
    priority_dimensions: tuple[str, ...]
    likely_window: str
    observations: tuple[str, ...]
    controls: tuple[str, ...]
    assumptions: tuple[str, ...]
    evidence_needed: tuple[str, ...]
    local_model_adjustment: float


@dataclass(frozen=True)
class ScanTelemetry:
    engine: str
    simulated_qubits: int
    coherence: float
    worlds: int
    seed: int
    duration_ms: int
    local_llama_passes: int
    local_gemma_loaded: bool
    redactions: int


class GammaSimstation:
    name = "AEGIS-816 / Dyson Sphere Gamma Simstation"
    simulated_qubits = 81_611_511
    observation_frames = 4096
    logical_cells = 2_400_000_000_000_000_000

    def boot_report(self) -> list[str]:
        return [
            "SIMCOM ACTIVE // DEFENSIVE DIGITAL TWIN // LOCAL-FIRST",
            "[00:00:00.000] Safety kernel: defense-only policy locked",
            "[00:00:00.041] Gamma coherence fabric: simulated",
            f"[00:00:00.112] Logical register: {self.simulated_qubits:,} simulated qubits",
            "[00:00:00.189] Monte Carlo scheduler: ready",
            "[00:00:00.267] Surface graph: identity / endpoint / API / cloud / physical / vendor",
            "[00:00:00.341] Local Llama micro-scanner: standby",
            "[00:00:00.418] Local Gemma private synthesizer: standby",
            "[00:00:00.502] AES-256-GCM vault boundary: armed",
            "[00:00:00.589] ML-KEM recovery boundary: capability check complete",
            "[00:00:00.712] Live exploitation and attribution shortcuts: disabled",
            "[00:00:00.799] BOOT COMPLETE",
        ]


SIMSTATION = GammaSimstation()


def default_packet() -> dict[str, Any]:
    return {
        "name": "Synthetic Multisite Operations Twin",
        "description": "Authorized defensive simulation across identity, endpoint, API, cloud, vendor, and physical surfaces.",
        "authorization": {
            "authorized": True,
            "statement": "I own or am explicitly authorized to simulate every synthetic surface in this scenario.",
            "scope": "Synthetic multisite operations digital twin",
            "synthetic": True,
        },
        "location": {"name": "Named region only", "latitude": None, "longitude": None},
        "worlds": 12000,
        "seed": 3923929,
        "endpointCount": 4800,
        "includeRemoteModels": False,
        "surfaces": [
            {
                "id": "identity-workforce",
                "label": "Workforce identity plane",
                "kind": "identity",
                "location": "All sites",
                "criticality": 0.94,
                "exposure": 0.62,
                "controlStrength": 0.64,
                "humanPressure": 0.73,
                "telemetryConfidence": 0.82,
                "inventoryCount": 1600,
                "signals": ["mixed MFA coverage", "high external contact", "password reset volume"],
            },
            {
                "id": "remote-access",
                "label": "Remote access gateway",
                "kind": "api",
                "location": "Primary edge",
                "criticality": 0.96,
                "exposure": 0.78,
                "controlStrength": 0.70,
                "humanPressure": 0.48,
                "telemetryConfidence": 0.88,
                "inventoryCount": 12,
                "signals": ["internet-facing", "vendor support sessions", "conditional access gaps"],
            },
            {
                "id": "endpoint-fleet",
                "label": "Managed endpoint fleet",
                "kind": "endpoint",
                "location": "Distributed sites",
                "criticality": 0.86,
                "exposure": 0.56,
                "controlStrength": 0.72,
                "humanPressure": 0.59,
                "telemetryConfidence": 0.75,
                "inventoryCount": 4800,
                "signals": ["coverage drift", "legacy applications", "shared workstations"],
            },
            {
                "id": "cloud-control",
                "label": "Cloud control plane",
                "kind": "cloud",
                "location": "Cloud region",
                "criticality": 0.98,
                "exposure": 0.51,
                "controlStrength": 0.77,
                "humanPressure": 0.42,
                "telemetryConfidence": 0.86,
                "inventoryCount": 240,
                "signals": ["service principals", "privileged automation", "cross-account trust"],
            },
            {
                "id": "visitor-access",
                "label": "Visitor and delivery access",
                "kind": "facility",
                "location": "Public entrances",
                "criticality": 0.70,
                "exposure": 0.68,
                "controlStrength": 0.58,
                "humanPressure": 0.81,
                "telemetryConfidence": 0.69,
                "inventoryCount": 18,
                "signals": ["shift changes", "temporary badges", "delivery congestion"],
            },
            {
                "id": "vendor-mesh",
                "label": "Third-party support mesh",
                "kind": "vendor",
                "location": "External",
                "criticality": 0.88,
                "exposure": 0.67,
                "controlStrength": 0.55,
                "humanPressure": 0.52,
                "telemetryConfidence": 0.61,
                "inventoryCount": 74,
                "signals": ["standing access", "shared support channels", "uneven assurance"],
            },
        ],
        "links": [
            {"source": "identity-workforce", "target": "remote-access", "trust": 0.82, "controlStrength": 0.66, "type": "authenticates"},
            {"source": "remote-access", "target": "endpoint-fleet", "trust": 0.74, "controlStrength": 0.63, "type": "administers"},
            {"source": "vendor-mesh", "target": "remote-access", "trust": 0.77, "controlStrength": 0.48, "type": "supports"},
            {"source": "cloud-control", "target": "identity-workforce", "trust": 0.69, "controlStrength": 0.75, "type": "federates"},
            {"source": "visitor-access", "target": "endpoint-fleet", "trust": 0.34, "controlStrength": 0.57, "type": "co-locates"},
            {"source": "endpoint-fleet", "target": "cloud-control", "trust": 0.52, "controlStrength": 0.70, "type": "operates"}
        ],
    }


class SuperScanner:
    def validate(self, packet: dict[str, Any]) -> dict[str, Any]:
        decision = authorize(packet)
        if not decision.allowed and SETTINGS.require_authorization:
            raise ScannerError(decision.reason)
        inspect_intent(json.dumps(packet, sort_keys=True))
        surfaces = packet.get("surfaces")
        if not isinstance(surfaces, list) or not surfaces:
            raise ScannerError("At least one surface is required.")
        if len(surfaces) > SETTINGS.max_surfaces:
            raise ScannerError(f"Surface count exceeds {SETTINGS.max_surfaces}.")
        worlds = int(packet.get("worlds", SETTINGS.default_worlds))
        packet["worlds"] = max(1000, min(SETTINGS.max_worlds, worlds))
        packet["seed"] = int(packet.get("seed", 3923929))
        for index, surface in enumerate(surfaces):
            if not isinstance(surface, dict):
                raise ScannerError(f"Surface {index} is not an object.")
            surface.setdefault("id", f"surface-{index + 1}")
            surface.setdefault("label", surface["id"])
            surface.setdefault("kind", "collective")
            surface.setdefault("location", packet.get("location", {}).get("name", "Unspecified"))
            for field, default in (
                ("criticality", 0.5),
                ("exposure", 0.5),
                ("controlStrength", 0.5),
                ("humanPressure", 0.5),
                ("telemetryConfidence", 0.5),
            ):
                surface[field] = self._clamp(float(surface.get(field, default)))
            surface["inventoryCount"] = max(1, int(surface.get("inventoryCount", 1)))
            surface["signals"] = [str(value)[:256] for value in surface.get("signals", [])][:64]
        surface_ids = {str(surface["id"]) for surface in surfaces}
        links = packet.get("links", [])
        if not isinstance(links, list):
            raise ScannerError("Scenario links must be a list.")
        normalized_links: list[dict[str, Any]] = []
        for index, link in enumerate(links[: SETTINGS.max_surfaces * 8]):
            if not isinstance(link, dict):
                raise ScannerError(f"Link {index} is not an object.")
            source = str(link.get("source", ""))
            target = str(link.get("target", ""))
            if source not in surface_ids or target not in surface_ids or source == target:
                continue
            normalized_links.append({
                "source": source,
                "target": target,
                "type": str(link.get("type", "depends-on"))[:64],
                "trust": self._clamp(float(link.get("trust", 0.5))),
                "controlStrength": self._clamp(float(link.get("controlStrength", 0.5))),
            })
        packet["links"] = normalized_links
        return packet

    async def scan(self, packet: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        packet = self.validate(dict(packet))
        redacted_packet, redactions = redact_packet(packet)
        worlds = int(packet["worlds"])
        seed = int(packet["seed"])
        surfaces: list[dict[str, Any]] = packet["surfaces"]
        local_micro = await self._local_llama_micro_passes(surfaces)
        result = await asyncio.to_thread(
            self._simulate, surfaces, packet.get("links", []), worlds, seed, local_micro
        )
        result["name"] = str(packet.get("name", "CyberForge scan"))
        result["description"] = str(packet.get("description", ""))
        result["authorization"] = {
            "scope": packet["authorization"].get("scope"),
            "synthetic": bool(packet["authorization"].get("synthetic", False)),
            "accepted": True,
        }
        result["location"] = packet.get("location", {})
        result["generatedAt"] = datetime.now(timezone.utc).isoformat()
        result["bootcom"] = SIMSTATION.boot_report()
        result["telemetry"]["redactions"] = redactions
        result["telemetry"]["durationMs"] = int((time.perf_counter() - started) * 1000)
        result["packetDigest"] = hashlib.sha3_256(
            json.dumps(redacted_packet, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        include_remote = bool(packet.get("includeRemoteModels", False))
        council_packet = self._council_packet(redacted_packet, result)
        result["council"] = await MODEL_COUNCIL.deliberate(
            council_packet,
            include_remote=include_remote,
        )
        result["forensicBoundary"] = {
            "entryVector": "simulation hypotheses only",
            "actor": "not attributed",
            "country": "not attributed",
            "timestamps": "probabilistic planning windows, not forensic facts",
        }
        return result

    def _simulate(
        self,
        surfaces: list[dict[str, Any]],
        links: list[dict[str, Any]],
        worlds: int,
        seed: int,
        local_micro: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        rng = random.Random(seed)
        coherence = 0.985 + rng.random() * 0.014
        dimension_hits: dict[str, float] = defaultdict(float)
        location_hits: dict[str, float] = defaultdict(float)
        hourly_hits = [0.0] * 24
        findings: list[SurfaceFinding] = []
        total_inventory = sum(int(surface.get("inventoryCount", 1)) for surface in surfaces)
        compromised_samples: list[int] = []

        if np is not None:
            np_rng = np.random.default_rng(seed)
            common_pressure = np_rng.beta(2.3, 5.4, size=worlds)
        else:
            common_pressure = [rng.betavariate(2.3, 5.4) for _ in range(worlds)]

        surface_probabilities: list[tuple[dict[str, Any], float, float, float]] = []
        for surface in surfaces:
            micro = local_micro.get(str(surface["id"]), {})
            micro_bias = float(micro.get("risk", 0.5)) - 0.5
            exposure = float(surface["exposure"])
            control = float(surface["controlStrength"])
            criticality = float(surface["criticality"])
            human = float(surface["humanPressure"])
            telemetry = float(surface["telemetryConfidence"])
            signal_pressure = min(1.0, len(surface.get("signals", [])) / 12.0)
            logit = (
                -2.20
                + exposure * 2.05
                + criticality * 0.95
                + human * 0.72
                + signal_pressure * 0.40
                - control * 1.75
                + (1.0 - telemetry) * 0.48
                + micro_bias * 0.55
            )
            base_probability = 1.0 / (1.0 + math.exp(-logit))
            impact = self._clamp(criticality * 0.78 + exposure * 0.15 + human * 0.07)
            confidence = self._clamp(0.45 + telemetry * 0.40 + min(0.15, math.log10(worlds) / 40))
            surface_probabilities.append((surface, base_probability, impact, confidence))

        surface_probabilities, attack_paths = self._propagate_graph(
            surface_probabilities, links
        )

        if np is not None:
            compromise_matrix: list[Any] = []
            for index, (surface, probability, _impact, _confidence) in enumerate(surface_probabilities):
                temporal = self._temporal_vector(surface["kind"])
                sampled_hour = np_rng.integers(0, 24, size=worlds)
                temporal_factor = np.take(np.asarray(temporal), sampled_hour)
                correlated = np.clip(
                    probability * (0.82 + common_pressure * 0.48) * temporal_factor,
                    0.0001,
                    0.999,
                )
                compromised = np_rng.random(worlds) < correlated
                compromise_matrix.append(compromised)
                for hour in range(24):
                    mask = sampled_hour == hour
                    if mask.any():
                        hourly_hits[hour] += float(compromised[mask].mean())
            inventory = np.asarray([int(item[0].get("inventoryCount", 1)) for item in surface_probabilities])
            stacked = np.stack(compromise_matrix, axis=1)
            compromised_counts = (stacked * inventory).sum(axis=1)
            compromised_samples = [int(value) for value in compromised_counts.tolist()]
        else:
            compromised_samples = [0 for _ in range(worlds)]
            for world in range(worlds):
                pressure = common_pressure[world]
                hour = world % 24
                for surface, probability, _impact, _confidence in surface_probabilities:
                    temporal_factor = self._temporal_vector(surface["kind"])[hour]
                    actual = self._clamp(probability * (0.82 + pressure * 0.48) * temporal_factor)
                    if rng.random() < actual:
                        compromised_samples[world] += int(surface.get("inventoryCount", 1))
                        hourly_hits[hour] += 1.0 / max(1, len(surfaces))

        for surface, probability, impact, confidence in surface_probabilities:
            dimensions = KIND_DIMENSIONS.get(str(surface["kind"]), DIMENSIONS)
            risk = self._clamp(probability * impact)
            for dimension in dimensions:
                dimension_hits[dimension] += risk / len(dimensions)
            location_hits[str(surface["location"])] += risk
            micro = local_micro.get(str(surface["id"]), {})
            supplied_observations = tuple(surface.get("signals", []))
            local_observations = tuple(str(value) for value in micro.get("observations", []))
            observations = supplied_observations + local_observations
            if not observations:
                observations = (
                    "No explicit signal notes supplied; estimate relies on normalized surface fields.",
                )
            local_controls = tuple(str(value) for value in micro.get("controls", []))
            standard_controls = self._controls_for(dimensions)
            merged_controls = tuple(dict.fromkeys(local_controls + standard_controls))[:8]
            evidence_needed = tuple(str(value) for value in micro.get("evidence_needed", [])) or (
                "Passive telemetry and control evidence for this surface",
                "A recent owner-authorized recovery or containment exercise result",
            )
            findings.append(
                SurfaceFinding(
                    id=str(surface["id"]),
                    label=str(surface["label"]),
                    kind=str(surface["kind"]),
                    location=str(surface["location"]),
                    risk=risk,
                    probability=probability,
                    impact=impact,
                    confidence=confidence,
                    priority_dimensions=tuple(dimensions[:4]),
                    likely_window=self._window_for(str(surface["kind"])),
                    observations=observations,
                    controls=merged_controls,
                    assumptions=(
                        "Surface fields are normalized planning estimates.",
                        "No live probing or exploit execution occurred.",
                        "Shared-pressure correlation is simulated, not observed.",
                    ),
                    evidence_needed=evidence_needed[:6],
                    local_model_adjustment=float(micro.get("risk", 0.5)) - 0.5,
                )
            )

        findings.sort(key=lambda finding: finding.risk, reverse=True)
        max_dimension = max(dimension_hits.values(), default=1.0)
        dimension_scores = {
            dimension: self._clamp(dimension_hits.get(dimension, 0.0) / max_dimension)
            for dimension in DIMENSIONS
        }
        max_location = max(location_hits.values(), default=1.0)
        hotspots = [
            {"location": location, "risk": self._clamp(value / max_location)}
            for location, value in sorted(location_hits.items(), key=lambda item: item[1], reverse=True)
        ]
        max_hour = max(hourly_hits, default=1.0) or 1.0
        timeline = [
            {"hour": hour, "pressure": self._clamp(value / max_hour)}
            for hour, value in enumerate(hourly_hits)
        ]
        compromised_samples.sort()
        q05 = self._quantile(compromised_samples, 0.05)
        q50 = self._quantile(compromised_samples, 0.50)
        q95 = self._quantile(compromised_samples, 0.95)
        overall = statistics.fmean(finding.risk for finding in findings[: min(12, len(findings))]) if findings else 0.0
        endpoint_rate = 0.0 if total_inventory == 0 else q50 / total_inventory

        return {
            "mode": "defensive-hybrid-simulation",
            "overallRisk": self._clamp(overall),
            "dimensionScores": dimension_scores,
            "findings": [asdict(finding) for finding in findings],
            "hotspots": hotspots,
            "attackPaths": attack_paths,
            "timeline": timeline,
            "impactEstimate": {
                "inventoryModeled": total_inventory,
                "affectedEquivalentRange": {"low": q05, "median": q50, "high": q95},
                "affectedEquivalentPercent": {
                    "low": 0 if total_inventory == 0 else q05 / total_inventory,
                    "median": endpoint_rate,
                    "high": 0 if total_inventory == 0 else q95 / total_inventory,
                },
                "interpretation": (
                    "Equivalent affected inventory represents simulated loss of trustworthy operation, "
                    "not confirmed malware presence on each item."
                ),
            },
            "telemetry": {
                "engine": SIMSTATION.name,
                "simulatedQubits": SIMSTATION.simulated_qubits,
                "logicalCells": SIMSTATION.logical_cells,
                "observationFrames": SIMSTATION.observation_frames,
                "coherence": coherence,
                "worlds": worlds,
                "seed": seed,
                "localLlamaPasses": len(local_micro),
                "localGemmaLoaded": MODEL_MANAGER.status(GEMMA4_E2B.id).loaded,
                "surfaceLinks": len(links),
                "propagatedPaths": len(attack_paths),
                "redactions": 0,
                "durationMs": 0,
                "truthLabel": "quantum-inspired conventional simulation",
            },
            "summary": self._summary(findings, dimension_scores, q05, q95, total_inventory),
        }

    def _propagate_graph(
        self,
        probabilities: list[tuple[dict[str, Any], float, float, float]],
        links: list[dict[str, Any]],
    ) -> tuple[list[tuple[dict[str, Any], float, float, float]], list[dict[str, Any]]]:
        if not links:
            return probabilities, []
        by_id = {str(surface["id"]): [surface, probability, impact, confidence] for surface, probability, impact, confidence in probabilities}
        paths: list[dict[str, Any]] = []
        # Three bounded message-passing rounds approximate lateral trust pressure
        # without executing or recommending any intrusion behavior.
        for round_index in range(3):
            increments: dict[str, float] = defaultdict(float)
            for link in links:
                source = by_id.get(str(link["source"]))
                target = by_id.get(str(link["target"]))
                if source is None or target is None:
                    continue
                trust = float(link.get("trust", 0.5))
                control = float(link.get("controlStrength", 0.5))
                propagation = source[1] * trust * (1.0 - control) * (0.26 / (round_index + 1))
                increments[str(link["target"])] += propagation
                if round_index == 0:
                    paths.append({
                        "source": link["source"],
                        "target": link["target"],
                        "type": link.get("type", "depends-on"),
                        "pressure": self._clamp(propagation * 3.2),
                        "interpretation": "simulated trust-path amplification",
                    })
            for target_id, increment in increments.items():
                row = by_id[target_id]
                row[1] = self._clamp(1.0 - (1.0 - row[1]) * (1.0 - increment))
        paths.sort(key=lambda item: float(item["pressure"]), reverse=True)
        output = [(row[0], float(row[1]), float(row[2]), float(row[3])) for row in by_id.values()]
        return output, paths[:24]

    async def _local_llama_micro_passes(
        self, surfaces: list[dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """Lattice-tuned Llama micro-scans for any individual surface kind.

        Pipeline (from NAZA vpnscanner pattern, generalized beyond VPN):
        psutil metrics → RGB → PennyLane entropic score → optional GPT-5.6
        prompt rewrite → PUNKD + chunked Llama generation → JSON risk packet.
        """
        if not MODEL_MANAGER.status(LLAMA3_SMALL.id).loaded:
            return {}
        from .surface_lattice import scan_individual_surface

        ranked = sorted(
            surfaces,
            key=lambda item: float(item["criticality"]) * float(item["exposure"]),
            reverse=True,
        )[:24]
        outputs: dict[str, dict[str, Any]] = {}
        for surface in ranked:
            try:
                result = await scan_individual_surface(
                    surface,
                    use_gpt_composer=True,
                    use_chunked=True,
                    include_system_entropy=True,
                )
                outputs[str(surface["id"])] = {
                    "risk": self._clamp(float(result.get("risk", 0.5))),
                    "uncertainty": self._clamp(float(result.get("uncertainty", 0.5))),
                    "vectors": [
                        str(item)
                        for item in result.get("vectors", [])
                        if str(item) in DIMENSIONS
                    ][:4],
                    "observations": [
                        str(item)[:240] for item in result.get("observations", [])
                    ][:4],
                    "controls": [
                        str(item)[:280] for item in result.get("controls", [])
                    ][:4],
                    "evidence_needed": [
                        str(item)[:240] for item in result.get("evidence_needed", [])
                    ][:4],
                    "lattice": result.get("lattice"),
                }
            except Exception:
                continue
        return outputs

    @staticmethod
    def _micro_prompt(surface: dict[str, Any]) -> str:
        """Compatibility helper — preferred path is surface_lattice.scan_individual_surface."""
        from .surface_lattice import build_base_surface_prompt, lattice_tuning_block

        return build_base_surface_prompt(surface, lattice=lattice_tuning_block())

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        from .surface_lattice import parse_micro_json

        return parse_micro_json(text)
    @staticmethod
    def _council_packet(packet: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        return {
            "authorization": result["authorization"],
            "scenario": {
                "name": result["name"],
                "description": result["description"],
                "location": result["location"],
                "surfaceCount": len(packet.get("surfaces", [])),
            },
            "simulation": {
                "overallRisk": result["overallRisk"],
                "dimensionScores": result["dimensionScores"],
                "hotspots": result["hotspots"][:8],
                "attackPaths": result.get("attackPaths", [])[:8],
                "timeline": sorted(result["timeline"], key=lambda item: item["pressure"], reverse=True)[:6],
                "impactEstimate": result["impactEstimate"],
                "topFindings": result["findings"][:12],
            },
            "constraints": {
                "noLiveTargeting": True,
                "noAttributionWithoutEvidence": True,
                "noExploitInstructions": True,
                "redacted": True,
            },
        }

    @staticmethod
    def _window_for(kind: str) -> str:
        return {
            "identity": "08:00–18:00 local time, strongest during workload spikes",
            "human": "Shift changes, urgent requests, and high-interruption periods",
            "facility": "Visitor-heavy periods and shift transitions",
            "route": "Transitions between named locations and temporary connectivity",
            "vendor": "Approved support windows and after-hours maintenance",
            "api": "Continuous; elevated during deployment and token-rotation windows",
            "cloud": "Continuous; elevated near privilege and automation changes",
            "endpoint": "Continuous; elevated after software rollout or policy drift",
            "server": "Continuous; elevated during backup, patch, and maintenance windows",
        }.get(kind, "Continuous exposure with periodic control-drift peaks")

    @staticmethod
    def _temporal_vector(kind: str) -> list[float]:
        values: list[float] = []
        for hour in range(24):
            business = 8 <= hour <= 18
            shift = hour in {6, 7, 14, 15, 22, 23}
            if kind in {"identity", "human"}:
                value = 1.22 if business else 0.72
            elif kind in {"facility", "route"}:
                value = 1.30 if shift else (1.02 if business else 0.78)
            elif kind == "vendor":
                value = 1.18 if hour in {0, 1, 2, 20, 21, 22, 23} else 0.90
            else:
                value = 1.05 if hour in {1, 2, 3, 12, 13, 22, 23} else 0.96
            values.append(value)
        return values

    @staticmethod
    def _controls_for(dimensions: Iterable[str]) -> tuple[str, ...]:
        controls = {
            "credential": "Require phishing-resistant MFA, scoped secrets, and rapid rotation evidence.",
            "phishing": "Use protected communication paths, reporting drills, and high-risk-role coaching.",
            "endpoint": "Close EDR coverage gaps and rehearse one-click isolation with evidence capture.",
            "api": "Constrain tokens, validate schemas, rate-limit anomalies, and inventory machine identities.",
            "cloud": "Continuously compare effective IAM and trust paths to least-privilege policy.",
            "physical": "Correlate badge, visitor, camera, and after-hours access without profiling people.",
            "vendor": "Use just-in-time vendor access, session approval, recording, and assurance evidence.",
            "availability": "Segment recovery dependencies and prove immutable backup restoration.",
            "data": "Apply classification-aware egress controls, canaries, and data-access anomaly detection.",
        }
        return tuple(controls[dimension] for dimension in dimensions if dimension in controls)[:6]

    @staticmethod
    def _summary(
        findings: list[SurfaceFinding],
        dimensions: dict[str, float],
        low: int,
        high: int,
        total: int,
    ) -> str:
        leading = sorted(dimensions.items(), key=lambda item: item[1], reverse=True)[:3]
        top_surface = findings[0].label if findings else "no surface"
        return (
            f"The simulated defensive twin prioritizes {', '.join(item[0] for item in leading)}. "
            f"The highest-pressure modeled surface is {top_surface}. Across correlated worlds, "
            f"the equivalent inventory losing trustworthy operation falls between {low:,} and "
            f"{high:,} of {total:,} items at the 5th–95th percentile. This is a planning range, "
            "not a forensic machine count or attribution."
        )

    @staticmethod
    def _quantile(values: list[int], fraction: float) -> int:
        if not values:
            return 0
        index = min(len(values) - 1, max(0, int(round((len(values) - 1) * fraction))))
        return int(values[index])

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, value))


SUPER_SCANNER = SuperScanner()
