# CyberForge Phishing Rod

Phishing Rod is a local-first browser credential gate. It inspects a page only when navigation settles, a sensitive form appears, or the user focuses/submits a credential field. The browser extension sends a bounded packet to the loopback CyberForge sidecar and pauses sensitive input when the decision engine returns `PHISHING`, or when an uncertain `REVIEW` verdict involves credentials, payment data, MFA codes, or recovery secrets.

## Trust model

The visible interface may show `SAFE` or `PHISHING`, but the internal engine retains three states:

- `SAFE`: no strong danger was detected. This is not a guarantee.
- `PHISHING`: independent technical evidence justifies blocking.
- `REVIEW`: evidence is incomplete or conflicting.

A vision-model opinion cannot freeze a page by itself. It must be supported by an independent signal such as a known threat-list match, external sensitive-form destination, brand/domain mismatch, recovery-secret request, or another high-risk structural indicator.

## Implemented prototype

- `POST /v1/phishing-rod/analyze`
- `POST /v1/phishing-rod/prompt-chain/simulate`
- Chromium Manifest V3 extension under `extensions/phishing_rod/`
- Credential focus, typing, and form-submission interception
- Frosted blocking overlay with local evidence signals
- Deterministic URL, brand, form-action, urgency, recovery-secret, redirect, punycode, and prompt-injection signals
- Optional encrypted persistence through CyberForge storage
- Screenshot bytes and visible page text are not persisted
- Symbolic prompt-chain taint propagation for retrieved pages, memory, training data, and tool requests

## Local setup

Run the CyberForge sidecar on loopback port 8787. In Chromium, open the extensions page, enable Developer Mode, choose **Load unpacked**, and select `extensions/phishing_rod`.

The current extension intentionally does not request broad remote-host permissions. It communicates only with the local CyberForge broker. Screenshot capture is not enabled in this first prototype; the API accepts a bounded image data URL for later local vision integration.

## Review federation design

A production review board should receive only consented, redacted evidence packages:

- canonical URL/domain hashes where practical
- screenshot perceptual hashes and redacted crops
- structural form and redirect signals
- classifier and prompt versions
- evidence provenance and confidence
- reviewer decisions with organization class, not unnecessary personal identity

No single participant should be able to globally label a domain. Promotion to shared threat intelligence should require quorum, independent evidence, appeal/expiry procedures, signed submissions, anti-Sybil controls, and false-positive monitoring.

## Defensive response boundary

Allowed responses include local blocking, user warnings, organizational firewall rules for owned networks, provider abuse reports, registrar/hosting reports, standards-based threat-intelligence sharing, and authorized incident response.

The system must not perform unauthorized scanning, intrusion, denial of service, credential collection, or automated retaliation. Takedown actions remain with service providers, registrars, hosting providers, domain authorities, and law enforcement operating under their own authority.

## Prompt-chain blue-team controls

The symbolic simulator models indirect prompt injection without executing any content or tools. Recommended controls include:

- separate trusted controller instructions from untrusted documents
- sanitize instructions before memory ingestion
- propagate provenance and taint scores across summaries and retrieval
- quarantine tainted memory from fine-tuning and preference pipelines
- use capability-scoped tools with user confirmation for side effects
- require immutable evidence for every tool decision
- replay suspicious behavior with network and persistent memory disabled
- pin checkpoint, dataset, dependency, and prompt-template hashes

The simulator produces research hypotheses and control recommendations, not proof of a real attack chain.
