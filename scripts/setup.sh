#!/usr/bin/env bash
# Bootstrap a local development environment (POSIX shell / Git Bash).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "==> Copying environment templates (skipping any that already exist)"
[ -f .env ] || cp .env.example .env
[ -f backend/.env ] || cp backend/.env.example backend/.env
[ -f frontend/.env.local ] || cp frontend/.env.example frontend/.env.local

echo "==> Installing root + frontend npm workspace dependencies"
npm install

echo "==> Creating backend virtualenv and installing dependencies"
cd backend
python -m venv .venv
if [ -f .venv/Scripts/activate ]; then
  source .venv/Scripts/activate # Windows
else
  source .venv/bin/activate # macOS/Linux
fi
pip install --upgrade pip
pip install -e ".[dev]"
cd "$ROOT_DIR"

echo "==> Installing pre-commit hooks"
pip install --user pre-commit >/dev/null 2>&1 || true
pre-commit install || echo "pre-commit not found on PATH — install it manually: pip install pre-commit"

echo ""
echo "Setup complete. Next steps:"
echo "  docker compose up -d          # start Postgres/Redis/MinIO/backend/frontend"
echo "  cd backend && alembic upgrade head   # if running the backend outside Docker"
