#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip wheel setuptools
python -m pip install -r sidecar/requirements-dev.txt
cat <<'MSG'
Core sidecar installed.
For local models, install platform-compatible runtimes:
  python -m pip install -r sidecar/requirements-local.txt
Then run:
  ./tool/run_dev.sh
MSG
