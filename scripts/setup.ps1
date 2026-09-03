# Bootstrap a local development environment (PowerShell).
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

Write-Host "==> Copying environment templates (skipping any that already exist)"
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
if (-not (Test-Path "backend/.env")) { Copy-Item "backend/.env.example" "backend/.env" }
if (-not (Test-Path "frontend/.env.local")) { Copy-Item "frontend/.env.example" "frontend/.env.local" }

Write-Host "==> Installing root + frontend npm workspace dependencies"
npm install

Write-Host "==> Creating backend virtualenv and installing dependencies"
Set-Location "$RootDir/backend"
py -m venv .venv
& ".venv/Scripts/pip.exe" install --upgrade pip
& ".venv/Scripts/pip.exe" install -e ".[dev]"
Set-Location $RootDir

Write-Host "==> Installing pre-commit hooks"
try {
    pre-commit install
} catch {
    Write-Host "pre-commit not found on PATH — install it manually: pip install pre-commit"
}

Write-Host ""
Write-Host "Setup complete. Next steps:"
Write-Host "  docker compose up -d          # start Postgres/Redis/MinIO/backend/frontend"
Write-Host "  cd backend; .venv/Scripts/python -m alembic upgrade head   # if running the backend outside Docker"
