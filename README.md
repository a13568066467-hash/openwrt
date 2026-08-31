# OpenWrt WiFi 认证计费系统

基于 OpenWrt 25.12.5 + openNDS (FAS level 4) 的 WiFi 认证与流量计费平台。

## 项目结构

```
openwrt-feed/     自研 OpenWrt feed（nds-agent, nds-hooks, nds-profile, opennds）
build/            构建脚本与 diffconfig
cloud/            Go 云端服务（FAS 门户、计费账本、设备管理）
admin-web/        React + TS 管理面板（PC）
user-web/         React + TS 用户端 H5（移动端）
docs/             架构与接口文档
```

## 快速开始

### 1. WSL2 构建环境

```bash
# 在 WSL2 Ubuntu 22.04 中执行
bash /mnt/d/Users/Documents/project/openwrt/build/setup-wsl.sh
```

### 2. 链接自研 feed 并编译

```bash
bash /mnt/d/Users/Documents/project/openwrt/build/build.sh x86_64
```

### 3. 云端服务

```bash
cd cloud
cp .env.example .env   # 首次：MySQL 3307、Redis 6380（Docker 映射端口）
docker compose up -d
go run ./cmd/seed        # 首次：创建默认管理员 admin/admin123
go run ./cmd/server
```

Windows 一键启动（需先启动 Docker Desktop）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-dev.ps1
```

### 4. 管理面板 / 用户端

```bash
cd admin-web && npm install && npm run dev
cd user-web && npm install && npm run dev
```

## 架构要点

- **认证**：openNDS FAS level 4，登录页托管在云端 Go 服务
- **计量**：nds-agent (ucode) 每 5 秒合计上下行流量，超额 deauth
- **上报**：60 秒增量上报，session_key + seq 幂等
- **断网降级**：本地额度缓存，恢复后补报

## 文档

- [架构设计](docs/architecture.md)
- [FAS 接口](docs/fas-protocol.md)
- [设备 API](docs/device-api.md)
