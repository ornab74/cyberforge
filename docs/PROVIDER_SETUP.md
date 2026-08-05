# Model and Provider Setup

## Local model runtimes

Run:

```bash
./tool/setup_sidecar.sh
. .venv/bin/activate
python -m pip install -r sidecar/requirements-local.txt
```

Open **Vault & Models** in the Flutter app, create or unlock the local vault, then install and load either model.

### Gemma 4 E2B LiteRT-LM 4-bit

- Profile: `gemma4-e2b-litert-4bit`
- File: `gemma-4-E2B-it.litertlm`
- Runtime: LiteRT-LM 0.11.0
- Pinned SHA-256: `ab7838cdfc8f77e54d8ca45eadceb20452d9f01e4bfade03e5dce27911b27e42`

Gemma is used for private synthesis after the Llama micro-passes and numerical simulation.

### Llama 3 Small Q3_K_M

- Profile: `llama3-small-q3`
- File: `llama3-small-Q3_K_M.gguf`
- Runtime: llama.cpp through `llama-cpp-python`
- Pinned SHA-256: `8e4f4856fb84bafb895f1eb08e6c03e4be613ead2d942f91561aeac742a619aa`

Llama scans up to 24 high-pressure surfaces individually. It returns bounded JSON risk adjustments and never receives provider keys.

## Cloud council

Create or unlock the vault, choose **Add provider key**, and select:

- OpenAI for GPT-5.6;
- xAI for Grok 4.5;
- DigitalOcean for Kimi K3;
- Google for Gemini 3.6 Flash.

Cloud participation is off by default. Enable it per scan. The sidecar redacts the packet first and sends only abstract scenario and simulation summaries.

## xAI Grok

The adapter uses the xAI Responses API with model `grok-4.5`, `store: false`, and a fixed defensive system prompt. Store the key under provider ID `xai`.

## DigitalOcean

The adapter uses DigitalOcean Gradient AI’s OpenAI-compatible chat-completions endpoint and model ID `kimi-k3`. Store the DigitalOcean model-access token under provider ID `digitalocean`.

## OpenAI

The adapter uses the Responses API and model alias `gpt-5.6`. Store the key under provider ID `openai`.

## Google Gemini

The adapter calls `generateContent` with model `gemini-3.6-flash` and JSON response mode. Store the key under provider ID `gemini`.

## Environment import

Environment import is disabled by default because process environments are routinely exposed to child processes and diagnostic tools. To permit a one-time migration, set `CYBERFORGE_ALLOW_ENV_KEY_IMPORT=true`, unlock the vault, invoke the import endpoint, and remove the variables afterward.
