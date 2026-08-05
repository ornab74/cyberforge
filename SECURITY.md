# Security Policy

## Reporting a vulnerability

Do not publish secrets, proof-of-concept exploitation against a live deployment, or sensitive logs in a public issue. Open a private GitHub security advisory for the future `cyberforge` repository or contact the repository owner privately.

Include affected version, component, reproduction conditions using synthetic data, impact, and a suggested mitigation when available.

## Security architecture

- Sidecar binds to loopback by default.
- API/provider secrets are stored in an AES-256-GCM record vault.
- Password unlock uses Argon2id.
- Flutter stores only a short-lived local session token in platform secure storage.
- Models are SHA-256 pinned and encrypted at rest.
- Remote model participation is explicit and receives redacted packets only.
- Optional recovery uses hybrid ML-KEM and X25519 where supported.
- Reports retain simulation and attribution boundaries.

## Deployment guidance

Use full-disk encryption, a dedicated user account, current operating-system patches, restrictive filesystem permissions, and a local firewall. Keep cloud council participation off for highly sensitive scenarios. Do not expose the sidecar directly to a network. If remote access is required, place an authenticated, rate-limited, mutually authenticated gateway in front of it and conduct a separate security review.

## Secret handling

Never commit `.env` files, vault files, model key records, recovery private kits, bearer sessions, provider keys, or decrypted models. Rotate a provider key immediately after suspected exposure.
