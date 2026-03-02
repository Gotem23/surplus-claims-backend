# start_prod.ps1
# Prod: no reload, localhost only (reverse proxy should expose 443 externally)

Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path) | Out-Null
Set-Location .. | Out-Null

Remove-Item Env:ENV,Env:APP_ENV,Env:DATABASE_URL,Env:API_KEY_HASHES,Env:CORS_ORIGINS,Env:API_KEY_HEADER,Env:DISABLE_RATE_LIMIT -ErrorAction SilentlyContinue

Get-Content .env.prod | ForEach-Object {
  if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
  $k, $v = $_ -split '=', 2
  [Environment]::SetEnvironmentVariable($k.Trim(), $v.Trim(), "Process")
}

$env:ENV = "prod"

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info
