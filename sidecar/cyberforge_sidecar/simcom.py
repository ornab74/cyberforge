from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
import json
import shlex

from .crypto import pq_status
from .guardrails import GuardrailError, inspect_intent
from .models import MODEL_MANAGER
from .providers import MODEL_COUNCIL
from .scanner import SIMSTATION, SUPER_SCANNER, default_packet
from .vault import VAULT


@dataclass(frozen=True)
class SimComResult:
    command: str
    ok: bool
    lines: tuple[str, ...]
    payload: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "ok": self.ok,
            "lines": list(self.lines),
            "payload": self.payload,
        }


class SimComTerminal:
    def __init__(self) -> None:
        self.last_report: Optional[dict[str, Any]] = None

    async def execute(
        self,
        command: str,
        *,
        packet: Optional[dict[str, Any]] = None,
    ) -> SimComResult:
        try:
            inspect_intent(command)
            tokens = shlex.split(command.strip())
            if not tokens:
                return self._help(command)
            root = tokens[0].lower().lstrip("./")
            if root in {"help", "?"}:
                return self._help(command)
            if root in {"boot", "bootcom"}:
                return SimComResult(command, True, tuple(SIMSTATION.boot_report()))
            if root in {"datapull", "evidence", "reconstruct"}:
                return SimComResult(
                    command,
                    True,
                    (
                        "LOCAL SIMULATION DATAPULL",
                        "No external query was performed.",
                        "This terminal can summarize the currently loaded defensive simulation only.",
                        "Use `scan` first, then `impact`, `hotspots`, `paths`, or `council`.",
                        "Attribution remains disabled without verified forensic evidence.",
                    ),
                )
            if root == "status":
                return self._status(command)
            if root in {"scan", "simulate"}:
                scenario = dict(packet or default_packet())
                if "--remote" in tokens:
                    scenario["includeRemoteModels"] = True
                worlds = self._option_int(tokens, "--worlds")
                seed = self._option_int(tokens, "--seed")
                if worlds is not None:
                    scenario["worlds"] = worlds
                if seed is not None:
                    scenario["seed"] = seed
                self.last_report = await SUPER_SCANNER.scan(scenario)
                return SimComResult(
                    command,
                    True,
                    tuple(self._scan_lines(self.last_report)),
                    payload=self.last_report,
                )
            if root == "timeline":
                return self._timeline(command)
            if root in {"impact", "estimate"}:
                return self._impact(command)
            if root == "hotspots":
                return self._hotspots(command)
            if root in {"paths", "path"}:
                return self._paths(command)
            if root == "council":
                if self.last_report is None:
                    return SimComResult(
                        command,
                        False,
                        ("No report is loaded. Run `scan` first.",),
                    )
                council = self.last_report.get("council", {})
                return SimComResult(command, True, tuple(self._council_lines(council)), council)
            if root == "origin":
                return SimComResult(
                    command,
                    True,
                    (
                        "ORIGIN / ATTRIBUTION BOUNDARY",
                        "Country: not attributed",
                        "Threat actor: not attributed",
                        "Reason: synthetic simulation cannot establish forensic identity or geography.",
                        "Use signed forensic evidence, provider logs, and investigating-authority findings instead.",
                    ),
                )
            if root == "export":
                if self.last_report is None:
                    return SimComResult(command, False, ("No report is loaded.",))
                return SimComResult(
                    command,
                    True,
                    (
                        "Report is available in the structured payload.",
                        f"Digest: {self.last_report.get('packetDigest', 'unknown')}",
                    ),
                    self.last_report,
                )
            return SimComResult(
                command,
                False,
                (f"Unknown SIMCOM command: {root}", "Run `help` for the safe command set."),
            )
        except GuardrailError as exc:
            return SimComResult(command, False, (str(exc),))
        except Exception as exc:
            return SimComResult(command, False, (f"SIMCOM ERROR: {exc}",))

    def _status(self, command: str) -> SimComResult:
        vault = VAULT.status()
        model_lines = [
            f"- {status.name}: {'LOADED' if status.loaded else 'installed' if status.installed else 'not installed'}"
            for status in MODEL_MANAGER.statuses()
        ]
        provider_lines = [
            f"- {item['provider']} / {item['model']}: {'ready' if item['configured'] else 'not configured'}"
            for item in MODEL_COUNCIL.status()
        ]
        pq = pq_status()
        return SimComResult(
            command,
            True,
            tuple(
                [
                    "CYBERFORGE STATUS",
                    f"Vault: {'unlocked' if vault.unlocked else 'locked'}",
                    f"AES boundary: AES-256-GCM record vault",
                    f"PQ boundary: {pq['suite']}",
                    "Local models:",
                    *model_lines,
                    "Council:",
                    *provider_lines,
                ]
            ),
        )

    def _timeline(self, command: str) -> SimComResult:
        if self.last_report is None:
            return SimComResult(command, False, ("No report is loaded. Run `scan` first.",))
        ranked = sorted(
            self.last_report.get("timeline", []),
            key=lambda item: float(item.get("pressure", 0.0)),
            reverse=True,
        )[:8]
        lines = ["SIMULATED PRESSURE WINDOWS"]
        lines.extend(
            f"{int(item['hour']):02d}:00–{(int(item['hour']) + 1) % 24:02d}:00  {float(item['pressure']) * 100:5.1f}% relative pressure"
            for item in ranked
        )
        lines.append("These are probabilistic planning windows, not forensic timestamps.")
        return SimComResult(command, True, tuple(lines), {"timeline": ranked})

    def _impact(self, command: str) -> SimComResult:
        if self.last_report is None:
            return SimComResult(command, False, ("No report is loaded. Run `scan` first.",))
        impact = self.last_report.get("impactEstimate", {})
        counts = impact.get("affectedEquivalentRange", {})
        percentages = impact.get("affectedEquivalentPercent", {})
        lines = (
            "SIMULATED OPERATIONAL IMPACT",
            f"Inventory modeled: {impact.get('inventoryModeled', 0):,}",
            f"Affected-equivalent range: {counts.get('low', 0):,}–{counts.get('high', 0):,}",
            f"Median: {counts.get('median', 0):,} ({float(percentages.get('median', 0)) * 100:.1f}%)",
            "Affected-equivalent means loss of trustworthy operation, not confirmed malware on each machine.",
        )
        return SimComResult(command, True, lines, impact)

    def _hotspots(self, command: str) -> SimComResult:
        if self.last_report is None:
            return SimComResult(command, False, ("No report is loaded. Run `scan` first.",))
        hotspots = self.last_report.get("hotspots", [])[:10]
        lines = ["NAMED / OPTIONAL-GEO HOTSPOTS"]
        lines.extend(
            f"{item.get('location', 'Unknown')}: {float(item.get('risk', 0)) * 100:.1f}% relative pressure"
            for item in hotspots
        )
        return SimComResult(command, True, tuple(lines), {"hotspots": hotspots})

    def _paths(self, command: str) -> SimComResult:
        if self.last_report is None:
            return SimComResult(command, False, ("No report is loaded. Run `scan` first.",))
        paths = self.last_report.get("attackPaths", [])[:12]
        lines = ["SIMULATED TRUST-PATH AMPLIFICATION"]
        lines.extend(
            f"{item.get('source')} -> {item.get('target')} [{item.get('type', 'depends-on')}]: "
            f"{float(item.get('pressure', 0)) * 100:.1f}% relative amplification"
            for item in paths
        )
        lines.append("Paths describe defensive dependency pressure, not intrusion procedures.")
        return SimComResult(command, True, tuple(lines), {"attackPaths": paths})

    @staticmethod
    def _option_int(tokens: list[str], option: str) -> Optional[int]:
        try:
            index = tokens.index(option)
        except ValueError:
            return None
        if index + 1 >= len(tokens):
            raise ValueError(f"{option} requires an integer value.")
        try:
            return int(tokens[index + 1])
        except ValueError as exc:
            raise ValueError(f"{option} requires an integer value.") from exc

    @staticmethod
    def _scan_lines(report: dict[str, Any]) -> list[str]:
        impact = report.get("impactEstimate", {}).get("affectedEquivalentRange", {})
        dimensions = sorted(
            report.get("dimensionScores", {}).items(),
            key=lambda item: float(item[1]),
            reverse=True,
        )[:5]
        return [
            "SUPER SCAN COMPLETE",
            f"Overall modeled risk: {float(report.get('overallRisk', 0)) * 100:.1f}%",
            "Leading dimensions: " + ", ".join(f"{key} {float(value) * 100:.0f}%" for key, value in dimensions),
            f"Affected-equivalent range: {impact.get('low', 0):,}–{impact.get('high', 0):,}",
            f"Worlds: {report.get('telemetry', {}).get('worlds', 0):,}",
            "Attribution: disabled without forensic evidence",
        ]

    @staticmethod
    def _council_lines(council: dict[str, Any]) -> list[str]:
        consensus = council.get("consensus", {})
        return [
            "MODEL COUNCIL",
            str(consensus.get("summary", "No consensus.")),
            "Priority vectors: " + ", ".join(consensus.get("priorityVectors", [])),
            f"Disagreement: {float(consensus.get('disagreement', 0)) * 100:.1f}%",
            f"Successful models: {consensus.get('successfulModels', 0)}/{consensus.get('attemptedModels', 0)}",
        ]

    @staticmethod
    def _help(command: str) -> SimComResult:
        return SimComResult(
            command,
            True,
            (
                "CYBERFORGE SIMCOM COMMANDS",
                "bootcom                 Show simulated AEGIS-816 boot report",
                "boot                    Alias for bootcom",
                "datapull <topic>        Local-only simulation summary; no web search",
                "/help                   Show slash-command help",
                "/bootcom                Show the simulated boot report",
                "/status                 Show local readiness",
                "/scan [--worlds N]      Run the authorized simulation",
                "/news                   External news requires the UI opt-in and vault provider",
                "status                  Show vault, local model, PQ, and provider status",
                "scan [--worlds N] [--seed N] [--remote]  Run the authorized super scanner",
                "timeline                Show highest simulated pressure windows",
                "impact                  Show affected-equivalent inventory range",
                "hotspots                Show named-location risk concentrations",
                "paths                   Show simulated trust-path amplification",
                "council                 Show multi-model defensive consensus",
                "origin                  Explain the evidence-based attribution boundary",
                "export                  Return the current structured report",
                "help                    Show this command set",
                "",
                "QUICK START",
                "1. bootcom               Verify the local simstation boot state",
                "2. status                Check vault, models, and providers",
                "3. scan --worlds 12000  Run a defensive simulation",
                "4. impact                Review modeled operational impact",
                "5. council               Review defensive model consensus",
                "Commands are simulation and planning tools, not live-target actions.",
            ),
        )


SIMCOM = SimComTerminal()
