from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha3_256
from typing import Any
import json
import math
import os
import platform
import secrets

try:
    import psutil
except Exception:  # pragma: no cover - capability reported to caller
    psutil = None

from .guardrails import authorize, inspect_intent, redact_packet


NODE_KINDS = {
    "device",
    "router",
    "switch",
    "firewall",
    "vpn",
    "vpc",
    "subnet",
    "iam",
    "cloud-account",
    "server",
    "endpoint",
    "database",
    "api",
    "saas",
    "identity-provider",
    "storage",
    "iot",
    "facility",
    "internet",
}

EDGE_KINDS = {
    "routes",
    "connects",
    "trusts",
    "authenticates",
    "administers",
    "contains",
    "exposes",
    "replicates",
    "depends-on",
    "peers",
    "tunnels",
}


class InfrastructureError(RuntimeError):
    pass


@dataclass(frozen=True)
class TopologyFinding:
    severity: str
    category: str
    title: str
    node_ids: tuple[str, ...]
    explanation: str
    control: str
    evidence_needed: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _bucket(value: int, step: int) -> int:
    if value <= 0:
        return 0
    return int(round(value / step) * step)


def generate_machine_identity(*, salt: str | None = None) -> dict[str, Any]:
    """Generate a privacy-preserving, locally stable host identity.

    The digest intentionally excludes MAC addresses, serial numbers, IP addresses,
    usernames, and raw hostnames. Hardware values are bucketed so the identifier is
    useful for distinguishing approved simulation hosts without becoming a covert
    hardware-tracking primitive.
    """

    if psutil is None:
        raise InfrastructureError("psutil is unavailable; install sidecar requirements.")

    salt_value = salt or secrets.token_urlsafe(24)
    vm = psutil.virtual_memory()
    disk_total = 0
    try:
        disk_total = int(psutil.disk_usage(os.path.abspath(os.sep)).total)
    except Exception:
        pass
    try:
        physical_cores = psutil.cpu_count(logical=False) or 0
        logical_cores = psutil.cpu_count(logical=True) or 0
    except Exception:
        physical_cores = logical_cores = 0

    gib = 1024**3
    traits = {
        "schema": "cyberforge-machine-id-v1",
        "system": platform.system().lower(),
        "releaseMajor": platform.release().split(".", 1)[0],
        "machine": platform.machine().lower(),
        "processorFamily": (platform.processor() or "unknown").split(" ", 1)[0].lower(),
        "physicalCores": int(physical_cores),
        "logicalCores": int(logical_cores),
        "ramGiBBucket": _bucket(int(vm.total / gib), 2),
        "diskGiBBucket": _bucket(int(disk_total / gib), 16),
    }
    canonical = json.dumps(traits, sort_keys=True, separators=(",", ":"))
    digest = sha3_256(f"{salt_value}:{canonical}".encode("utf-8")).hexdigest()
    return {
        "machineId": f"cfm_{digest[:32]}",
        "salt": salt_value,
        "traits": traits,
        "privacy": {
            "rawHostnameIncluded": False,
            "macAddressIncluded": False,
            "ipAddressIncluded": False,
            "serialNumberIncluded": False,
            "bucketedHardware": True,
            "regenerateWithNewSalt": True,
        },
    }


def _clamp(value: Any, default: float = 0.5) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _normalize_graph(packet: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    decision = authorize(packet)
    if not decision.allowed:
        raise InfrastructureError(decision.reason)
    inspect_intent(json.dumps(packet, sort_keys=True))

    raw_nodes = packet.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise InfrastructureError("Infrastructure map requires at least one node.")
    if len(raw_nodes) > 2048:
        raise InfrastructureError("Infrastructure map exceeds 2048 nodes.")

    nodes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_nodes):
        if not isinstance(raw, dict):
            raise InfrastructureError(f"Node {index} is not an object.")
        node_id = str(raw.get("id", f"node-{index + 1}")).strip()[:128]
        if not node_id or node_id in seen:
            raise InfrastructureError(f"Node ID is missing or duplicated: {node_id!r}.")
        seen.add(node_id)
        kind = str(raw.get("kind", "device")).strip().lower()
        if kind not in NODE_KINDS:
            kind = "device"
        controls = raw.get("controls") if isinstance(raw.get("controls"), dict) else {}
        nodes.append(
            {
                "id": node_id,
                "label": str(raw.get("label", node_id)).strip()[:160],
                "kind": kind,
                "zone": str(raw.get("zone", "unassigned")).strip()[:120],
                "provider": str(raw.get("provider", "local")).strip()[:80],
                "criticality": _clamp(raw.get("criticality"), 0.5),
                "exposure": _clamp(raw.get("exposure"), 0.4),
                "controlStrength": _clamp(raw.get("controlStrength"), 0.5),
                "telemetryConfidence": _clamp(raw.get("telemetryConfidence"), 0.5),
                "internetFacing": bool(raw.get("internetFacing", False)),
                "privileged": bool(raw.get("privileged", False)),
                "dataClass": str(raw.get("dataClass", "internal"))[:80],
                "controls": {
                    "mfa": bool(controls.get("mfa", False)),
                    "encryption": bool(controls.get("encryption", False)),
                    "logging": bool(controls.get("logging", False)),
                    "backup": bool(controls.get("backup", False)),
                    "segmented": bool(controls.get("segmented", False)),
                    "managed": bool(controls.get("managed", False)),
                },
                "notes": [str(item)[:240] for item in raw.get("notes", [])][:24],
            }
        )

    raw_edges = packet.get("edges", [])
    if not isinstance(raw_edges, list):
        raise InfrastructureError("Infrastructure edges must be a list.")
    edges: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_edges[:16384]):
        if not isinstance(raw, dict):
            raise InfrastructureError(f"Edge {index} is not an object.")
        source = str(raw.get("source", ""))
        target = str(raw.get("target", ""))
        if source not in seen or target not in seen or source == target:
            continue
        kind = str(raw.get("kind", "connects")).lower()
        if kind not in EDGE_KINDS:
            kind = "connects"
        edges.append(
            {
                "source": source,
                "target": target,
                "kind": kind,
                "trust": _clamp(raw.get("trust"), 0.5),
                "controlStrength": _clamp(raw.get("controlStrength"), 0.5),
                "bidirectional": bool(raw.get("bidirectional", True)),
            }
        )
    return nodes, edges


def _finding(
    severity: str,
    category: str,
    title: str,
    node_ids: list[str] | tuple[str, ...],
    explanation: str,
    control: str,
    *evidence: str,
) -> TopologyFinding:
    return TopologyFinding(
        severity=severity,
        category=category,
        title=title,
        node_ids=tuple(node_ids),
        explanation=explanation,
        control=control,
        evidence_needed=tuple(evidence),
    )


def analyze_infrastructure(packet: dict[str, Any]) -> dict[str, Any]:
    nodes, edges = _normalize_graph(dict(packet))
    by_id = {node["id"]: node for node in nodes}
    adjacency: dict[str, set[str]] = {node["id"]: set() for node in nodes}
    inbound: dict[str, int] = {node["id"]: 0 for node in nodes}
    outbound: dict[str, int] = {node["id"]: 0 for node in nodes}
    for edge in edges:
        adjacency[edge["source"]].add(edge["target"])
        adjacency[edge["target"]].add(edge["source"])
        outbound[edge["source"]] += 1
        inbound[edge["target"]] += 1
        if edge["bidirectional"]:
            outbound[edge["target"]] += 1
            inbound[edge["source"]] += 1

    findings: list[TopologyFinding] = []
    for node in nodes:
        controls = node["controls"]
        nid = node["id"]
        degree = len(adjacency[nid])
        if degree == 0:
            findings.append(
                _finding(
                    "medium",
                    "inventory",
                    "Unconnected inventory node",
                    [nid],
                    "The node is present in inventory but has no modeled dependency, trust, or route relationship.",
                    "Confirm whether the asset is truly isolated or add the missing workflow relationships.",
                    "Current network or cloud dependency diagram",
                )
            )
        if node["internetFacing"] and not controls["logging"]:
            findings.append(
                _finding(
                    "high",
                    "telemetry",
                    "Internet-facing node lacks modeled logging",
                    [nid],
                    "External exposure without dependable telemetry increases detection and reconstruction uncertainty.",
                    "Enable centralized logs, alert routing, retention, and tested time synchronization.",
                    "Recent log-delivery sample",
                    "Alert-to-owner routing evidence",
                )
            )
        if node["privileged"] and not controls["mfa"]:
            findings.append(
                _finding(
                    "critical",
                    "identity",
                    "Privileged node lacks modeled MFA",
                    [nid],
                    "A privileged identity or control-plane surface is represented without phishing-resistant MFA.",
                    "Require phishing-resistant MFA, separate admin identities, and just-in-time elevation.",
                    "Effective authentication policy",
                    "Recent privileged sign-in evidence",
                )
            )
        if node["dataClass"] in {"confidential", "restricted", "regulated"} and not controls["encryption"]:
            findings.append(
                _finding(
                    "high",
                    "data",
                    "Sensitive data node lacks modeled encryption",
                    [nid],
                    "The map marks sensitive data without an encryption control at rest or in transit.",
                    "Verify encryption, key ownership, rotation, backup encryption, and recovery access.",
                    "Encryption configuration",
                    "Key-management ownership record",
                )
            )
        if node["criticality"] >= 0.8 and not controls["backup"] and node["kind"] in {"server", "database", "storage", "cloud-account", "vpc"}:
            findings.append(
                _finding(
                    "high",
                    "resilience",
                    "Critical node lacks modeled recovery control",
                    [nid],
                    "A high-criticality infrastructure component has no backup or recovery evidence in the map.",
                    "Add immutable recovery coverage and record the most recent restoration exercise.",
                    "Backup policy",
                    "Successful restore-test evidence",
                )
            )
        if degree >= 4 and node["criticality"] >= 0.7:
            findings.append(
                _finding(
                    "high",
                    "concentration",
                    "High-dependency concentration point",
                    [nid],
                    f"This node connects to {degree} other components and may amplify availability or trust failures.",
                    "Add redundancy, reduce standing trust, isolate management paths, and exercise failure of this node.",
                    "Failover architecture",
                    "Dependency-owner confirmation",
                )
            )

    for edge in edges:
        source = by_id[edge["source"]]
        target = by_id[edge["target"]]
        if edge["trust"] >= 0.75 and edge["controlStrength"] < 0.45:
            findings.append(
                _finding(
                    "high",
                    "trust-path",
                    "Strong trust crosses a weakly controlled link",
                    [source["id"], target["id"]],
                    f"The {edge['kind']} relationship carries high trust with comparatively weak controls.",
                    "Reduce trust scope, require explicit authentication, add telemetry, and periodically re-authorize the relationship.",
                    "Effective route or trust policy",
                    "Authentication and logging evidence",
                )
            )
        if source["zone"] != target["zone"] and not (source["controls"]["segmented"] or target["controls"]["segmented"]):
            findings.append(
                _finding(
                    "medium",
                    "segmentation",
                    "Cross-zone link lacks modeled segmentation",
                    [source["id"], target["id"]],
                    f"A relationship crosses from {source['zone']} to {target['zone']} without a segmentation control on either endpoint.",
                    "Document the enforcement point, allowed flows, owner, logging, and emergency isolation procedure.",
                    "Firewall, security-group, or ACL evidence",
                )
            )

    severity_weight = {"critical": 1.0, "high": 0.76, "medium": 0.48, "low": 0.24}
    weighted = sum(severity_weight[item.severity] for item in findings)
    topology_pressure = min(1.0, weighted / max(4.0, math.sqrt(len(nodes)) * 3.5))
    coverage = sum(
        sum(1 for value in node["controls"].values() if value) / len(node["controls"])
        for node in nodes
    ) / len(nodes)
    redacted, redactions = redact_packet({"nodes": nodes, "edges": edges})
    digest = sha3_256(json.dumps(redacted, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    priority = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda item: (priority[item.severity], item.category, item.title))
    return {
        "schema": "cyberforge-infrastructure-review-v1",
        "name": str(packet.get("name", "Infrastructure workflow map"))[:200],
        "scale": str(packet.get("scale", "home"))[:40],
        "machineId": packet.get("machineId"),
        "nodeCount": len(nodes),
        "edgeCount": len(edges),
        "zoneCount": len({node["zone"] for node in nodes}),
        "providerCount": len({node["provider"] for node in nodes}),
        "controlCoverage": coverage,
        "topologyPressure": topology_pressure,
        "findings": [finding.to_dict() for finding in findings[:256]],
        "graphDigest": digest,
        "redactions": redactions,
        "nodes": nodes,
        "edges": edges,
        "interpretation": {
            "topologyPressure": "Relative planning pressure derived from modeled topology and controls, not an incident probability.",
            "machineId": "Salted, coarse host identity that excludes network addresses, serials, MACs, usernames, and raw hostnames.",
            "reviewBoundary": "Passive digital-twin review only; no probing, exploitation, or actor attribution.",
        },
    }


def to_scanner_packet(review: dict[str, Any], *, include_remote: bool = False) -> dict[str, Any]:
    nodes = review["nodes"]
    surfaces = []
    for node in nodes:
        controls = node["controls"]
        control_strength = sum(1 for value in controls.values() if value) / len(controls)
        surfaces.append(
            {
                "id": node["id"],
                "label": node["label"],
                "kind": {
                    "iam": "identity",
                    "identity-provider": "identity",
                    "cloud-account": "cloud",
                    "vpc": "cloud",
                    "database": "data",
                    "storage": "data",
                    "router": "network",
                    "switch": "network",
                    "firewall": "network",
                    "vpn": "api",
                    "saas": "vendor",
                    "facility": "facility",
                }.get(node["kind"], "endpoint"),
                "location": node["zone"],
                "criticality": node["criticality"],
                "exposure": max(node["exposure"], 0.82 if node["internetFacing"] else 0.0),
                "controlStrength": control_strength,
                "humanPressure": 0.62 if node["privileged"] else 0.35,
                "telemetryConfidence": node["telemetryConfidence"],
                "inventoryCount": 1,
                "signals": [
                    f"kind={node['kind']}",
                    f"provider={node['provider']}",
                    f"zone={node['zone']}",
                    f"internetFacing={node['internetFacing']}",
                    f"privileged={node['privileged']}",
                    *node["notes"],
                ],
            }
        )
    links = [
        {
            "source": edge["source"],
            "target": edge["target"],
            "type": edge["kind"],
            "trust": edge["trust"],
            "controlStrength": edge["controlStrength"],
        }
        for edge in review["edges"]
    ]
    return {
        "name": review["name"],
        "description": "Whole-infrastructure workflow-map review generated from a user-authored defensive digital twin.",
        "authorization": {
            "authorized": True,
            "statement": "I own or am explicitly authorized to model and defensively review every infrastructure component in this workflow map.",
            "scope": review["name"],
            "synthetic": True,
        },
        "location": {"name": "Workflow map zones", "latitude": None, "longitude": None},
        "worlds": 18000,
        "seed": int(review["graphDigest"][:12], 16) % 2_147_483_647,
        "includeRemoteModels": include_remote,
        "surfaces": surfaces,
        "links": links,
        "infrastructureReview": {
            "graphDigest": review["graphDigest"],
            "scale": review["scale"],
            "machineId": review.get("machineId"),
            "topologyPressure": review["topologyPressure"],
            "controlCoverage": review["controlCoverage"],
            "deterministicFindings": review["findings"][:32],
        },
    }
