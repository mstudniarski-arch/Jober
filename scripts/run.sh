#!/usr/bin/env bash
# Lokalny przebieg skanu + commit raportu (używany przez launchd).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

.venv/bin/python -m scout.main

git add reports data/seen.json
git diff --cached --quiet || git commit -m "Raport $(date +%F)"
