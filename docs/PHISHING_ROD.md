# CyberForge Phishing Rod Ω

Phishing Rod is a local-first browser credential gate and defensive phishing evidence system. It inspects a page only when navigation settles, a sensitive form appears, or the user focuses, pastes into, or submits a credential field. The browser extension sends a bounded packet to the loopback CyberForge sidecar and pauses sensitive input when the decision engine returns `PHISHING`, or when an uncertain `REVIEW` verdict involves credentials, payment data, MFA codes, or recovery secrets.

## Trust model

The visible interface may show `SAFE` or `PHISHING`, but the internal engine retains three states:

- `SAFE`: no strong danger was detected. This is not a guarantee.
- `PHISHING`: independent technical evidence justifies blocking.
- `REVIEW`: evidence is incomplete or conflicting.

A vision-model opinion cannot freeze a page by itself. It must be supported by an independent signal such as a known threat-list match, external sensitive-form destination, brand/domain mismatch, recovery-secret request, or another high-risk structural indicator.

## Implemented system

### Browser protection

- Chromium Manifest V3 extension under `extensions/phishing_rod/`
- Credential focus, typing, paste, and form-submission interception
- Fifteen-second SAFE leases followed by mandatory re-evaluation
- Mutation-aware rescans when forms, destinations, scripts, or links change
- Displayed-link versus actual-link mismatch collection
- Third-party script-origin inventory
- Form action, field type, autocomplete, hidden-field, target, and frame evidence
- Frosted blocking overlay with risk score, evidence signals, rescan, and safe navigation

### Privacy-preserving visual analysis

The extension captures a screenshot only when all of the following are true:

1. a sensitive field is present;
2. the local CyberForge broker reports that vision is enabled;
3. the current tab can be masked and captured successfully.

Before capture, the content script covers passwords, usernames, MFA fields, payment fields, editable content, email and phone inputs, token/secret fields, message areas, and elements marked `data-private`. The service worker then captures a low-quality JPEG of the visible tab, sends it only to the loopback broker, and restores the page immediately. Capture failure falls back to structural analysis.

Screenshot bytes, visible page text, credentials, and field values are not written to encrypted history. Persisted records contain only bounded structural evidence, hashes, decisions, prompt versions, and provenance.

### Isolated local vision adapter

`phishing_vision.py` provides an optional OpenAI-compatible local multimodal adapter configured with:

- `CYBERFORGE_PHISHING_VISION_URL`
- `CYBERFORGE_PHISHING_VISION_MODEL`
- `CYBERFORGE_PHISHING_VISION_TIMEOUT`
- `CYBERFORGE_PHISHING_VISION_MAX_FAILURES`
- `CYBERFORGE_PHISHING_VISION_COOLDOWN`

The endpoint must be explicit loopback HTTP. Redirects, proxy environment variables, and non-loopback destinations are rejected. The adapter uses a fixed trusted prompt, labels every page element as untrusted evidence, requests strict JSON, caps requests and responses, serializes inference, and opens a cooldown circuit after repeated failures.

### APIs

- `GET /v1/phishing-rod/status`
- `POST /v1/phishing-rod/analyze`
- `POST /v1/phishing-rod/prompt-chain/simulate`
- `POST /v1/phishing-rod/federation/votes/sign`
- `POST /v1/phishing-rod/federation/quorum`

## Signed review federation

The review-board prototype uses Ed25519-signed, expiring votes bound to one evidence digest. Quorum rejects:

- invalid or expired signatures;
- votes for a different evidence package;
- repeated votes from the same public key;
- insufficient reviewer diversity;
- insufficient organization-class diversity.

A shared `PHISHING` or `SAFE` decision requires configurable weighted support from multiple independent reviewers and at least two organization classes by default. Government, school, hospital, utility, corporate, nonprofit, platform, and research participants can contribute without granting any participant unilateral global blocking authority.

Quorum results include a deterministic decision digest, weighted vote totals, accepted/rejected counts, diversity requirements, expiry enforcement, and a truth label. They may be stored in the encrypted CyberForge system of record only with an unlocked vault and explicit consent.

## Prompt-chain blue-team laboratory

The symbolic simulator models indirect prompt injection without executing content or tools. It propagates taint through webpage, document, retrieval, summary, memory, checkpoint, training, and tool-request nodes. This adapts the uploaded Superchain Lab ideas around multi-tier tainted memory, capability-scoped symbolic tools, tamper-evident ledgers, replay digests, ontology drift, narrative feedback, and system-level coupling into defensive controls. The uploaded simulator explicitly separated working, episodic, semantic, and archive memory and filtered retrieval using taint thresholds. fileciteturn42file8L716-L795 It also enforced a symbolic capability kernel that denied network, shell, credential, scanning, exploitation, and execution payloads. fileciteturn42file3L225-L305

Recommended controls include:

- separate trusted controller instructions from untrusted documents;
- sanitize active instructions before memory ingestion;
- propagate provenance and taint across summaries, retrieval, and consolidation;
- quarantine tainted memory from fine-tuning and preference pipelines;
- require typed, expiring capability tokens for every side effect;
- bind tool calls to immutable evidence and policy decisions;
- replay suspicious behavior with networking and persistent memory disabled;
- compare clean versus suspect checkpoints, prompts, dependencies, and datasets;
- monitor semantic ontology drift rather than only policy wording;
- detect self-reinforcing causal and narrative attractors;
- impose retry, novelty, and escalation budgets;
- require human approval for any external report or block promotion.

The simulator produces research hypotheses and control recommendations, not proof of a real attack chain.

## Local setup

Run the CyberForge sidecar on loopback port 8787. In Chromium, open the extensions page, enable Developer Mode, choose **Load unpacked**, and select `extensions/phishing_rod`.

A compatible local multimodal server may be configured on loopback. Without it, Phishing Rod continues using deterministic URL, form, brand, link, script, redirect, recovery-secret, urgency, and prompt-injection evidence.

## Defensive response boundary

Allowed responses include local blocking, user warnings, organizational firewall rules for owned networks, provider abuse reports, registrar or hosting reports, standards-based threat-intelligence sharing, and authorized incident response.

The system must not perform unauthorized scanning, intrusion, denial of service, credential collection, coercive attribution, automated retaliation, or autonomous takedowns. Takedown actions remain with service providers, registrars, hosting providers, domain authorities, courts, and law enforcement operating under their own authority.
