# 设备 API

Base URL: `/api/v1/device`

认证: Header `X-Device-ID` + `X-Device-Secret`

## POST /register

注册新设备 (无需认证)

```json
{
  "name": "Router-01",
  "device_id": "dev-001",
  "secret": "your-secret"
}
```

## POST /heartbeat

```json
{
  "device_id": "dev-001",
  "uptime": 12345,
  "online": true
}
```

响应:
```json
{
  "ok": true,
  "commands": [
    {"action": "deauth", "mac": "aa:bb:cc:dd:ee:ff"},
    {"action": "set_quota", "mac": "aa:bb:cc:dd:ee:ff", "user_id": 1, "remaining_bytes": 104857600}
  ]
}
```

## POST /report

```json
{
  "reports": [
    {
      "session_key": "dev-001:aa:bb:cc:dd:ee:ff:token123:1700000000",
      "seq": 1,
      "mac": "aa:bb:cc:dd:ee:ff",
      "ip": "192.168.100.101",
      "delta_bytes": 1048576,
      "total_bytes": 1048576,
      "timestamp": 1700000060
    }
  ]
}
```

响应:
```json
{
  "ok": true,
  "quota_updates": [
    {"mac": "aa:bb:cc:dd:ee:ff", "user_id": 1, "remaining_bytes": 103809024}
  ]
}
```

幂等键: `(session_key, seq)`
