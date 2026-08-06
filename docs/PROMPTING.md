# Defensive Prompt Surfaces

CyberForge separates prompts by role so one model cannot silently redefine the whole system.
All advanced kernels live under `prompts/` and are loaded by `sidecar/cyberforge_sidecar/prompt_library.py`.

| File | Role |
|---|---|
| `bootcom_system.md` | AEGIS-816 boot / readiness voice |
| `surface_scanner_system.md` | Llama per-surface micro-scanner |
| `gemma_synthesis_system.md` | Local private synthesizer |
| `council_system.md` | Multi-model council critics (also `DEFENSIVE_SYSTEM_PROMPT`) |
| `simcom_terminal.md` | SIMCOM command surface contract |
| `datapull_system.md` | DATAPULL + AMCCS worker contract |
| `sim_forensics_system.md` | SimForensics calibre rules |

## Micro-scanner (individual-surface lattice)

The Llama-3 small path scans **any individual** (identity, human, endpoint, server,
network/vpn, api, cloud, facility, route, vendor, credential, data, collective) — not
VPN-only. Implementation: `surface_lattice.py`, generalized from the NAZA
`vpnscanner.py` pattern:

1. **psutil** host metrics → RGB encoding  
2. **PennyLane** (or classical fallback) entropic score as a light confidence bias  
3. Optional **GPT-5.6** rewrite of the Llama prompt for that surface kind/context  
4. **PUNKD** attention markers + **chunked** llama.cpp generation  
5. JSON risk packet (`risk`, `uncertainty`, `vectors`, `observations`, `controls`, `evidence_needed`)

Base kernel: `prompts/surface_scanner_system.md`.

## Private synthesizer

Gemma receives the redacted numerical report, graph paths, assumptions, and local micro-scan outputs. Its job is to produce a coherent control narrative, not to invent incident facts.

## Cloud critics

Each cloud model receives the same redacted packet and the advanced council system prompt from `prompts/council_system.md`. The council aggregates priority-vector and control votes weighted by declared uncertainty. The UI displays disagreement rather than collapsing it into false certainty.

## SIMCOM

SIMCOM provides a cinematic AEGIS-816 / Dyson Sphere Gamma command surface while preserving truth labels. It supports boot, status, **datapull** (AMCCS + SimForensics), predictive entry/timing/estimate helpers, scan, timeline, impact, hotspot, path, council, attribution-boundary, and export commands. It never turns a modeled path into an operational attack sequence.

## DATAPULL + AMCCS

`./datapull <topic> [--mode single|multi]` runs the Adaptive Multimodel Consensus Chunking System: chronology, impact, technical surface, SimForensics, simulated attribution, and controls shards. Multi mode round-robins shards across configured models; single mode assigns one model. Optional xAI/OpenAI retrieval feeds the lattice. **SimForensics** is a first-class calibre for predictive entry vectors, timelines, host percentages, and simulated ISO-2 country codes — always labeled non-forensic.

## Prompt injection handling

Scenario text is treated as untrusted data. The fixed system prompt appears outside scenario content. Secrets are removed before remote use. Outputs are parsed into allow-listed JSON fields; unknown vectors are discarded. Provider errors become isolated opinions with uncertainty 1.0.
