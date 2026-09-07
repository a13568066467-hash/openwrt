# Lab one-shot: Docker + cloud + admin/user frontends + router pair
# Saved as UTF-8 with BOM for Windows PowerShell 5.x Chinese safety.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Cloud = Join-Path $Root "cloud"
$EnvFile = Join-Path $Cloud ".env"
$CloudIP = if ($env:NDS_CLOUD_IP) { $env:NDS_CLOUD_IP } else { "192.168.1.125" }

function Import-DotEnv([string]$Path) {
  if (-not (Test-Path $Path)) { return }
  Get-Content -LiteralPath $Path -Encoding UTF8 | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
    $name, $value = $_ -split '=', 2
    Set-Item -Path "Env:$name" -Value $value
  }
}

function Test-Port([int]$Port) {
  $line = netstat -ano | Select-String ":$Port\s+.*LISTENING"
  return [bool]$line
}

function Ensure-Firewall([int]$Port) {
  netsh advfirewall firewall add rule name="NDS-$Port" dir=in action=allow protocol=TCP localport=$Port 2>$null | Out-Null
}

function Find-Npm {
  foreach ($c in @($env:NPM, "D:\Node\npm.cmd", "npm.cmd", "npm")) {
    if (-not $c) { continue }
    if (Test-Path $c) { return (Resolve-Path $c).Path }
    $cmd = Get-Command $c -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
  }
  throw "npm not found. Install Node or set NPM env var."
}

function Start-CloudServer {
  $logDir = Join-Path $Root "build\logs"
  New-Item -ItemType Directory -Force -Path $logDir | Out-Null
  $userWeb = (Join-Path $Root "user-web\dist")
  $launcher = Join-Path $logDir "start-cloud.ps1"
  $launcherBody = @"
`$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath '$Cloud'
if (Test-Path .env) {
  Get-Content -LiteralPath .env -Encoding UTF8 | ForEach-Object {
    if (`$_ -match '^\s*#' -or `$_ -match '^\s*`$') { return }
    `$n, `$v = `$_ -split '=', 2
    Set-Item -Path ("Env:" + `$n) -Value `$v
  }
}
`$env:USER_PORTAL_URL = 'http://${CloudIP}:8080/portal/'
`$env:USER_WEB_DIR = '$userWeb'
go run ./cmd/server
"@
  $utf8Bom = New-Object System.Text.UTF8Encoding $true
  [System.IO.File]::WriteAllText($launcher, $launcherBody, $utf8Bom)
  Start-Process powershell -ArgumentList @("-NoExit", "-File", $launcher)
}

Import-DotEnv $EnvFile
$env:USER_PORTAL_URL = "http://${CloudIP}:8080/portal/"
$env:USER_WEB_DIR = Join-Path $Root "user-web\dist"

Write-Host "=== 1/5 Docker MySQL / Redis ==="
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw "Start Docker Desktop first." }
Push-Location $Cloud
docker compose up -d
$ready = $false
for ($i = 0; $i -lt 45; $i++) {
  # mysqladmin prints a password warning on stderr; do not treat it as fatal.
  cmd /c "docker compose exec -T mysql mysqladmin ping -h localhost -unds -pnds123 1>nul 2>nul"
  if ($LASTEXITCODE -eq 0) { $ready = $true; break }
  Start-Sleep 2
}
if (-not $ready) { Pop-Location; throw "MySQL is not ready." }
Pop-Location

Write-Host "=== 2/5 Build user-web (cloud /portal/) ==="
$npm = Find-Npm
Push-Location (Join-Path $Root "user-web")
& $npm run build
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "user-web build failed." }
Pop-Location

Write-Host "=== 3/5 Cloud API :8080 / :8443 ==="
foreach ($p in 8080, 8443, 3000, 3001) { Ensure-Firewall $p }
if (-not (Test-Port 8080)) {
  Start-CloudServer
  for ($i = 0; $i -lt 40; $i++) {
    if (Test-Port 8080) { break }
    Start-Sleep 2
  }
}
if (-not (Test-Port 8080)) { throw "cloud is not listening on 8080." }

Write-Host "=== 4/5 Admin :3000 / User Vite :3001 ==="
if (-not (Test-Port 3000)) {
  Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location -LiteralPath (Join-Path '$Root' 'admin-web'); & '$npm' run dev"
  )
}
if (-not (Test-Port 3001)) {
  Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location -LiteralPath (Join-Path '$Root' 'user-web'); & '$npm' run dev"
  )
}
for ($i = 0; $i -lt 30; $i++) {
  if ((Test-Port 3000) -and (Test-Port 3001)) { break }
  Start-Sleep 2
}

Write-Host "=== 5/5 Pair router frontends / stabilize openNDS ==="
python (Join-Path $Root "scripts\pair-router-frontends.py")
if ($LASTEXITCODE -ne 0) {
  Write-Host "pair failed, trying stabilize..."
  python (Join-Path $Root "scripts\stabilize-opennds.py")
}

Write-Host ""
Write-Host "Ready:"
Write-Host "  Admin (PC)      http://${CloudIP}:3000   admin / admin123"
Write-Host "  User Vite       http://${CloudIP}:3001/portal/"
Write-Host "  User portal     http://${CloudIP}:8080/portal/   (after auth)"
Write-Host "  Captive entry   phone -> NDS-WiFi -> http://home.me"
Write-Host "  Cloud API       http://${CloudIP}:8080"
