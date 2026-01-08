# Run baseline quality + security checks (CI-friendly)
# Usage: .\scripts\check.ps1

$ErrorActionPreference = "Stop"

Write-Host "Running pytest..."
pytest

Write-Host "Running ruff..."
ruff check .

Write-Host "Running bandit..."
bandit -r app -q

Write-Host "Running pip-audit..."
pip-audit

Write-Host "All checks passed."
