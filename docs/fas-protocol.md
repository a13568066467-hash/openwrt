# FAS Level 1 协议

当前闭环使用 openNDS FAS level 1。云端 FAS 登录成功后，浏览器先跳到网关
`opennds_auth` 完成放行，再回跳 `/portal/` 用户中心并携带用户 token。

## 认证跳转

openNDS 302 到:
```
https://{fasremotefqdn}:{fasport}{faspath}?fas={base64}
```

base64 解码后为逗号分隔的 `key=value` 列表:
- clientip, clientmac, gatewayname, client_hid, gatewayaddress, authdir, originurl, clientif

## Level 1 放行回跳

### 请求

用户在云端 FAS 页面提交：

```
POST /fas?fas={base64}
Content-Type: application/x-www-form-urlencoded

username={username}&password={password}&action=login&fas={base64}
```

### 响应

成功后返回“已开通”页面，页面中的立即进入链接指向：

```
http://{gatewayaddress}{authdir}?tok={rhid}&redir={urlencode(portal_url)}&custom={custom_b64}
```

- `rhid = sha256(client_hid + FAS_KEY)`
- `redir` 指向 `USER_PORTAL_URL`，并带用户 JWT token
- `custom` 是 base64 JSON，包含 `user_id`、上下行速率与上下行配额

openNDS 放行后会请求 `/fas?status=authenticated&redir=...`，云端立即 302 到
`redir`，避免手机停留在 `FAS OK`。

## 已登录用户二次认证

用户中心会把用户 JWT 保存在浏览器 `localStorage.user_token`。手机再次打开
`http://home.me` 或充值后需要恢复上网时，FAS 登录页会自动提交：

```
POST /fas?fas={base64}
action=token
token={user_jwt}
```

云端验证 token、账号状态和剩余额度后，直接进入 level 1 放行回跳，不再要求用户
重复输入账号密码。若 token 失效、账号停用或额度不足，则不会放行；额度不足时跳转
`/portal/recharge?token=...`。

## authmon 兼容队列

代码仍写入 auth 队列并保留 authmon 查询接口，用于兼容 level 3/4 或后续回退；
当前 Newifi 实验室和固件默认不依赖 authmon 轮询完成放行。
写入新认证项时，云端会清理同一网关队列内超过 10 分钟的旧文件，避免 level 1
长期运行时 auth_queue 无限堆积。

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
- username, password, action (login|register|token)
- token (仅 action=token 时使用)
- fas (base64 encoded params)

成功后创建活跃会话、绑定当前 MAC 到当前账号，并进入 level 1 放行回跳。
