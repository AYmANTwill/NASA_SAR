# Starts the backend (127.0.0.1:8000) and the v2 interface (127.0.0.1:5310). Stop with .\stop_demo.ps1
param([string]$DataDir = "D:\project\NASA_SAR\data")
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
if (-not (Test-Path $DataDir)) { throw "Data folder not found: $DataDir (use -DataDir)" }
$env:NISAR_DATA = $DataDir
Remove-Item Env:NISAR_LOS_SIGN_VERIFIED -ErrorAction SilentlyContinue
$logs = Join-Path $root "demo_logs"; New-Item -ItemType Directory -Force $logs | Out-Null

$api = Start-Process python -ArgumentList "-m","uvicorn","api:app","--host","127.0.0.1","--port","8000" `
  -WorkingDirectory (Join-Path $root "backend") -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput (Join-Path $logs "backend.out.log") -RedirectStandardError (Join-Path $logs "backend.err.log")
$ok = $false
for ($i = 0; $i -lt 60; $i++) {
  try { if ((Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing).StatusCode -eq 200) { $ok = $true; break } } catch { Start-Sleep 1 }
}
if (-not $ok) { throw "Backend did not answer /health in 60 s. See demo_logs\backend.err.log" }

$fe = Join-Path $root "frontend-v2"
if (-not (Test-Path (Join-Path $fe "node_modules"))) { Push-Location $fe; npm ci; Pop-Location }
$ui = Start-Process cmd.exe -ArgumentList "/c","npm run dev" -WorkingDirectory $fe -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput (Join-Path $logs "frontend.out.log") -RedirectStandardError (Join-Path $logs "frontend.err.log")
@($api.Id, $ui.Id) | Set-Content (Join-Path $logs "pids.txt")
for ($i = 0; $i -lt 30; $i++) { try { Invoke-WebRequest http://127.0.0.1:5310/ -UseBasicParsing | Out-Null; break } catch { Start-Sleep 1 } }
Write-Host "Open http://127.0.0.1:5310/en/  (fr, ar also). API: http://127.0.0.1:8000/api/cases"
