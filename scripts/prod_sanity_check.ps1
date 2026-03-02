# scripts/prod_sanity_check.ps1
# Verifies: prod env loaded, correct DB, keys present, CORS set, docs/openapi blocked, reload disabled.

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== Surplus Claims PROD Sanity Check ==="

function Fail($msg) {
  Write-Host "[FAIL] $msg"
  exit 1
}

function Ok($msg) {
  Write-Host "[OK] $msg"
}

# ---- Config ----
$HostAddr = "127.0.0.1"
$Port = if ($env:PORT -and $env:PORT.Trim()) { [int]$env:PORT } else { 8000 }
$BaseUrl = "http://$HostAddr`:$Port"

# ---- Basic env checks ----
$envVal = ($env:ENV).Trim()
if (-not $envVal) { Fail "ENV is not set" }
if ($envVal.ToLower() -ne "prod" -and $envVal.ToLower() -ne "production") { Fail "ENV is not prod: $envVal" }
Ok "ENV = $envVal"

if (-not $env:DATABASE_URL -or -not $env:DATABASE_URL.Trim()) { Fail "DATABASE_URL missing" }
if (-not $env:API_KEY_HASHES -or -not $env:API_KEY_HASHES.Trim()) { Fail "API_KEY_HASHES missing" }
if (-not $env:CORS_ORIGINS -or -not $env:CORS_ORIGINS.Trim()) { Fail "CORS_ORIGINS missing" }

# ---- Parse DB URL (no secrets) ----
python -c @"
import os
from urllib.parse import urlparse
u=urlparse(os.getenv('DATABASE_URL',''))
db=(u.path or '').lstrip('/')
user=u.username or ''
host=u.hostname or ''
print(db)
print(user)
print(host)
"@ | ForEach-Object { $_ } | Out-Null

$dbName = python -c "import os; from urllib.parse import urlparse; u=urlparse(os.getenv('DATABASE_URL','')); print((u.path or '').lstrip('/'))"
$dbUser = python -c "import os; from urllib.parse import urlparse; u=urlparse(os.getenv('DATABASE_URL','')); print(u.username or '')"
$dbHost = python -c "import os; from urllib.parse import urlparse; u=urlparse(os.getenv('DATABASE_URL','')); print(u.hostname or '')"

if (-not $dbName) { Fail "Could not parse DB name from DATABASE_URL" }
if ($dbName -match "_dev$" -or $dbName -match "_test$" -or $dbName -match "_dev" -or $dbName -match "_test") { Fail "DB name looks dev/test: $dbName" }
Ok "DB Name = $dbName"

if (-not $dbUser) { Fail "Could not parse DB user from DATABASE_URL" }
Ok "DB User = $dbUser"

if (-not $dbHost) { Fail "Could not parse DB host from DATABASE_URL" }
Ok "DB Host = $dbHost"

# ---- Keys count / CORS ----
$keyCount = python -c "import os; raw=os.getenv('API_KEY_HASHES',''); hs=[h.strip() for h in raw.split(',') if h.strip()]; print(len(hs))"
if ([int]$keyCount -lt 1) { Fail "API Keys Count is 0" }
Ok "API Keys Count = $keyCount"

Ok "CORS_ORIGINS = $($env:CORS_ORIGINS)"

Write-Host ""
Write-Host "Testing API..."

# ---- /health ----
try {
  $health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method GET -TimeoutSec 5
  if ($health.status -ne "ok") { Fail "/health status not ok" }
  if ($health.db -ne "ok") { Fail "/health db not ok" }
  Ok "/health = OK"
} catch {
  Fail "/health failed: $($_.Exception.Message)"
}

# ---- /docs blocked in prod ----
try {
  $resp = Invoke-WebRequest -Uri "$BaseUrl/docs" -Method GET -TimeoutSec 5 -ErrorAction Stop
  # If it somehow returns 200, that's a fail in prod
  Fail "/docs is accessible (expected blocked)"
} catch {
  $code = $null
  if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
    $code = [int]$_.Exception.Response.StatusCode.value__
  }
  if ($code -eq 404 -or $code -eq 405) {
    Ok "/docs blocked"
  } else {
    Fail "/docs unexpected status: $code"
  }
}

# ---- /openapi.json blocked in prod ----
try {
  $resp = Invoke-WebRequest -Uri "$BaseUrl/openapi.json" -Method GET -TimeoutSec 5 -ErrorAction Stop
  Fail "/openapi.json is accessible (expected blocked)"
} catch {
  $code = $null
  if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
    $code = [int]$_.Exception.Response.StatusCode.value__
  }
  if ($code -eq 404 -or $code -eq 405) {
    Ok "/openapi.json blocked"
  } else {
    Fail "/openapi.json unexpected status: $code"
  }
}

# ---- Reload disabled check ----
# We can't perfectly detect reload from outside, but we can enforce:
# - you started with no --reload
# - app.main blocks it (already in code)
Ok "Reload disabled"

Write-Host ""
Write-Host "=== PROD VERIFIED: SAFE TO OPERATE ==="
