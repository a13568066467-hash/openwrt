# 本地开发环境一键启动（Windows PowerShell）
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Cloud = Join-Path $Root "cloud"
$EnvFile = Join-Path $Cloud ".env"

if (Test-Path $EnvFile) {
  Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
    $name, $value = $_ -split '=', 2
    Set-Item -Path "Env:$name" -Value $value
  }
}

Write-Host "=== 初始化数据库（需 cloud/.env 中 DATABASE_DSN 可连接） ==="
Push-Location $Cloud
go run ./cmd/seed
if ($LASTEXITCODE -ne 0) {
  Pop-Location
  throw "seed 失败：请先在 MySQL 创建 nds_billing 库和 nds 用户（见 cloud/.env.example）"
}
Pop-Location

Write-Host "=== 启动 Go 云端服务 :8080 ==="
Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command",
  "Set-Location '$Cloud'; Get-Content .env | ForEach-Object { if (`$_ -match '^\s*#|^\s*$') { return }; `$n,`$v = `$_ -split '=',2; Set-Item Env:`$n `$v }; go run ./cmd/server"
)

Write-Host "=== 启动管理面板 :3000 ==="
Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command",
  "Set-Location (Join-Path '$Root' 'admin-web'); & 'D:\Node\npm.cmd' run dev"
)

Write-Host "=== 启动用户端 :3001 ==="
Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command",
  "Set-Location (Join-Path '$Root' 'user-web'); & 'D:\Node\npm.cmd' run dev"
)

Write-Host ""
Write-Host "服务已启动："
Write-Host "  云端 API     http://localhost:8080"
Write-Host "  管理面板     http://localhost:3000  (admin / admin123)"
Write-Host "  用户端 H5    http://localhost:3001"
Write-Host "  MySQL        localhost:3306 (本机)"
Write-Host "  Redis        localhost:6379 (本机)"
