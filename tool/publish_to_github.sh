#!/usr/bin/env bash
set -euo pipefail

owner="${1:-ornab74}"
repo="${2:-cyberforge}"
visibility="${CYBERFORGE_VISIBILITY:-public}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI is required: https://cli.github.com/" >&2
  exit 1
fi

gh auth status >/dev/null

target="https://github.com/${owner}/${repo}.git"
if git remote get-url origin >/dev/null 2>&1; then
  current="$(git remote get-url origin)"
  if [[ "$current" != "$target" && "$current" != "git@github.com:${owner}/${repo}.git" ]]; then
    echo "Refusing to replace existing origin: $current" >&2
    exit 1
  fi
fi

if gh repo view "${owner}/${repo}" >/dev/null 2>&1; then
  echo "Repository ${owner}/${repo} already exists." >&2
  if ! git remote get-url origin >/dev/null 2>&1; then
    git remote add origin "$target"
  fi
  git push -u origin main
else
  gh repo create "${owner}/${repo}" \
    "--${visibility}" \
    --source=. \
    --remote=origin \
    --push \
    --description "Defense-first AI cybersecurity simulation and blue-team digital twin."
fi
