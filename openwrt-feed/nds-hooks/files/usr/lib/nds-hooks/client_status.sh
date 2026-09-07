#!/bin/sh
# NewWiFI client status / Error511 — light theme matching user-web portal.
# Invoked as: statuspath <status|err511> <clientip> [b64query]

status=$1
clientip=$2
b64query=$3

do_ndsctl() {
	local timeout=4
	for tic in $(seq $timeout); do
		ndsstatus="ready"
		ndsctlout=$(eval ndsctl "$ndsctlcmd")
		for keyword in $ndsctlout; do
			if [ "$keyword" = "locked" ]; then
				ndsstatus="busy"
				sleep 1
				break
			fi
		done
		if [ "$ndsstatus" = "ready" ]; then
			break
		fi
	done
}

get_client_zone() {
	failcheck=$(echo "$clientif" | grep "get_client_interface")
	if [ -z "$failcheck" ]; then
		client_if=$(echo "$clientif" | awk '{printf $1}')
		client_meshnode=$(echo "$clientif" | awk '{printf $2}' | awk -F ':' '{print $1$2$3$4$5$6}')
		if [ -n "$client_meshnode" ]; then
			client_zone="Mesh $client_meshnode"
		else
			client_zone="$client_if"
		fi
	else
		client_zone=""
	fi
}

htmlentityencode() {
	entitylist="
 s/\"/\&quot;/g
 s/>/\&gt;/g
 s/</\&lt;/g
 s/%/\%/g
 s/'/\&#39;/g
 s/\`/\&#96;/g
 "
	local buffer="$1"
	for entity in $entitylist; do
		entityencoded=$(echo "$buffer" | sed "$entity")
		buffer=$entityencoded
	done
	entityencoded=$(echo "$buffer" | awk '{ gsub(/\$/, "\\$"); print }')
}

parse_variables() {
	# openNDS may emit "key=val,key=val" or "key=val, key=val"
	for var in $queryvarlist; do
		evalstr=$(echo "$query" | awk -F"$var=" '{print $2}' | awk -F',' '{print $1}')
		evalstr=$(echo "$evalstr" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
		evalstr=$(printf "${evalstr//%/\\x}")
		htmlentityencode "$evalstr"
		evalstr=$entityencoded
		if [ -z "$evalstr" ]; then
			continue
		fi
		eval $var=$(echo "\"$evalstr\"")
		evalstr=""
	done
	query=""
}

parse_parameters() {
	if [ "$status" = "status" ]; then
		ndsctlcmd="json $clientip"
		do_ndsctl
		if [ "$ndsstatus" = "ready" ]; then
			param_str=$ndsctlout
			for param in gatewayname gatewayaddress gatewayfqdn mac version ip client_type clientif session_start session_end \
				last_active token state upload_rate_limit_threshold download_rate_limit_threshold \
				upload_packet_rate upload_bucket_size download_packet_rate download_bucket_size \
				upload_quota download_quota upload_this_session download_this_session upload_session_avg download_session_avg
			do
				val=$(echo "$param_str" | grep "\"$param\":" | awk -F'"' '{printf "%s", $4}')
				if [ "$val" = "null" ]; then
					val="不限"
				fi
				if [ -z "$val" ]; then
					eval $param=$(echo "暂无")
				else
					eval $param=$(echo "\"$val\"")
				fi
			done
			gatewayname_dec=$(printf "${gatewayname//%/\\x}")
			brand=$(echo "$gatewayname_dec" | sed 's/ Node:.*//')
			[ -z "$brand" ] && brand="NewWiFI"
			htmlentityencode "$brand"
			gatewaynamehtml=$entityencoded
			get_client_zone
			sessionstart=$(date -d @"$session_start" 2>/dev/null || echo "$session_start")
			if [ "$session_end" = "不限" ] || [ "$session_end" = "Unlimited" ]; then
				sessionend="不限"
			else
				sessionend=$(date -d @"$session_end" 2>/dev/null || echo "$session_end")
			fi
			lastactive=$(date -d @"$last_active" 2>/dev/null || echo "$last_active")
		fi
	else
		mountpoint=$(/usr/lib/opennds/libopennds.sh tmpfs)
		. "$mountpoint/ndscids/ndsinfo"
		gatewaynamehtml="NewWiFI"
	fi
}

css_block() {
	cat <<'CSS'
:root{
  --brand:#1296db;--brand-dark:#0a6fad;--brand-light:#e8f6fd;
  --text:#1a1a2e;--muted:#8c9aab;--surface:#fff;--bg:#eef2f7;
  --radius:20px;--shadow:0 4px 24px rgba(18,150,219,.1);
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;min-height:100%;width:100%}
body{
  font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Segoe UI",sans-serif;
  background:var(--bg);color:var(--text);
  display:flex;justify-content:center;
  min-height:100vh;min-height:100dvh;
  -webkit-font-smoothing:antialiased;
}
.wrap{
  width:100%;max-width:430px;min-height:100vh;min-height:100dvh;
  display:flex;flex-direction:column;background:var(--bg);
  padding-bottom:calc(20px + env(safe-area-inset-bottom,0px));
}
.hero{
  position:relative;overflow:hidden;color:#fff;
  padding:calc(28px + env(safe-area-inset-top,0px)) 20px 40px;
  border-radius:0 0 28px 28px;
  background:linear-gradient(145deg,#1296db 0%,#0abde3 50%,#00b894 100%);
}
.hero__orb{position:absolute;border-radius:50%;background:rgba(255,255,255,.08);pointer-events:none}
.hero__orb--1{width:180px;height:180px;top:-60px;right:-40px}
.hero__orb--2{width:100px;height:100px;bottom:20px;left:-20px;background:rgba(255,255,255,.06)}
.hero__content{position:relative;z-index:1}
.hero__badge{
  display:inline-flex;align-items:center;justify-content:center;
  width:58px;height:58px;border-radius:18px;margin-bottom:14px;
  background:rgba(255,255,255,.2);border:1px solid rgba(255,255,255,.25);
  font-size:22px;font-weight:800;letter-spacing:.04em;
}
.hero__title{font-size:clamp(22px,5.5vw,26px);font-weight:800;margin:0 0 6px;letter-spacing:.01em}
.hero__sub{font-size:14px;opacity:.9;margin:0;line-height:1.5}
.body{padding:0 16px;margin-top:-22px;position:relative;z-index:2;flex:1}
.card{
  background:var(--surface);border-radius:var(--radius);padding:8px 16px 16px;
  box-shadow:var(--shadow);
}
.row{
  display:flex;justify-content:space-between;align-items:flex-start;gap:12px;
  padding:14px 2px;border-bottom:1px solid #eef2f7;
}
.row:last-of-type{border-bottom:none}
.k{color:var(--muted);font-size:13px;flex-shrink:0}.v{font-size:13px;font-weight:600;text-align:right;word-break:break-all;line-height:1.4}
.actions{display:flex;flex-direction:column;gap:10px;margin-top:14px}
.btn{
  width:100%;padding:14px 16px;border-radius:14px;border:none;
  font-size:16px;font-weight:700;cursor:pointer;
}
.btn-primary{color:#fff;background:linear-gradient(135deg,var(--brand),var(--brand-dark));box-shadow:0 8px 20px rgba(18,150,219,.28)}
.btn-ghost{background:#f3f6fa;color:var(--text)}
.hint{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:13px;margin:12px 0 0}
.hint input{width:18px;height:18px;accent-color:var(--brand)}
.msg{text-align:center;color:var(--muted);font-size:14px;padding:18px 8px;line-height:1.55}
form{margin:0}
@media (max-width:360px){
  .hero{padding-left:16px;padding-right:16px}
  .body{padding:0 12px}
  .v,.k{font-size:12px}
}
CSS
}

header() {
	echo "<!DOCTYPE html>
<html lang=\"zh-CN\"><head>
<meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover,maximum-scale=1\">
<title>${gatewaynamehtml}</title>
<style>
$(css_block)
</style>
</head><body>
<div class=\"wrap\">
<header class=\"hero\">
  <span class=\"hero__orb hero__orb--1\" aria-hidden=\"true\"></span>
  <span class=\"hero__orb hero__orb--2\" aria-hidden=\"true\"></span>
  <div class=\"hero__content\">
    <div class=\"hero__badge\">N</div>
    <h1 class=\"hero__title\">${gatewaynamehtml}</h1>
    <p class=\"hero__sub\">会话状态 · 本机上网信息</p>
  </div>
</header>
<main class=\"body\"><div class=\"card\">"
}

footer() {
	echo "</div></main></div></body></html>"
}

body() {
	if [ "$ndsstatus" = "busy" ]; then
		echo "<p class=\"msg\">系统繁忙，请点击「刷新」重试</p>
<div class=\"actions\"><button class=\"btn btn-primary\" type=\"button\" onclick=\"history.go(0);return true;\">刷新</button></div>"
		return
	fi

	if [ "$status" = "status" ]; then
		adv_checked=""
		[ "$advanced" = "checked" ] && adv_checked="checked"
		[ "$session_end" = "Unlimited" ] && sessionend="不限"
		[ "$download_rate_limit_threshold" = "Unlimited" ] && download_rate_limit_threshold="不限"
		[ "$upload_rate_limit_threshold" = "Unlimited" ] && upload_rate_limit_threshold="不限"
		[ "$download_quota" = "Unlimited" ] && download_quota="不限"
		[ "$upload_quota" = "Unlimited" ] && upload_quota="不限"

		echo "<div class=\"row\"><span class=\"k\">IP 地址</span><span class=\"v\">$ip</span></div>
<div class=\"row\"><span class=\"k\">MAC 地址</span><span class=\"v\">$mac</span></div>
<div class=\"row\"><span class=\"k\">会话开始</span><span class=\"v\">$sessionstart</span></div>
<div class=\"row\"><span class=\"k\">会话结束</span><span class=\"v\">$sessionend</span></div>
<div class=\"row\"><span class=\"k\">本次下载</span><span class=\"v\">$download_this_session KB</span></div>
<div class=\"row\"><span class=\"k\">本次上传</span><span class=\"v\">$upload_this_session KB</span></div>
<div class=\"row\"><span class=\"k\">平均下载</span><span class=\"v\">$download_session_avg Kb/s</span></div>
<div class=\"row\"><span class=\"k\">平均上传</span><span class=\"v\">$upload_session_avg Kb/s</span></div>"

		if [ "$advanced" = "checked" ]; then
			echo "<div class=\"row\"><span class=\"k\">客户端类型</span><span class=\"v\">$client_type</span></div>
<div class=\"row\"><span class=\"k\">接入接口</span><span class=\"v\">$clientif</span></div>
<div class=\"row\"><span class=\"k\">最近活跃</span><span class=\"v\">$lastactive</span></div>
<div class=\"row\"><span class=\"k\">下载限速</span><span class=\"v\">$download_rate_limit_threshold Kb/s</span></div>
<div class=\"row\"><span class=\"k\">上传限速</span><span class=\"v\">$upload_rate_limit_threshold Kb/s</span></div>
<div class=\"row\"><span class=\"k\">下载配额</span><span class=\"v\">$download_quota KB</span></div>
<div class=\"row\"><span class=\"k\">上传配额</span><span class=\"v\">$upload_quota KB</span></div>"
		fi

		echo "<form action=\"$url/\" method=\"get\">
<label class=\"hint\"><input type=\"checkbox\" name=\"advanced\" value=\"checked\" $adv_checked> 显示详细信息</label>
<div class=\"actions\">
<button class=\"btn btn-primary\" type=\"submit\">刷新</button>
</div>
</form>
<form action=\"$url/opennds_deny/\" method=\"get\" style=\"margin-top:10px\">
<button class=\"btn btn-ghost\" type=\"submit\">退出登录</button>
</form>"

	elif [ "$status" = "err511" ]; then
		echo "<p class=\"msg\">需要先完成上网认证后才能使用网络</p>
<form action=\"$url/login\" method=\"get\" target=\"_blank\">
<div class=\"actions\"><button class=\"btn btn-primary\" type=\"submit\">继续登录</button></div>
</form>"
	else
		exit 1
	fi
}

if [ -z "$clientip" ]; then
	exit 1
fi

if [ "$status" = "status" ] || [ "$status" = "err511" ]; then
	parse_parameters

	# Decode openNDS query first so gatewayfqdn/gatewayaddress are available
	# before we build refresh/login form actions.
	if [ -n "$b64query" ]; then
		ndsctlcmd="b64decode $b64query"
		do_ndsctl
		querystr=$ndsctlout
		querystr=${querystr:1:1024}
		queryvarlist=""
		for element in $querystr; do
			htmlentityencode "$element"
			element=$entityencoded
			varname=$(echo "$element" | awk -F'=' '$2!="" {printf "%s", $1}')
			queryvarlist="$queryvarlist $varname"
		done
		query=$querystr
		parse_variables
	fi

	if [ -z "$gatewayfqdn" ] || [ "$gatewayfqdn" = "disable" ] || [ "$gatewayfqdn" = "disabled" ] \
		|| [ "$gatewayfqdn" = "暂无" ] || [ "$gatewayfqdn" = "不限" ]; then
		if [ -n "$gatewayaddress" ] && [ "$gatewayaddress" != "暂无" ] && [ "$gatewayaddress" != "不限" ]; then
			url="http://$gatewayaddress"
		else
			url="http://home.me"
		fi
	else
		url="http://$gatewayfqdn"
	fi
	case "$url" in
		http://|http:///|http://暂无|http://暂无/|http://不限|http://不限/) url="http://home.me" ;;
	esac

	header
	body
	footer
	exit 0
fi

exit 1
