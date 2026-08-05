#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ -f .venv/bin/activate ]]; then
  . .venv/bin/activate
fi
if ! python -c 'import fastapi, uvicorn, httpx, cryptography, argon2' >/dev/null 2>&1; then
  echo 'CyberForge backend dependencies are missing.' >&2
  echo 'Run ./tool/setup_sidecar.sh, then run ./tool/run_dev.sh again.' >&2
  echo 'Or install into the active environment: python -m pip install -r sidecar/requirements.txt' >&2
  exit 1
fi
export PYTHONPATH="$ROOT/sidecar${PYTHONPATH:+:$PYTHONPATH}"
python -m cyberforge_sidecar "$@"
