# 设备 API

Base URL: `/api/v1/device`，全部为 `POST`，请求与响应均为 JSON。

## 认证

设备凭据放在**请求体**里，不使用 HTTP 头：

```json
{ "device_id": "dev-001", "device_secret": "..." }
```

之所以不用 `X-Device-*` 头，是因为 agent 的备用传输 `uclient-fetch` 无法设置自定义请求头（精简固件里可能没有 curl）。`device_secret` 在云端以 bcrypt 哈希存储。

认证失败返回 `401`，请求体不是合法 JSON 返回 `400`。

## POST /register

注册新设备，当前不需要认证。`secret` 至少 16 字符。

```json
{ "name": "Router-01", "device_id": "dev-001", "secret": "至少16字符的密钥" }
```

响应 `{"ok": true, "id": 1}`；`device_id` 重复返回 `409`。

## POST /heartbeat

```json
{
  "device_id": "dev-001",
  "device_secret": "...",
  "uptime": 12345,
  "online": true,
  "agent_version": "1.0.0"
}
```

响应会带上该路由器待执行的指令，一次最多 50 条，取走即标记为已下发：

```json
{
  "ok": true,
  "commands": [
    { "action": "deauth", "mac": "aa:bb:cc:dd:ee:ff" },
    { "action": "set_quota", "mac": "aa:bb:cc:dd:ee:ff", "user_id": 1, "remaining_bytes": 104857600 }
  ]
}
```

指令只下发一次。agent 对两种指令都是幂等执行的，所以即使响应丢失，最坏结果也只是少执行一次踢下线——下一个周期本地额度判定会补上。

## POST /report

上报增量用量。`delta_bytes` 是自上次成功上报以来新增的**上下行合计**字节数。

```json
{
  "device_id": "dev-001",
  "device_secret": "...",
  "reports": [
    {
      "session_key": "dev-001:aa:bb:cc:dd:ee:ff:token123:1700000000",
      "seq": 1,
      "mac": "aa:bb:cc:dd:ee:ff",
      "ip": "192.168.100.101",
      "download_bytes": 786432,
      "upload_bytes": 262144,
      "delta_bytes": 1048576,
      "total_bytes": 1048576,
      "timestamp": 1700000060
    }
  ]
}
```

补报积压的历史数据时会带上 `"replay": true`。

响应：

```json
{
  "ok": true,
  "quota_updates": [
    { "mac": "aa:bb:cc:dd:ee:ff", "user_id": 1, "remaining_bytes": 103809024 }
  ],
  "commands": []
}
```

`quota_updates` 每个 MAC 只出现一次，即使同一批里有多条该 MAC 的增量。

## 幂等与计费语义

- **幂等键 `(session_key, seq)`**，由数据库唯一索引保证。重复上报直接跳过，不重复扣费。`seq` 在路由器侧持久化，重启后不会从头计数。
- **归属**：按「该路由器上该 MAC 的活跃会话」确定用户。一个 MAC 可能先后绑定过多个账户，所以不能只按 MAC 查绑定表；绑定表仅作为没有活跃会话时的兜底。
- **超额扣至零**：路由器每 60 秒才上报一次，最后一笔增量几乎必然超出余额。超出部分按实际可扣金额记账，余额落到 0，而不是整笔拒绝——否则这些已经跑掉的流量既不计费，也永远触发不了断网。余额归零时云端自动排入一条 `deauth` 指令。
