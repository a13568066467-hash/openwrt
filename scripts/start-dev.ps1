# 本地开发环境一键启动（Windows PowerShell）
# 前置：先启动 Docker Desktop，并确保 mysql:8.0 / redis:7-alpine 镜像可拉取
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Cloud = Join-Path $Root "cloud"
$EnvFile = Join-Path $Cloud ".env"

function Import-DotEnv([string]$Path) {
  if (-not (Test-Path $Path)) { return }
  Get-Content $Path | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
    $name, $value = $_ -split '=', 2
    Set-Item -Path "Env:$name" -Value $value
  }
}

Import-DotEnv $EnvFile

Write-Host "=== 检查 Docker ==="
docker info *> $null
if ($LASTEXITCODE -ne 0) {
  throw "Docker 未运行，请先启动 Docker Desktop"
}

Write-Host "=== 启动 MySQL / Redis (Docker) ==="
Push-Location $Cloud
docker compose up -d
if ($LASTEXITCODE -ne 0) {
  Pop-Location
  throw "docker compose up 失败，请检查镜像是否已拉取完成"
}

Write-Host "=== 等待 MySQL 就绪 ==="
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
  docker compose exec -T mysql mysqladmin ping -h localhost -unds -pnds123 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) { $ready = $true; break }
  Start-Sleep -Seconds 2
}
if (-not $ready) {
  Pop-Location
  throw "MySQL 未在预期时间内就绪，请执行 docker compose logs mysql 查看日志"
}

Write-Host "=== 初始化数据库 ==="
go run ./cmd/seed
if ($LASTEXITCODE -ne 0) {
  Pop-Location
  throw "seed 失败，请检查 cloud/.env 中的 DATABASE_DSN（默认 localhost:3307）"
}
Pop-Location

$npmCmd = Get-Command npm -ErrorAction SilentlyContinue
$npm = if ($npmCmd) { $npmCmd.Source } else { "npm" }

Write-Host "=== 启动 Go 云端服务 :8080 ==="
Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command",
  "Set-Location '$Cloud'; Get-Content .env | ForEach-Object { if (`$_ -match '^\s*#|^\s*$') { return }; `$n,`$v = `$_ -split '=',2; Set-Item Env:`$n `$v }; go run ./cmd/server"
)

Write-Host "=== 启动管理面板 :3000 ==="
Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command",
  "Set-Location (Join-Path '$Root' 'admin-web'); & '$npm' run dev"
)

Write-Host "=== 启动用户端 :3001 ==="
Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command",
  "Set-Location (Join-Path '$Root' 'user-web'); & '$npm' run dev"
)

Write-Host ""
Write-Host "服务已启动："
Write-Host "  云端 API     http://localhost:8080"
Write-Host "  管理面板     http://localhost:3000  (admin / admin123)"
Write-Host "  用户端 H5    http://localhost:3001"
Write-Host "  MySQL        localhost:3307 (Docker)"
Write-Host "  Redis        localhost:6380 (Docker)"
