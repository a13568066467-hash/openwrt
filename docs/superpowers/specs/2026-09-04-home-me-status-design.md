# NewWiFI 状态页 home.me

日期: 2026-09-04

## 变更

- `gatewayfqdn`: `status.client` → `home.me`
- `gatewayname`: `NDS-Billing-Gateway` → `NewWiFI`
- 自定义 `statuspath`: `/usr/lib/nds-hooks/client_status.sh`
- DHCP option 114 → `http://home.me`
- 中文标签；删除底部版权

## 下发

电脑连上路由器 LAN（`192.168.10.125`）后执行：

```powershell
python scripts/apply-home-me-status.py
```
