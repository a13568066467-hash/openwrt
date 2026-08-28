# FAS Level 4 协议

基于 openNDS authmon 与远程 FAS 的交互协议。

## 认证跳转

openNDS 302 到:
```
https://{fasremotefqdn}:{fasport}{faspath}?fas={base64}
```

base64 解码后为逗号分隔的 `key=value` 列表:
- clientip, clientmac, gatewayname, client_hid, gatewayaddress, authdir, originurl, clientif

## authmon 轮询

### 请求

```
GET {fas_url}?auth_get={action}&gatewayhash={sha256(urlencode(gatewayname))}&payload={b64encode(payload)}
User-Agent: openNDS(authmon;NDS:{version};)
```

| action | payload | 说明 |
|--------|---------|------|
| clear | none | 启动时清理队列 |
| view | none | 拉取待认证列表 |
| view | `* {rhid1} {rhid2}` | 确认已认证 |

### 响应

**有待认证客户端:**
```
* {urlencode(entry1)} {urlencode(entry2)} ...
```

每条 entry 格式 (空格分隔):
```
{rhid} {sessionlength} {uploadrate} {downloadrate} {uploadquota} {downloadquota} {custom_b64}
```

- rhid = sha256(hid + fas_key)
- sessionlength: 分钟 (0=无限)
- uploadrate/downloadrate: kbit/s
- uploadquota/downloadquota: kB
- custom: base64 JSON

**确认 ack:** 返回字面量 `ack`

**无待认证:** 空 body

## 登录/注册

POST `/fas` with form fields:
- username, password, action (login|register)
- fas (base64 encoded params)

成功后写入 auth 队列，等待 authmon 拉取。
