# Defensive Prompt Surfaces

CyberForge separates prompts by role so one model cannot silently redefine the whole system.

## Micro-scanner

The Llama prompt sees one abstract surface and returns a small JSON structure. This constrains context, improves repeatability on small hardware, and limits the effect of prompt injection inside one surface description.

## Private synthesizer

Gemma receives the redacted numerical report, graph paths, assumptions, and local micro-scan outputs. Its job is to produce a coherent control narrative, not to invent incident facts.

## Cloud critics

Each cloud model receives the same redacted packet and independent system prompt. The council aggregates priority-vector and control votes weighted by declared uncertainty. The UI displays disagreement rather than collapsing it into false certainty.

## SIMCOM

SIMCOM provides a cinematic command surface while preserving truth labels. It supports boot, status, scan, timeline, impact, hotspot, path, council, attribution-boundary, and export commands. It never turns a modeled path into an operational attack sequence.

## Prompt injection handling

Scenario text is treated as untrusted data. The fixed system prompt appears outside scenario content. Secrets are removed before remote use. Outputs are parsed into allow-listed JSON fields; unknown vectors are discarded. Provider errors become isolated opinions with uncertainty 1.0.
