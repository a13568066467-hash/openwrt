# 部署与运维

## 云端部署

```bash
cd cloud
cp .env.example .env
docker compose up -d     # MySQL :3307, Redis :6380（映射端口，避免与本机冲突）
go run ./cmd/seed        # 创建默认管理员 admin/admin123
go run ./cmd/server
```

> Go 进程启动时会自动读取 `cloud/.env`（或当前目录 `.env`），但显式环境变量优先级更高。
> `/health` 会返回当前数据库目标，实验室必须确认是 `tcp(localhost:3307)/nds_billing`，避免误连本机 `3306` 导致“明明账号存在却提示密码错误”。
> Windows 建议用 `.\scripts\start-lab.ps1` 启动，它会按实验室参数启动 Docker 与云端服务。

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

用户端构建产物由 cloud 的 `USER_WEB_DIR` 提供，以 `/portal/` 路径挂载。`.env.example` 里默认写的是 `../user-web/dist`；注意 Go 端 `config.Load()` 对 `USER_WEB_DIR` 的兜底值是**空字符串**（即不挂载 `/portal/`），所以必须经 `.env` 或环境变量显式传入。

用户中心首页、充值页、明细页会每 30 秒刷新一次 profile 余额；cloud 对 `/portal/` SPA 入口返回 `Cache-Control: no-store`，避免手机浏览器继续使用旧入口 JS。若现场仍看到旧余额，先刷新页面或清浏览器缓存，再看 30 秒后余额是否变化。

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

刷入固件后，修改 UCI。**`faskey` 必须与云端 `.env` 的 `FAS_KEY` 一致**，否则 level 1/4 的 `tok=sha256(hid+faskey)` 校验失败，登录后会被踢回认证页：

```bash
uci set opennds.@opennds[0].enabled='1'
uci set opennds.@opennds[0].gatewayinterface='br-guest'
uci set opennds.@opennds[0].fasremotefqdn='your-cloud-domain.com'
uci set opennds.@opennds[0].fasport='8443'
uci set opennds.@opennds[0].fas_secure_enabled='1'   # 当前链路使用 FAS level 1；必须配合相同 faskey
uci set opennds.@opennds[0].faskey='<与云端 FAS_KEY 相同的值>'
uci set opennds.@opennds[0].gatewayname='dev-001'
uci set opennds.@opennds[0].gatewayfqdn='home.me'
uci set opennds.@opennds[0].statuspath='/usr/lib/nds-hooks/client_status.sh'
uci set opennds.@opennds[0].binauth='/usr/lib/nds-hooks/binauth.sh'
uci set nds-agent.main.cloud_url='https://your-cloud-domain.com:8443'
uci set nds-agent.main.device_id='dev-001'
uci set nds-agent.main.device_secret='your-secret'
uci set nds-agent.main.report_interval='30'
uci commit
/etc/init.d/opennds restart
/etc/init.d/nds-agent restart
```

> 完整清单以 `scripts/configure-newifi-router.sh` 和固件内 `99-nds-profile` 为准；上面只列常改项。
> 生产服务器应使用真实域名与 HTTPS，并在构建/首配时写入 `NDS_CLOUD_SCHEME`、`NDS_CLOUD_HOST`、`NDS_CLOUD_PORT`、`NDS_DEVICE_ID`、`NDS_DEVICE_SECRET`。
> 实验室云端在 LAN 侧电脑 `192.168.1.125:8080` 且该电脑同时作为上游 NAT 时，才使用 `CLOUD_ZONE=lan`、guest-to-LAN forwarding 与 guest-to-LAN NAT；配置会先放行云端必要端口，再阻断 guest 直接访问 `192.168.1.0/24` LAN 私网。生产云端在 WAN/公网侧时不要开启这组 LAN 转发/NAT。
> `/api/v1/device/register` 默认关闭，只有明确设置 `ALLOW_DEVICE_REGISTER=1` 或配置一次性 `DEVICE_REGISTER_TOKEN` 时才允许注册设备，避免服务器上线后被任意设备写入。
> 批量刷固件不能共用实验室 `NewWiFI` / `nds-newifi-secret-16chars`。固件默认会用本机 MAC 生成 `NewWiFI-<mac>` 形式的设备 ID，并生成随机 `device_secret` 写入 `/etc/config/nds-agent`；openNDS `gatewayname` 也默认使用同一个唯一 `device_id`。服务器端必须按每台设备的实际 `device_id` / `device_secret` 建档，或在受控时间窗口用 `DEVICE_REGISTER_TOKEN` 完成注册。

单台路由刷完后可用下面命令从路由器读取实际身份并注册到云端：

```powershell
$env:NDS_DEVICE_REGISTER_TOKEN="<云端 DEVICE_REGISTER_TOKEN>"
python scripts/register-router-device.py --cloud-base https://your-cloud-domain.com:8443 --router-host 192.168.1.1
```

Newifi 实验室一键配置（LAN 口接电脑）：

```powershell
# 实验室用 192.168.1.125 直连云端（IP 方式，level 1）；生产改 faskey 并同步云端 FAS_KEY
$env:NDS_ROUTER_PASS="<路由器 root 密码>"
python scripts/apply-newifi-setup.py
python scripts/apply-home-me-status.py      # 下发 home.me 中文状态页
```

`apply-newifi-setup.py` 会优先读取当前环境的 `NDS_FAS_KEY`，未设置时读取 `cloud/.env` 的 `FAS_KEY` 并传给路由器；如果是全新路由且未显式设置 `NDS_DEVICE_SECRET`，路由端会生成随机密钥，之后必须用 `scripts/register-router-device.py` 注册到云端。

如果实验室路由的默认网关指向 PC `192.168.1.125`，手机认证后仍打不开外网，必须在 Windows 管理员 PowerShell 中开启 PC 转发/NAT：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\enable-pc-uplink.ps1
```

验收时应看到 `OpenWrtLab` NAT 存在，并且上联网卡和 `192.168.1.125` 所在以太网的 IPv4 `Forwarding` 均为 `Enabled`。生产部署不建议依赖 PC NAT；应让路由 WAN 直接接真实上游或把云端部署到公网/可达内网。

访客 WiFi 网段为 `192.168.100.0/24`（网关 `192.168.100.1`）；管理 LAN 可能是 `192.168.10.1`。手机状态页地址：`http://home.me`。

> `check-guest-dhcp.py` 与 `apply-guest-dhcp-heal.py` 默认先试 `NDS_ROUTER_HOST`，再试 `192.168.10.1`；若路由器仍在默认 `192.168.1.1`，请设 `NDS_ROUTER_HOST=192.168.1.1`。

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
python scripts/check-full-flow-health.py  # FULL_FLOW_HEALTH=PASS
```

`check-full-flow-health.py` 会用 `NDS_HEALTH_USERNAME` / `NDS_HEALTH_PASSWORD` 对 FAS 登录回跳做写入型探测，默认使用专用健康账号 `__nds_healthcheck__` 和虚拟 MAC，不会关闭正式测试账号的在线会话。脚本同时验证密码登录和已有用户 token 的二次认证回跳；主测试账号只用于用户 API 登录、用户中心 token 与历史计量验证。
探测结束后脚本会清理健康账号的虚拟 session、虚拟设备绑定和本次 auth_queue 文件，不污染后台在线统计。

5. **验收**：手机连 NDS-WiFi 拿 `192.168.100.x` → 登录放行 → `http://home.me` → 用户中心设备名。

说明：`192.168.10.1` 是实验室改过的管理地址；Breed / 全新 OpenWrt 默认是 `192.168.1.1`。验证时务必网线接 LAN，并避免 VPN 劫持探测结果。
- [ ] `cloud /health` 显示数据库为实验室 `3307` 或生产目标库
- [ ] `/api/v1/device/register` 未授权访问返回 403
- [ ] `nds-agent` 的 `cloud_url`、`device_id`、`device_secret`、`report_interval` 已写入
- [ ] 批量设备的 `device_id` / `device_secret` 每台唯一，openNDS `gatewayname` 与 `device_id` 一致，且已在服务器 routers 表注册
- [ ] 手机连 WiFi 自动弹出登录页
- [ ] 注册/登录后跳转网关放行并进入用户中心
- [ ] 手机已有用户中心登录态时，再打开 `http://home.me` 不再要求重复输入账密，可自动二次认证并进入用户中心
- [ ] 同一手机 MAC 重新登录到新账号后，「我的设备」只归属最新登录账号
- [ ] 流量按上下行合计计量
- [ ] 同一手机 MAC 换账号后，用户用量接口不显示旧账号 session 的历史记录
- [ ] `check-full-flow-health.py` 中 `live openNDS session metered` 与 `active session reflects live counters` 均为 OK
- [ ] 用户中心余额停留 30 秒后会自动刷新，不需要重新登录
- [ ] 额度耗尽 5 秒内断网
- [ ] 卡密充值后恢复上网
- [ ] 卡密充值成功后点击「重新认证上网」可重新经过 `home.me` 放行并回到用户中心
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
