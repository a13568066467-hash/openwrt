# 部署与运维

## 云端部署

```bash
cd cloud
cp .env.example .env
docker compose up -d     # MySQL :3307, Redis :6380（映射端口，避免与本机冲突）
go run ./cmd/seed        # 创建默认管理员 admin/admin123
go run ./cmd/server
```

首次使用 Docker 前可预先拉取镜像：

```bash
docker pull mysql:8.0
docker pull redis:7-alpine
```

## 前端部署

```bash
cd admin-web && npm install && npm run build
cd user-web && npm install && npm run build
```

## OpenWrt 固件编译

```bash
# WSL2 Ubuntu 22.04
bash build/setup-wsl.sh

# 编译 x86_64
bash build/build.sh x86_64

# 其他架构
bash build/build.sh ramips_mt7621
bash build/build.sh ath79_generic
```

## 路由器配置

刷入固件后，修改 UCI:

```bash
uci set opennds.@opennds[0].fasremotefqdn='your-cloud-domain.com'
uci set opennds.@opennds[0].fasport='8443'
uci set nds-agent.main.cloud_url='https://your-cloud-domain.com:8443'
uci set nds-agent.main.device_id='dev-001'
uci set nds-agent.main.device_secret='your-secret'
uci commit
/etc/init.d/opennds restart
/etc/init.d/nds-agent restart
```

## 验收清单

- [ ] 手机连 WiFi 自动弹出登录页
- [ ] 注册后自动绑定 MAC 并上网
- [ ] 流量按上下行合计计量
- [ ] 额度耗尽 5 秒内断网
- [ ] 卡密充值后恢复上网
- [ ] 断网降级后恢复补报无重复

## 全链路测试

1. 启动 cloud + docker compose
2. QEMU 启动 x86_64 固件或真机刷入
3. 手机连接 NDS-WiFi SSID
4. 注册账户 → 验证上网
5. 管理面板调整流量/限速
6. 用户端卡密充值
7. 断开云端网络 → 验证本地降级 → 恢复补报
