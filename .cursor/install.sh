#!/usr/bin/env bash
# Idempotent bootstrap for the Salt Django backend on Cloud Agents.
# The Swift/iOS frontend under frontend/ requires Xcode/macOS and cannot be
# built or run on this Linux environment, so setup covers the backend only.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"

# Django 6.1 requires Python 3.12+, which the base image already provides.
# The stdlib venv module needs the distro python3-venv package, which is not
# present on the default image, so ensure it before creating the venv.
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y --no-install-recommends python3-venv
fi

cd "$BACKEND_DIR"

# Create the virtualenv only if it is missing so re-runs stay fast.
if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
. .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt

# Apply migrations so the local SQLite database is ready to use.
python manage.py migrate --noinput

echo "Salt backend bootstrap complete."
