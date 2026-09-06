package fas

import (
	"fmt"
	"html"
	"net/http"

	"github.com/nds-billing/cloud/internal/database"
)

// Shared dark-portal shell. No external font CDN — captive clients only reach the lab cloud.
const portalCSS = `
:root{
  --bg0:#070B14;--bg1:#121A2E;--star:#7EC8FF;--signal:#3DDC97;
  --text:#E8EEF8;--muted:#8B9BB4;--danger:#FF6B7A;--glass:rgba(18,26,46,.72);
}
*{box-sizing:border-box}
html,body{margin:0;min-height:100%}
body{
  font-family:"Avenir Next","Segoe UI","PingFang SC","Hiragino Sans GB",sans-serif;
  color:var(--text);
  background:radial-gradient(1200px 600px at 20% -10%,#1a2744 0%,transparent 55%),
             radial-gradient(900px 500px at 100% 10%,#0d3d38 0%,transparent 50%),
             linear-gradient(165deg,var(--bg0),var(--bg1) 60%,#0a1220);
  min-height:100vh;display:flex;align-items:center;justify-content:center;
  padding:24px 16px;overflow-x:hidden;position:relative;
}
.stars,.stars:before,.stars:after{
  content:"";position:fixed;inset:0;pointer-events:none;
  background-image:
    radial-gradient(1.5px 1.5px at 12% 18%,rgba(126,200,255,.9),transparent),
    radial-gradient(1px 1px at 28% 72%,rgba(126,200,255,.55),transparent),
    radial-gradient(1.5px 1.5px at 61% 24%,rgba(61,220,151,.7),transparent),
    radial-gradient(1px 1px at 78% 58%,rgba(126,200,255,.5),transparent),
    radial-gradient(1.2px 1.2px at 88% 14%,rgba(255,255,255,.45),transparent),
    radial-gradient(1px 1px at 42% 40%,rgba(126,200,255,.4),transparent),
    radial-gradient(1px 1px at 8% 88%,rgba(61,220,151,.45),transparent),
    radial-gradient(1.4px 1.4px at 53% 86%,rgba(126,200,255,.55),transparent);
  animation:drift 28s linear infinite;opacity:.85;z-index:0;
}
.stars:before{animation-duration:42s;opacity:.5;transform:scale(1.2)}
.stars:after{animation-duration:56s;opacity:.35;transform:scale(1.45)}
@keyframes drift{from{transform:translateY(0)}to{transform:translateY(-40px)}}
@media (prefers-reduced-motion:reduce){
  .stars,.stars:before,.stars:after,.orb,.ring{animation:none!important}
}
.wrap{position:relative;z-index:1;width:100%;max-width:400px}
.brand{
  text-align:center;margin-bottom:22px;
  letter-spacing:.28em;font-weight:700;font-size:28px;
  background:linear-gradient(120deg,#fff 10%,var(--star) 45%,var(--signal) 90%);
  -webkit-background-clip:text;background-clip:text;color:transparent;
}
.tagline{text-align:center;color:var(--muted);font-size:14px;margin:-10px 0 22px;letter-spacing:.06em}
.card{
  background:var(--glass);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);
  border:1px solid rgba(126,200,255,.18);border-radius:22px;padding:26px 22px 22px;
  box-shadow:0 20px 50px rgba(0,0,0,.45),inset 0 1px 0 rgba(255,255,255,.06);
}
label{display:block;font-size:12px;color:var(--muted);margin:12px 0 6px;letter-spacing:.04em}
input{
  width:100%;padding:13px 14px;border-radius:12px;border:1px solid rgba(126,200,255,.2);
  background:rgba(7,11,20,.65);color:var(--text);font-size:16px;outline:none;
}
input:focus{border-color:var(--star);box-shadow:0 0 0 3px rgba(126,200,255,.15)}
input::placeholder{color:#5a6a82}
.btn{
  width:100%;margin-top:16px;padding:14px 16px;border:none;border-radius:14px;
  font-size:16px;font-weight:600;cursor:pointer;letter-spacing:.04em;
}
.btn-primary{
  color:#041018;
  background:linear-gradient(135deg,var(--signal),#2bb8ff);
  box-shadow:0 10px 28px rgba(61,220,151,.28);
}
.btn-primary:active{transform:translateY(1px)}
.btn-ghost{
  margin-top:10px;background:transparent;color:var(--muted);
  border:1px solid rgba(139,155,180,.35);
}
.error{
  background:rgba(255,107,122,.12);border:1px solid rgba(255,107,122,.35);
  color:var(--danger);border-radius:12px;padding:10px 12px;margin-bottom:12px;
  text-align:center;font-size:14px;
}
.hint{text-align:center;color:var(--muted);font-size:12px;margin-top:14px;line-height:1.5}
details.register{margin-top:14px}
details.register summary{
  list-style:none;cursor:pointer;text-align:center;color:var(--star);
  font-size:13px;padding:8px;letter-spacing:.03em;
}
details.register summary::-webkit-details-marker{display:none}
.center{text-align:center}
.orb{
  width:72px;height:72px;margin:8px auto 18px;border-radius:50%;
  background:radial-gradient(circle at 35% 30%,#fff,var(--star) 35%,var(--signal) 75%,transparent 76%);
  box-shadow:0 0 40px rgba(61,220,151,.45);animation:pulse 1.6s ease-in-out infinite;
}
@keyframes pulse{0%,100%{transform:scale(1);opacity:1}50%{transform:scale(1.06);opacity:.85}}
.ring{
  width:56px;height:56px;margin:0 auto 16px;border-radius:50%;
  border:3px solid rgba(126,200,255,.2);border-top-color:var(--signal);
  animation:spin .9s linear infinite;
}
@keyframes spin{to{transform:rotate(360deg)}}
h1{font-size:22px;font-weight:650;margin:0 0 8px;letter-spacing:.02em}
p.lead{margin:0;color:var(--muted);font-size:14px;line-height:1.55}
a.link{color:var(--star);text-decoration:none;font-size:13px}
a.link:hover{text-decoration:underline}
.mt{margin-top:18px}
`

func writeHTML(w http.ResponseWriter, body string) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	fmt.Fprint(w, body)
}

func (h *Handler) renderPortal(w http.ResponseWriter, _ *FASParams, fasEncoded, errMsg string) {
	errHTML := ""
	if errMsg != "" {
		errHTML = fmt.Sprintf(`<div class="error">%s</div>`, html.EscapeString(errMsg))
	}
	fas := html.EscapeString(fasEncoded)
	writeHTML(w, fmt.Sprintf(`<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>NDS · 上网认证</title>
<style>%s</style>
</head><body>
<div class="stars" aria-hidden="true"></div>
<div class="wrap">
  <div class="brand">NDS</div>
  <p class="tagline">连上，再出发</p>
  <div class="card">
    %s
    <form method="POST" autocomplete="on">
      <input type="hidden" name="fas" value="%s">
      <input type="hidden" name="action" value="login">
      <label for="login-user">账号</label>
      <input id="login-user" name="username" placeholder="手机号 / 用户名" required autocomplete="username">
      <label for="login-pass">密码</label>
      <input id="login-pass" name="password" type="password" placeholder="输入密码" required autocomplete="current-password">
      <button type="submit" class="btn btn-primary">登录上网</button>
    </form>
    <details class="register">
      <summary>没有账号？注册即送 100MB</summary>
      <form method="POST" style="margin-top:8px">
        <input type="hidden" name="fas" value="%s">
        <input type="hidden" name="action" value="register">
        <label for="reg-user">新账号</label>
        <input id="reg-user" name="username" placeholder="设置用户名" required autocomplete="username">
        <label for="reg-pass">设置密码</label>
        <input id="reg-pass" name="password" type="password" placeholder="至少 6 位" required autocomplete="new-password">
        <button type="submit" class="btn btn-ghost">创建账户</button>
      </form>
    </details>
    <p class="hint">认证通过后将自动开通本机上网，并进入用户中心</p>
  </div>
</div>
</body></html>`, portalCSS, errHTML, fas, fas))
}

func (h *Handler) renderSuccess(w http.ResponseWriter, r *http.Request, params *FASParams, user *database.User, rhid, customB64 string) {
	portal := h.portalURL(r, user, "/")
	redirect := portal
	if authURL := gatewayAuthURL(params, portal, rhid, customB64); authURL != "" {
		redirect = authURL
	}
	safe := html.EscapeString(redirect)
	writeHTML(w, fmt.Sprintf(`<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta http-equiv="refresh" content="3;url=%s">
<title>NDS · 已开通</title>
<style>%s</style>
</head><body>
<div class="stars" aria-hidden="true"></div>
<div class="wrap">
  <div class="brand">NDS</div>
  <div class="card center">
    <div class="orb" aria-hidden="true"></div>
    <div class="ring" aria-hidden="true"></div>
    <h1>已开通</h1>
    <p class="lead">网络正在放行，即将进入用户中心</p>
    <p class="hint mt"><a class="link" id="go" href="%s">立即进入</a></p>
  </div>
</div>
<script>
(function(){
  var u = document.getElementById('go').href;
  setTimeout(function(){ location.replace(u); }, 1200);
})();
</script>
</body></html>`, safe, portalCSS, safe))
}

func (h *Handler) renderQuotaExhausted(w http.ResponseWriter, r *http.Request, user *database.User) {
	redirect := h.portalURL(r, user, "/recharge")
	safe := html.EscapeString(redirect)
	writeHTML(w, fmt.Sprintf(`<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta http-equiv="refresh" content="2;url=%s">
<title>NDS · 流量已用尽</title>
<style>%s</style>
</head><body>
<div class="stars" aria-hidden="true"></div>
<div class="wrap">
  <div class="brand">NDS</div>
  <div class="card center">
    <h1>流量已用尽</h1>
    <p class="lead">本次无法开通上网，正在前往充值</p>
    <a class="btn btn-primary mt" style="display:inline-block;width:auto;min-width:160px;text-decoration:none" href="%s">去充值</a>
  </div>
</div>
<script>
setTimeout(function(){ location.replace(%q); }, 1600);
</script>
</body></html>`, safe, portalCSS, safe, redirect))
}
