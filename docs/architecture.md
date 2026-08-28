# 系统架构

## 组件

| 组件 | 技术 | 职责 |
|------|------|------|
| openNDS | C + shell | Captive Portal 认证 (FAS level 4) |
| nds-agent | ucode | 合计配额判定、用量上报、云端同步 |
| nds-hooks | shell | BinAuth 事件捕获 |
| nds-profile | UCI | 默认网络/openNDS 配置 |
| cloud | Go + MySQL + Redis | FAS 门户、计费账本、设备管理 |
| admin-web | React + Ant Design | PC 管理面板 |
| user-web | React + Ant Design Mobile | 移动端充值 |

## 数据流

1. 客户端连 WiFi → CPD 探测 → openNDS 302 到云端 FAS
2. 用户登录/注册 → 云端写入 auth 队列 → authmon 轮询拉取 → ndsctl auth
3. nds-agent 每 5 秒合计计量 → 超额 deauth
4. nds-agent 每 60 秒上报增量 → 云端扣减额度 → 回传 quota_updates

## 部署拓扑

```
Internet
    │
    ├── Cloud Server (Go :8080/:8443)
    │       ├── MySQL
    │       └── Redis
    │
    └── OpenWrt Router(s)
            ├── openNDS (guest WiFi)
            └── nds-agent → HTTPS → Cloud
```

## 关键约束

- Guest 接口必须关闭 IPv6
- openNDS 配额为上下行独立，合计判定由 nds-agent 实现
- 限速使用 openNDS 内置（近似，60Mbit/s 上限）
- 断网降级：本地 quota.json 缓存
