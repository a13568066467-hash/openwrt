# 系统架构

## 组件

| 组件 | 技术 | 职责 |
|------|------|------|
| openNDS | C + shell | Captive Portal 认证（FAS level 4） |
| nds-agent | ucode | 合计配额判定、用量上报、云端同步 |
| nds-hooks | shell | BinAuth 授权参数回填与事件记录 |
| nds-profile | UCI | 默认网络 / 防火墙 / openNDS 配置 |
| cloud | Go + MySQL + Redis | FAS 门户、计费账本、设备管理 |
| admin-web | React + Ant Design | PC 管理面板 |
| user-web | React + Ant Design Mobile | 移动端充值 |

## 数据流

1. 客户端连 WiFi → CPD 探测 → openNDS 302 跳转到云端 FAS
2. 用户登录/注册 → 云端写入 auth 队列并创建活跃会话 → authmon 轮询拉取 → openNDS 放行
3. nds-agent 每 5 秒采样 `ndsctl json`，按上下行合计判定，超额立即 deauth
4. nds-agent 每 60 秒上报增量 → 云端扣减额度 → 回传 `quota_updates` 与待执行指令

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

以下几条都是实测踩出来的，改动相关代码前请先看这里。

### 网络与认证

- **Guest 接口必须关闭 IPv6**。openNDS 完全不处理 IPv6，客户端一旦拿到可路由的 IPv6 地址就能绕过门户直接上网。因此 guest 网络关闭了 RA、DHCPv6、NDP 和前缀委派。
- **Guest 防火墙区域 `input=REJECT` 必须配合放行规则**。至少要放行 DHCP(67/udp)、DNS(53) 和 openNDS 网关端口(2050/tcp)，否则客户端连 IP 都拿不到。
- 限速使用 openNDS 内置实现（基于 nftables 报文速率，近似值，约 60Mbit/s 上限、30 秒移动平均）。

### 计费语义

- **openNDS 的配额是上下行独立的**，而产品卖的是合计流量，所以合计判定由 nds-agent 实现；下发给 openNDS 的上下行配额只作为兜底。
- **消费扣至零而非拒绝**。路由器每 60 秒才上报一次，最后一笔增量几乎必然超出余额；若整笔拒绝，这些已经跑掉的流量既不计费也永远触发不了断网。管理员手动扣减则相反，余额不足会直接失败。
- **流量归属按活跃会话而非 MAC 绑定表**。同一个 MAC 可能先后绑定过多个账户，只按 MAC 查会扣错人。
- **幂等键 `(session_key, seq)`** 由数据库唯一索引保证；`seq` 在路由器侧持久化，重启不重置。

### 断网降级

- 路由器缓存 `quota.json`，其中的 `remaining_bytes` 是云端已确认的余额。每个会话另记一个 baseline（云端已入账的字节数），断网期间用「当前会话用量 − baseline」推算实际剩余，因此断网时计量依然准确。
- 上报失败的增量写入 `backlog.jsonl`，恢复后按序补报，靠幂等键去重。

### 路由器侧实现约束

- **ucode 的 `for...in` 遍历数组得到的是「值」而非索引**，与 JavaScript 相反；遍历对象才得到键。
- **OpenWrt 25.12 的 ucode 不支持 `export function f() {}`**（该版本要求 export 语句以分号结尾）。统一在文件末尾写 `export { ... };`，新旧版本都兼容。
- **没有 `stringify()` 内置函数**，JSON 序列化用 `sprintf('%J', value)`。
- **`fs` 模块没有 `exec`**，执行命令用内置的 `system()` 或 `fs.popen()`。
- agent 不使用 uloop：只是定时轮询，用内置 `sleep()` 的普通循环即可，少一个依赖也更容易在主机上测试。
- **设备凭据放在 HTTP 请求体而非请求头**。备用传输 `uclient-fetch` 无法设置自定义请求头。
- **BinAuth 脚本内禁止调用查询守护进程的 ndsctl 命令**：openNDS 在脚本执行期间是阻塞的，会与自身的锁死锁。base64 解码因此用 busybox 而非 `ndsctl b64decode`。

### 构建约束

- **OpenWrt 25.12 使用 apk 而非 opkg**，首启脚本里不要调用包管理器；`dnsmasq-full` 这类替换在 `build/configs/*.config` 里于构建期选定。
- **feed 名称只能匹配 `\w+`**（见 `scripts/feeds` 第 58 行），不能含连字符，所以 feed 名是 `ndsbilling`；包名带连字符没问题。
