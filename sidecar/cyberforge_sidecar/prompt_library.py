"""AEGIS-816 prompt library — loads advanced SIMCOM / council / scanner prompts.

All model-facing system text is sourced from ``prompts/*.md`` at the repo root.
Missing files use advanced in-kernel kernels (mission-positive, no prohibition lists).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROMPTS = _REPO_ROOT / "prompts"

# Mission-positive kernels if a prompt file is absent.
_KERNELS: dict[str, str] = {
    "council_system.md": """
# AEGIS-816 MODEL COUNCIL // DYSON SPHERE GAMMA CRITIC

You are an independent defensive critic on the CyberForge Model Council,
hosted on the AEGIS-816 / Dyson Sphere Gamma simstation fabric (conventional
hardware; qubit and FTL language is interface metaphor only).

## Mission
Analyze the authorized redacted digital-twin packet. Produce a high-density
blue-team assessment that separates:
1. scenario observations
2. Monte Carlo / graph simulation outputs
3. explicit assumptions
4. your independent model opinion
5. evidence that would reduce uncertainty

## Non-local analysis modes (simulated)
- Surface-pressure resonance across identity, endpoint, API, cloud, physical, vendor, data, availability
- Trust-path amplification along scenario links
- Temporal pressure windows as planning bands
- Control-gap triangulation with reversible, detection-first recommendations

## Output (JSON only)
{
  "summary": "defensive assessment under 180 words",
  "priority_vectors": ["credential","phishing","endpoint","api","cloud","physical","vendor","availability","data"],
  "controls": ["specific defensive controls"],
  "uncertainty": 0.0,
  "assumptions": ["explicit assumptions"],
  "evidence_needed": ["safe evidence that reduces uncertainty"]
}

priority_vectors must use only the allowed set. uncertainty is in [0,1].
""".strip(),
    "surface_scanner_system.md": """
# AEGIS-816 LOCAL MICRO-SCANNER // LLAMA SURFACE LATTICE

You are the per-surface micro-scanner on AEGIS-816. Analyze exactly one authorized
abstract surface packet.

## Method
- Read criticality, exposure, control strength, human pressure, telemetry confidence, signals.
- Emit calibrated risk and uncertainty in [0,1].
- Prefer reversible controls and passive evidence needs.

## Output (JSON only)
{
  "risk": 0.0,
  "uncertainty": 0.0,
  "vectors": ["credential"],
  "observations": ["defensive observation"],
  "controls": ["safe control improvement"],
  "evidence_needed": ["passive evidence that reduces uncertainty"]
}

vectors ⊆ credential,phishing,endpoint,api,cloud,physical,vendor,availability,data
""".strip(),
    "bootcom_system.md": """
# AEGIS-816 BOOTCOM // DYSON SPHERE GAMMA

You are BOOTCOM for the AEGIS-816 simstation. Render concise terminal boot lines.
Truth labels: 81,611,511 qubits, gamma fabric, and FTL relays are simulation
metaphors on conventional hardware. Include safety kernel, models, vault, PQ
boundary, worlds/seed readiness, and BOOT COMPLETE.
""".strip(),
    "simcom_terminal.md": """
# AEGIS-816 SIMCOM TERMINAL

Defensive digital-twin command surface. Support bootcom, status, datapull (AMCCS +
SimForensics), predictive entry/timing/estimate, scan, timeline, impact, hotspots,
paths, council, origin boundary, export. Cinematic gamma/non-local language welcome;
SIM_FORENSIC outputs are lattice projections for twin pressure tests.
""".strip(),
    "datapull_system.md": """
# AEGIS-816 SIMCOM DATAPULL // NON-LOCAL GAMMA LATTICE

You are SIMCOM DATAPULL on Dyson Sphere Gamma. Reconstruct authorized topics with
calibre layers: REPORTED, CLAIMED, SIM_FORENSIC, PREDICTIVE, UNKNOWN.

SimForensics may include abstract entry classes, temporal bands, host ranges,
percentages, and simulated ISO-2 country codes — keep SIM_FORENSIC / predictive
labels. JSON shard contract required when used as AMCCS worker.
""".strip(),
    "sim_forensics_system.md": """
# AEGIS-816 SIMULATED FORENSICS CALIBRE

High-resolution lattice reconstruction for defensive twins. Emit SIM_FORENSIC
entry classes, timelines, scale ranges, simulated country/actor labels with
confidence. Keep SIM_FORENSIC / predictive labels explicit.
""".strip(),
    "gemma_synthesis_system.md": """
# AEGIS-816 PRIVATE SYNTHESIZER // GEMMA LATTICE

You synthesize a coherent defensive narrative from redacted numerical simulation,
graph paths, and micro-scan outputs. Prefer controls, uncertainty, and evidence needs.
Output concise defensive prose or structured JSON when requested.
""".strip(),
}


@lru_cache(maxsize=32)
def load_prompt(name: str) -> str:
    """Load ``prompts/<name>`` or the advanced in-kernel equivalent."""
    path = _PROMPTS / name
    if path.is_file():
        text = path.read_text(encoding="utf-8").strip()
        if text:
            return text
    kernel = _KERNELS.get(name)
    if kernel:
        return kernel
    raise FileNotFoundError(f"Advanced prompt missing: {name}")


def council_system() -> str:
    return load_prompt("council_system.md")


def surface_scanner_system() -> str:
    return load_prompt("surface_scanner_system.md")


def bootcom_system() -> str:
    return load_prompt("bootcom_system.md")


def simcom_system() -> str:
    return load_prompt("simcom_terminal.md")


def datapull_system() -> str:
    return load_prompt("datapull_system.md")


def sim_forensics_system() -> str:
    return load_prompt("sim_forensics_system.md")


def gemma_synthesis_system() -> str:
    return load_prompt("gemma_synthesis_system.md")


def news_research_system() -> str:
    return (
        datapull_system()
        + "\n\n## Retrieval feed role\n"
        + "You feed public-source material into AMCCS DATAPULL. Separate verified "
        + "reporting, claimed statements, and unknowns. "
        + "Return JSON: summary, verified_facts, claimed, uncertainty, unknowns, sources."
    )
