#!/usr/bin/env bash
# Per-boot startup for the Salt Django backend.
# The install phase already prepared the venv and database; here we only make
# sure the SQLite schema is up to date in case migrations changed since the
# snapshot was taken. The dev server itself runs as a named terminal.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT/backend"

if [ -x ".venv/bin/python" ]; then
  # shellcheck disable=SC1091
  . .venv/bin/activate
  python manage.py migrate --noinput
fi
