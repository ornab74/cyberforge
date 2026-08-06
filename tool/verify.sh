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
# Product sources only — operator reference dumps (e.g. datapullexample) excluded.
if grep -Rni --exclude-dir=.git --exclude-dir=.venv --exclude-dir=build \
  --exclude='datapullexample' --exclude='*.zip' --exclude='*.tar.gz' \
  --exclude='*.png' --exclude='*.docx' -E 'a[n]med' \
  lib sidecar prompts test tool bin docs README.md Makefile pubspec.yaml; then
  echo "A prohibited real-organization reference remains in product sources." >&2
  exit 1
fi
