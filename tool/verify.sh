#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT/sidecar${PYTHONPATH:+:$PYTHONPATH}"
python -m compileall -q sidecar/cyberforge_sidecar
python -m pytest -q sidecar/tests
if command -v flutter >/dev/null 2>&1; then
  flutter pub get
  flutter analyze
  flutter test
else
  echo "flutter not installed; skipped Flutter checks" >&2
fi
if grep -Rni --exclude-dir=.git --exclude='*.zip' --exclude='*.tar.gz' -E 'a[n]med' .; then
  echo "A prohibited real-organization reference remains." >&2
  exit 1
fi
