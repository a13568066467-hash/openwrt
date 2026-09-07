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

Windows 实验室也可：

```powershell
.\scripts\start-lab.ps1
```

## 前端部署

```bash
cd admin-web && npm install && npm run build
cd user-web && npm install && npm run build
```

用户端构建产物由 cloud 的 `USER_WEB_DIR`（默认 `../user-web/dist`）以 `/portal/` 提供。

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
uci set opennds.@opennds[0].gatewayname='NewWiFI'
uci set opennds.@opennds[0].gatewayfqdn='home.me'
uci set opennds.@opennds[0].statuspath='/usr/lib/nds-hooks/client_status.sh'
uci set nds-agent.main.cloud_url='https://your-cloud-domain.com:8443'
uci set nds-agent.main.device_id='dev-001'
uci set nds-agent.main.device_secret='your-secret'
uci commit
/etc/init.d/opennds restart
/etc/init.d/nds-agent restart
```

Newifi 实验室一键配置（LAN 口接电脑）：

```powershell
python scripts/apply-newifi-setup.py
python scripts/apply-home-me-status.py      # 下发 home.me 中文状态页
```

访客 WiFi 网段为 `192.168.100.0/24`（网关 `192.168.100.1`）；管理 LAN 可能是 `192.168.10.1`。手机状态页地址：`http://home.me`。

**接线（封装前必查）：** 电脑管理线必须插路由器 **LAN 口**，不要插 **WAN 口**。  
WAN 口只接上行光猫/上级路由；插错时有线网卡往往只有 `169.254.x`（链路 Up 但拿不到内网 IP），SSH/`check-guest-dhcp` 都会失败。

### 访客 WiFi 自动分配 IP（重点）

手机能连上 `NDS-WiFi` 却拿不到 IP，几乎总是这条链断了：

`br-guest` DOWN / `DEVICE_CLAIM_FAILED` → guest 无地址 → dnsmasq **不生成** `192.168.100` DHCP 池 → 手机无 IP。

固件侧已有三层自愈（`nds-profile`）：

1. 开机 `nds-late` 调用 `ensure-guest-dhcp.sh`
2. guest / `br-guest` hotplug 触发同一脚本
3. 每 30 秒 watchdog 复检（健康时 no-op）

实验室立刻下发并探测：

```powershell
python scripts/apply-guest-dhcp-heal.py
python scripts/check-guest-dhcp.py   # 期望 RESULT=PASS
```

仍失败时可手动：

```bash
/usr/lib/nds-profile/ensure-guest-dhcp.sh
# 或：
ip link set phy0-ap0 up; ip link set br-guest up
ifup guest
/etc/init.d/dnsmasq restart
/etc/init.d/opennds restart
```

## 定版封装清单

封装前按这个顺序做（固件目标：`ramips_mt7621` / Newifi D2）：

1. **代码定版**：合并本分支关键提交；`git push`；打 tag（如 `v1.0.0`）。
2. **重编固件**（当前 `build/images` 若早于最新 feed 改动则必须重编）：

```bash
# WSL
bash build/build.sh ramips_mt7621
# 产物：
# ~/owrt/openwrt/bin/targets/ramips/mt7621/*newifi-d2*sysupgrade.bin
# 可同步到 build/images/
```

3. **真机刷入**：Breed → 固件更新 → 选 sysupgrade（保留 Bootloader/EEPROM）→ 更新。
4. **实验室收尾配置**（刷完默认 LAN 仍是 `192.168.1.1`，不是 `192.168.10.1`）：

```powershell
# 电脑网线接 LAN，先关掉 Meta/代理
python scripts/apply-newifi-setup.py
python scripts/apply-guest-dhcp-heal.py
python scripts/apply-home-me-status.py
python scripts/check-guest-dhcp.py   # RESULT=PASS
```

5. **验收**：手机连 NDS-WiFi 拿 `192.168.100.x` → 登录放行 → `http://home.me` → 用户中心设备名。

说明：`192.168.10.1` 是实验室改过的管理地址；Breed / 全新 OpenWrt 默认是 `192.168.1.1`。验证时务必网线接 LAN，并避免 VPN 劫持探测结果。
- [ ] 手机连 WiFi 自动弹出登录页
- [ ] 注册/登录后跳转网关放行并进入用户中心
- [ ] 流量按上下行合计计量
- [ ] 额度耗尽 5 秒内断网
- [ ] 卡密充值后恢复上网
- [ ] 断网降级后恢复补报无重复
- [ ] `http://home.me` 显示 NewWiFI 中文状态页
- [ ] 用户中心「我的设备」能看到设备名称

## 全链路测试

1. 启动 cloud + docker compose
2. QEMU 启动 x86_64 固件或真机刷入
3. 手机连接 NDS-WiFi SSID
4. 注册账户 → 验证上网
5. 管理面板调整流量/限速
6. 用户端卡密充值
7. 断开云端网络 → 验证本地降级 → 恢复补报
