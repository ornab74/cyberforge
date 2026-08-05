# CyberForge 3

**CyberForge** is a local-first blue-team AI simulation system for modeling where cyber, credential, human, vendor, route, API, cloud, data, availability, and physical-security controls may fail under correlated pressure.

It combines a NAZA-style scanner, a seeded digital twin, real local models, optional cloud critics, encrypted key handling, post-quantum recovery, and a high-density Flutter command center.

> CyberForge is for synthetic scenarios and systems you own or are explicitly authorized to assess. It does not perform live exploitation and does not generate offensive procedures.

![CyberForge command center preview](docs/assets/cyberforge_v3_preview.png)

## Research monograph

The complete [CyberForge Research Monograph](CyberForge_Research_Monograph_Graylan_Janulis.docx) is also available below as one image per page for convenient reading on GitHub.

![CyberForge Research Monograph — page 1](docs/assets/monograph-pages/page-01.png)
![CyberForge Research Monograph — page 2](docs/assets/monograph-pages/page-02.png)
![CyberForge Research Monograph — page 3](docs/assets/monograph-pages/page-03.png)
![CyberForge Research Monograph — page 4](docs/assets/monograph-pages/page-04.png)
![CyberForge Research Monograph — page 5](docs/assets/monograph-pages/page-05.png)
![CyberForge Research Monograph — page 6](docs/assets/monograph-pages/page-06.png)
![CyberForge Research Monograph — page 7](docs/assets/monograph-pages/page-07.png)
![CyberForge Research Monograph — page 8](docs/assets/monograph-pages/page-08.png)
![CyberForge Research Monograph — page 9](docs/assets/monograph-pages/page-09.png)
![CyberForge Research Monograph — page 10](docs/assets/monograph-pages/page-10.png)
![CyberForge Research Monograph — page 11](docs/assets/monograph-pages/page-11.png)
![CyberForge Research Monograph — page 12](docs/assets/monograph-pages/page-12.png)
![CyberForge Research Monograph — page 13](docs/assets/monograph-pages/page-13.png)
![CyberForge Research Monograph — page 14](docs/assets/monograph-pages/page-14.png)
![CyberForge Research Monograph — page 15](docs/assets/monograph-pages/page-15.png)
![CyberForge Research Monograph — page 16](docs/assets/monograph-pages/page-16.png)
![CyberForge Research Monograph — page 17](docs/assets/monograph-pages/page-17.png)
![CyberForge Research Monograph — page 18](docs/assets/monograph-pages/page-18.png)
![CyberForge Research Monograph — page 19](docs/assets/monograph-pages/page-19.png)
![CyberForge Research Monograph — page 20](docs/assets/monograph-pages/page-20.png)
![CyberForge Research Monograph — page 21](docs/assets/monograph-pages/page-21.png)
![CyberForge Research Monograph — page 22](docs/assets/monograph-pages/page-22.png)
![CyberForge Research Monograph — page 23](docs/assets/monograph-pages/page-23.png)
![CyberForge Research Monograph — page 24](docs/assets/monograph-pages/page-24.png)
![CyberForge Research Monograph — page 25](docs/assets/monograph-pages/page-25.png)
![CyberForge Research Monograph — page 26](docs/assets/monograph-pages/page-26.png)
![CyberForge Research Monograph — page 27](docs/assets/monograph-pages/page-27.png)
![CyberForge Research Monograph — page 28](docs/assets/monograph-pages/page-28.png)
![CyberForge Research Monograph — page 29](docs/assets/monograph-pages/page-29.png)
![CyberForge Research Monograph — page 30](docs/assets/monograph-pages/page-30.png)
![CyberForge Research Monograph — page 31](docs/assets/monograph-pages/page-31.png)
![CyberForge Research Monograph — page 32](docs/assets/monograph-pages/page-32.png)
![CyberForge Research Monograph — page 33](docs/assets/monograph-pages/page-33.png)

## Core capabilities

- **Super Scanner:** models one surface or a connected collective of people-role aggregates, endpoints, identities, APIs, cloud systems, routes, facilities, suppliers, and data classes.
- **Optional geography:** accepts a named place, abstract zone, route, GPS coordinates, or no coordinates at all.
- **Real local Llama 3:** scans individual high-pressure surfaces through llama.cpp.
- **Real local Gemma 4 E2B 4-bit:** performs private synthesis through LiteRT-LM using the pinned `.litertlm` model.
- **Secure model council:** optionally adds GPT-5.6, Grok 4.5, DigitalOcean Kimi K3, and Google Gemini to the local council.
- **AEGIS-816 simulator:** runs seeded, reproducible Monte Carlo worlds plus bounded trust-graph propagation.
- **Advanced display:** risk arc, surface matrix, temporal pressure, equivalent operational impact, graph paths, hotspots, model disagreement, and BOOTCOM telemetry.
- **SIMCOM terminal:** boot, status, scan, timeline, impact, hotspots, paths, council, attribution boundary, and structured export.
- **Encrypted provider vault:** Argon2id unlock, record-level AES-256-GCM, hashed logical identifiers, data-key rotation, and short-lived sessions.
- **Encrypted model storage:** streamed SHA-256 verification, AES-GCM at rest, verified temporary decryption, and unload cleanup.
- **Post-quantum recovery:** optional ML-KEM + X25519 hybrid envelope with HKDF and AES-256-GCM.
- **Safety architecture:** explicit authorization, prompt firewall, recursive secret redaction, bounded inputs, local-first defaults, and no simulated actor/country attribution.

## Architecture

```text
Flutter CyberForge Command Center
          │ 127.0.0.1:8788
          ▼
FastAPI sidecar
  ├── authorization gate + prompt firewall
  ├── recursive secret redaction
  ├── surface and trust graph normalizer
  ├── Llama 3 per-surface micro-scans
  ├── AEGIS-816 Monte Carlo simulation
  ├── bounded graph-pressure propagation
  ├── Gemma 4 local private synthesis
  ├── optional GPT-5.6 / Grok 4.5 / Kimi K3 / Gemini critics
  ├── AES-GCM provider and model vault
  └── optional ML-KEM hybrid recovery
```

The “Dyson Sphere Gamma” and “81,611,511 qubits” language is a clearly labeled simulation interface. The implementation runs on conventional hardware.

## Quick start

### 1. Prepare the Python sidecar

```bash
./tool/setup_sidecar.sh
./tool/run_dev.sh
```

`setup_sidecar.sh` creates a project-local `.venv` and installs the FastAPI
backend dependencies. Keep the backend terminal running while using Flutter.

If you see `ModuleNotFoundError: No module named 'fastapi'`, the active virtual
environment does not contain the backend packages. From the repository root,
run:

```bash
deactivate 2>/dev/null || true
./tool/setup_sidecar.sh
./tool/run_dev.sh
```

Alternatively, install into an already-active environment:

```bash
python -m pip install --upgrade pip wheel setuptools
python -m pip install -r sidecar/requirements.txt
./tool/run_dev.sh
```

Verify the backend before launching Flutter:

```bash
curl http://127.0.0.1:8788/health
```

The response should contain `"status":"ok"`. Flutter expects the sidecar on
port `8788` by default.

The core simulator works without any model or provider key.

### 2. Add Flutter platforms when needed

```bash
./tool/bootstrap_platforms.sh
```

### Automatic backend startup

On Linux, macOS, and Windows desktop, the Flutter executable automatically:

1. Finds the repository root.
2. Creates `.venv` with Python 3.
3. Installs `sidecar/requirements.txt`.
4. Installs `sidecar/requirements-local.txt` (`llama-cpp-python`, LiteRT-LM,
   and the optional post-quantum runtime).
5. Starts the FastAPI sidecar with the project-local Python.

This may take several minutes on the first launch, especially when a platform
has to build a `llama-cpp-python` wheel. Subsequent launches reuse the venv.
The Flutter UI still opens if setup fails, so the Settings page can report the
problem. To manage the sidecar manually instead:

```bash
CYBERFORGE_AUTO_BACKEND=false flutter run -d linux
```

For a manual setup, run `./tool/setup_sidecar.sh` first. The automatic path is
disabled during Flutter tests.

### 3. Run the command center

```bash
flutter pub get
flutter run -d linux
```

The default sidecar URL is `http://127.0.0.1:8788`. Override it at build time:

```bash
flutter run -d linux \
  --dart-define=CYBERFORGE_SIDECAR_URL=http://127.0.0.1:8788
```

## Enable real local models

Install platform-compatible runtime packages:

```bash
. .venv/bin/activate
python -m pip install -r sidecar/requirements-local.txt
```

In **Vault & Models**:

1. Create or unlock the local vault.
2. Install the model. CyberForge downloads, hashes, and encrypts it.
3. Load the model. CyberForge decrypts it into a restrictive temporary file, verifies the hash again, and starts the runtime.

Pinned profiles:

| Profile | File | Runtime | SHA-256 |
|---|---|---|---|
| Gemma 4 E2B 4-bit | `gemma-4-E2B-it.litertlm` | LiteRT-LM 0.11.0 | `ab7838cdfc8f77e54d8ca45eadceb20452d9f01e4bfade03e5dce27911b27e42` |
| Llama 3 Small Q3_K_M | `llama3-small-Q3_K_M.gguf` | llama.cpp | `8e4f4856fb84bafb895f1eb08e6c03e4be613ead2d942f91561aeac742a619aa` |

## Configure cloud models securely

Open **Vault & Models → Add provider key**. Keys are encrypted locally and never inserted into scenario JSON.

- `openai` → GPT-5.6 through the Responses API.
- `xai` → Grok 4.5 through the xAI Responses API with server-side storage disabled.
- `digitalocean` → Kimi K3 through DigitalOcean Gradient AI’s OpenAI-compatible endpoint.
- `gemini` → Gemini 3.6 Flash through `generateContent`.

Remote participation is off for every new scan. Turning it on sends only a recursively redacted simulation packet.

## Scenario example

```json
{
  "name": "Synthetic Multisite Operations Twin",
  "authorization": {
    "authorized": true,
    "statement": "I own or am explicitly authorized to simulate every surface in this scenario.",
    "scope": "Synthetic digital twin",
    "synthetic": true
  },
  "location": {
    "name": "Named zone",
    "latitude": null,
    "longitude": null
  },
  "worlds": 12000,
  "seed": 3923929,
  "includeRemoteModels": false,
  "surfaces": [
    {
      "id": "identity-plane",
      "label": "Workforce identity plane",
      "kind": "identity",
      "location": "All sites",
      "criticality": 0.94,
      "exposure": 0.62,
      "controlStrength": 0.64,
      "humanPressure": 0.73,
      "telemetryConfidence": 0.82,
      "inventoryCount": 1600,
      "signals": ["mixed MFA coverage", "password reset volume"]
    }
  ],
  "links": [
    {
      "source": "identity-plane",
      "target": "remote-access",
      "type": "authenticates",
      "trust": 0.82,
      "controlStrength": 0.66
    }
  ]
}
```

Surface values are planning estimates from 0 to 1. They are not vulnerability scan results unless they were derived from an authorized passive connector and clearly labeled.

## SIMCOM

```text
bootcom
status
scan
scan --worlds 24000 --seed 3923929
scan --remote
timeline
impact
hotspots
paths
council
origin
export
```

`origin` explains the attribution boundary; it does not guess an actor or country.

## Validation

```bash
./tool/verify.sh
```

This runs Python compilation and tests, scans for prohibited real-organization references, and runs Flutter analysis/tests when Flutter is installed.

## Documentation

- [Architecture v3](docs/ARCHITECTURE_V3.md)
- [Cryptography](docs/CRYPTOGRAPHY.md)
- [Provider setup](docs/PROVIDER_SETUP.md)
- [Threat model](docs/THREAT_MODEL.md)
- [Defensive prompting](docs/PROMPTING.md)
- [Safety policy](SAFETY.md)
- [Security policy](SECURITY.md)
- [Validation report](docs/VALIDATION.md)

## Repository publication

This package is standalone. To create a new GitHub repository under your authenticated account:

```bash
./tool/publish_to_github.sh ornab74 cyberforge
```

The publishing script refuses to overwrite an unrelated `origin`.
