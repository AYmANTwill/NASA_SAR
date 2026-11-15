# Stops the processes started by start_demo.ps1 and whatever listens on 8000 and 5310.
foreach ($port in 8000, 5310) {
  Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { taskkill /PID $_.OwningProcess /T /F | Out-Null }
}
Write-Host "Demo stopped."
