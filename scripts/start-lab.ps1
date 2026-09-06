# 实验室一键：Docker + cloud + 管理端/用户端 + 路由器联调
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Cloud = Join-Path $Root "cloud"
$EnvFile = Join-Path $Cloud ".env"
$CloudIP = if ($env:NDS_CLOUD_IP) { $env:NDS_CLOUD_IP } else { "192.168.1.125" }

function Import-DotEnv([string]$Path) {
  if (-not (Test-Path $Path)) { return }
  Get-Content $Path | ForEach-Object {
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
  throw "找不到 npm，请安装 Node 或设置 NPM 环境变量"
}

Import-DotEnv $EnvFile
$env:USER_PORTAL_URL = "http://${CloudIP}:8080/portal/"
$env:USER_WEB_DIR = Join-Path $Root "user-web\dist"

Write-Host "=== 1/5 Docker MySQL / Redis ==="
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw "请先启动 Docker Desktop" }
Push-Location $Cloud
docker compose up -d
$ready = $false
for ($i = 0; $i -lt 45; $i++) {
  docker compose exec -T mysql mysqladmin ping -h localhost -unds -pnds123 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) { $ready = $true; break }
  Start-Sleep 2
}
if (-not $ready) { Pop-Location; throw "MySQL 未就绪" }
Pop-Location

Write-Host "=== 2/5 构建用户端静态资源 (供 cloud /portal/) ==="
$npm = Find-Npm
Push-Location (Join-Path $Root "user-web")
& $npm run build
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "user-web build 失败" }
Pop-Location

Write-Host "=== 3/5 云端 API :8080 / :8443 ==="
foreach ($p in 8080, 8443, 3000, 3001) { Ensure-Firewall $p }
if (-not (Test-Port 8080)) {
  $logDir = Join-Path $Root "build\logs"
  New-Item -ItemType Directory -Force -Path $logDir | Out-Null
  Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$Cloud'; Get-Content .env | ForEach-Object { if (`$_ -match '^\s*#|^\s*$') { return }; `$n,`$v = `$_ -split '=',2; Set-Item Env:`$n `$v }; `$env:USER_PORTAL_URL='http://${CloudIP}:8080/portal/'; `$env:USER_WEB_DIR='$((Join-Path $Root 'user-web\dist') -replace '\\','\\')'; go run ./cmd/server"
  )
  for ($i = 0; $i -lt 40; $i++) {
    if (Test-Port 8080) { break }
    Start-Sleep 2
  }
}
if (-not (Test-Port 8080)) { throw "cloud 未在 8080 监听" }

Write-Host "=== 4/5 管理端 :3000 / 用户端 Vite :3001 ==="
if (-not (Test-Port 3000)) {
  Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location (Join-Path '$Root' 'admin-web'); & '$npm' run dev"
  )
}
if (-not (Test-Port 3001)) {
  Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location (Join-Path '$Root' 'user-web'); & '$npm' run dev"
  )
}
for ($i = 0; $i -lt 30; $i++) {
  if ((Test-Port 3000) -and (Test-Port 3001)) { break }
  Start-Sleep 2
}

Write-Host "=== 5/5 路由器联调 (开放 Guest→前端端口 + 稳定 openNDS) ==="
python (Join-Path $Root "scripts\pair-router-frontends.py")
if ($LASTEXITCODE -ne 0) {
  Write-Host "pair 失败，尝试 stabilize..."
  python (Join-Path $Root "scripts\stabilize-opennds.py")
}

Write-Host ""
Write-Host "全部就绪："
Write-Host "  管理端(电脑)   http://${CloudIP}:3000   admin / admin123"
Write-Host "  用户端(开发)   http://${CloudIP}:3001/portal/"
Write-Host "  用户中心(手机) http://${CloudIP}:8080/portal/   ← 认证后跳转"
Write-Host "  认证入口       手机连 NDS-WiFi → http://status.client"
Write-Host "  云端 API       http://${CloudIP}:8080"
