#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

pushd frontend >/dev/null
npm install
popd >/dev/null

echo "Bootstrap complete."
echo "Run backend: cd backend && ../.venv/bin/python manage.py runserver"
echo "Run frontend: cd frontend && npm run dev"
