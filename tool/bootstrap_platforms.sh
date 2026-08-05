#!/usr/bin/env bash
set -euo pipefail

if ! command -v flutter >/dev/null 2>&1; then
  echo "Flutter is required. Install it and run flutter doctor first." >&2
  exit 1
fi

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

flutter create \
  --project-name cyberforge \
  --org com.cyberforge \
  --platforms android,ios,linux,macos,windows,web \
  .

flutter pub get
printf '\nPlatform runners generated. Start with: flutter run -d linux\n'
