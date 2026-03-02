# start_dev.ps1
# Dev: reload enabled, localhost only

Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path) | Out-Null
Set-Location .. | Out-Null

# Clear common vars so the env file is the source of truth
Remove-Item Env:ENV,Env:APP_ENV,Env:DATABASE_URL,Env:API_KEY_HASHES,Env:CORS_ORIGINS,Env:API_KEY_HEADER,Env:DISABLE_RATE_LIMIT -ErrorAction SilentlyContinue

# Load .env.dev into the current PowerShell process
Get-Content .env.dev | ForEach-Object {
  if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
  $k, $v = $_ -split '=', 2
  [Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim(), "Process")
}

$env:ENV = "dev"

python -m uvicorn app.main:app --host 127.0.0.1 --port 8004 --reload --log-level debug
