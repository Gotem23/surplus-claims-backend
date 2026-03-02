# stop_port.ps1
param(
  [Parameter(Mandatory=$true)]
  [int]$Port
)

$lines = netstat -ano | findstr (":" + $Port)

if (-not $lines) {
  Write-Host ("No process found listening on port " + $Port)
  exit 0
}

$pids = @()
foreach ($l in $lines) {
  $parts = ($l -split "\s+") | Where-Object { $_ -ne "" }
  $pid = $parts[-1]
  if ($pid -match '^\d+$') { $pids += [int]$pid }
}

$pids = $pids | Sort-Object -Unique

foreach ($pid in $pids) {
  Write-Host ("Killing PID " + $pid + " (port " + $Port + ")")
  taskkill /PID $pid /F | Out-Null
}

Write-Host "Done."
