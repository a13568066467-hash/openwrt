package fas

import (
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/nds-billing/cloud/internal/config"
	"github.com/nds-billing/cloud/internal/database"
	"github.com/nds-billing/cloud/internal/ledger"
	"golang.org/x/crypto/bcrypt"
	"gorm.io/gorm"
)

type Handler struct {
	db     *gorm.DB
	cfg    *config.Config
	ledger *ledger.Service
}

func NewHandler(db *gorm.DB, cfg *config.Config) *Handler {
	return &Handler{db: db, cfg: cfg, ledger: ledger.New(db)}
}

type FASParams struct {
	ClientIP       string
	ClientMAC      string
	GatewayName    string
	ClientHID      string
	GatewayAddress string
	AuthDir        string
	OriginURL      string
	ClientIF       string
}

func (h *Handler) decodeFAS(encoded string) (*FASParams, error) {
	raw, err := base64.StdEncoding.DecodeString(encoded)
	if err != nil {
		return nil, err
	}
	params := make(map[string]string)
	for _, part := range strings.Split(string(raw), ", ") {
		kv := strings.SplitN(part, "=", 2)
		if len(kv) == 2 {
			params[kv[0]] = kv[1]
		}
	}
	return &FASParams{
		ClientIP:       params["clientip"],
		ClientMAC:      params["clientmac"],
		GatewayName:    params["gatewayname"],
		ClientHID:      params["client_hid"],
		GatewayAddress: params["gatewayaddress"],
		AuthDir:        params["authdir"],
		OriginURL:      params["originurl"],
		ClientIF:       params["clientif"],
	}, nil
}

func (h *Handler) gatewayHash(gatewayName string) string {
	sum := sha256.Sum256([]byte(url.QueryEscape(gatewayName)))
	return hex.EncodeToString(sum[:])
}

func (h *Handler) computeRHID(hid string) string {
	sum := sha256.Sum256([]byte(strings.TrimSpace(hid) + strings.TrimSpace(h.cfg.FASKey)))
	return hex.EncodeToString(sum[:])
}

func (h *Handler) authQueueDir(gatewayName string) string {
	return filepath.Join(h.cfg.AuthLogPath, h.gatewayHash(gatewayName))
}

func (h *Handler) HandleFAS(w http.ResponseWriter, r *http.Request) {
	if r.URL.Query().Get("auth_get") != "" {
		h.handleAuthGet(w, r)
		return
	}

	fasEncoded := r.URL.Query().Get("fas")
	if fasEncoded == "" {
		http.Error(w, "missing fas parameter", http.StatusBadRequest)
		return
	}

	params, err := h.decodeFAS(fasEncoded)
	if err != nil {
		http.Error(w, "invalid fas data", http.StatusBadRequest)
		return
	}

	if r.Method == http.MethodPost {
		h.handleLogin(w, r, params)
		return
	}

	h.renderPortal(w, params, fasEncoded, "")
}

func (h *Handler) handleAuthGet(w http.ResponseWriter, r *http.Request) {
	action := r.URL.Query().Get("auth_get")
	gatewayHash := r.URL.Query().Get("gatewayhash")
	payload := r.URL.Query().Get("payload")

	if payload == "none" {
		payload = ""
	}
	if payload != "" {
		decoded, err := base64.StdEncoding.DecodeString(payload)
		if err == nil {
			payload = string(decoded)
		}
	}

	queueDir := filepath.Join(h.cfg.AuthLogPath, gatewayHash)

	switch action {
	case "clear":
		os.RemoveAll(queueDir)
		w.WriteHeader(http.StatusOK)
		return
	case "view":
		if payload != "" && payload != "none" {
			// Ack: remove acknowledged rhid files
			parts := strings.Fields(payload)
			for i, p := range parts {
				if i == 0 && p == "*" {
					continue
				}
				os.Remove(filepath.Join(queueDir, p))
			}
			w.Write([]byte("ack"))
			return
		}

		entries, _ := os.ReadDir(queueDir)
		if len(entries) == 0 {
			w.WriteHeader(http.StatusOK)
			return
		}

		var parts []string
		for _, e := range entries {
			if e.IsDir() {
				continue
			}
			data, err := os.ReadFile(filepath.Join(queueDir, e.Name()))
			if err != nil {
				continue
			}
			parts = append(parts, url.QueryEscape(strings.TrimSpace(string(data))))
		}
		if len(parts) == 0 {
			w.WriteHeader(http.StatusOK)
			return
		}
		w.Write([]byte("* " + strings.Join(parts, " ")))
		return
	}

	w.WriteHeader(http.StatusOK)
}

func (h *Handler) handleLogin(w http.ResponseWriter, r *http.Request, params *FASParams) {
	username := r.FormValue("username")
	password := r.FormValue("password")
	action := r.FormValue("action")

	if action == "register" {
		h.handleRegister(w, r, params, username, password)
		return
	}

	var user database.User
	fasEncoded := r.FormValue("fas")
	if fasEncoded == "" {
		fasEncoded = r.URL.Query().Get("fas")
	}

	if err := h.db.Where("username = ?", username).First(&user).Error; err != nil {
		h.renderPortal(w, params, fasEncoded, "用户名或密码错误")
		return
	}

	if err := bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(password)); err != nil {
		h.renderPortal(w, params, fasEncoded, "用户名或密码错误")
		return
	}

	if user.Status != "active" {
		h.renderPortal(w, params, fasEncoded, "账户已被禁用")
		return
	}

	if user.QuotaRemainingBytes <= 0 {
		h.renderPortal(w, params, fasEncoded, "流量已用尽，请充值")
		return
	}

	h.authorizeClient(w, params, &user)
}

func (h *Handler) handleRegister(w http.ResponseWriter, r *http.Request, params *FASParams, username, password string) {
	fasEncoded := r.FormValue("fas")
	if fasEncoded == "" {
		fasEncoded = r.URL.Query().Get("fas")
	}

	if username == "" || password == "" {
		h.renderPortal(w, params, fasEncoded, "用户名和密码不能为空")
		return
	}

	var existing database.User
	if err := h.db.Where("username = ?", username).First(&existing).Error; err == nil {
		h.renderPortal(w, params, fasEncoded, "用户名已存在")
		return
	}

	hash, _ := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	expires := time.Now().AddDate(0, 0, h.cfg.QuotaExpiryDays)

	user := database.User{
		Username:            username,
		PasswordHash:        string(hash),
		QuotaRemainingBytes: 100 * 1024 * 1024, // 100MB trial
		UploadRateKbps:      h.cfg.DefaultUploadRate,
		DownloadRateKbps:    h.cfg.DefaultDownloadRate,
		QuotaExpiresAt:      &expires,
		Status:              "active",
	}
	if err := h.db.Create(&user).Error; err != nil {
		h.renderPortal(w, params, fasEncoded, "注册失败")
		return
	}

	h.ledger.TopUp(user.ID, 100*1024*1024, "register_trial", "注册赠送100MB", nil)
	h.bindMAC(user.ID, params.ClientMAC)
	h.authorizeClient(w, params, &user)
}

func (h *Handler) bindMAC(userID uint, mac string) {
	mac = strings.ToLower(mac)
	var device database.UserDevice
	err := h.db.Where("user_id = ? AND mac = ?", userID, mac).First(&device).Error
	now := time.Now()
	if err != nil {
		h.db.Create(&database.UserDevice{UserID: userID, MAC: mac, FirstSeen: now, LastSeen: now})
	} else {
		h.db.Model(&device).Update("last_seen", now)
	}
}

func (h *Handler) authorizeClient(w http.ResponseWriter, params *FASParams, user *database.User) {
	h.bindMAC(user.ID, params.ClientMAC)
	h.openSession(params, user)

	quotaC := h.computeAuthQuota(user.QuotaRemainingBytes)

	customData, _ := json.Marshal(map[string]interface{}{
		"user_id":         user.ID,
		"sessiontimeout":  0,
		"upload_rate":     user.UploadRateKbps,
		"download_rate":   user.DownloadRateKbps,
		"upload_quota":    quotaC / 1024,
		"download_quota":  quotaC / 1024,
	})
	customB64 := base64.StdEncoding.EncodeToString(customData)

	rhid := h.computeRHID(params.ClientHID)
	logLine := fmt.Sprintf("%s 0 %d %d %d %d %s",
		rhid, user.UploadRateKbps, user.DownloadRateKbps,
		quotaC/1024, quotaC/1024, customB64)

	queueDir := h.authQueueDir(params.GatewayName)
	os.MkdirAll(queueDir, 0700)
	os.WriteFile(filepath.Join(queueDir, rhid), []byte(logLine), 0600)

	h.renderSuccess(w, params)
}

// openSession records who is online where. Usage reports arrive later keyed
// only by router and MAC, so without this row the cloud cannot attribute
// traffic to an account. Enforcing one device per account happens here too, by
// closing the account's other sessions.
func (h *Handler) openSession(params *FASParams, user *database.User) {
	now := time.Now()
	mac := strings.ToLower(params.ClientMAC)

	h.db.Model(&database.Session{}).Where("user_id = ? AND active = ?", user.ID, true).
		Updates(map[string]any{"active": false, "ended_at": now})

	var router database.Router
	if err := h.db.Where("device_id = ?", params.GatewayName).First(&router).Error; err != nil {
		// An unregistered gateway can still authorise clients; their traffic
		// simply cannot be attributed until the router is registered.
		return
	}

	h.db.Create(&database.Session{
		SessionKey: fmt.Sprintf("%s:%s:%d", params.GatewayName, mac, now.UnixNano()),
		UserID:     user.ID,
		RouterID:   router.ID,
		MAC:        mac,
		IP:         params.ClientIP,
		StartedAt:  now,
		Active:     true,
	})
}

func (h *Handler) computeAuthQuota(remaining int64) int64 {
	minC := int64(20 * 1024 * 1024)
	tenPercent := remaining / 10
	if tenPercent < minC {
		return minC
	}
	if tenPercent > remaining {
		return remaining
	}
	return tenPercent
}

func (h *Handler) renderPortal(w http.ResponseWriter, params *FASParams, fasEncoded, errMsg string) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	errHTML := ""
	if errMsg != "" {
		errHTML = fmt.Sprintf(`<div class="error">%s</div>`, errMsg)
	}
	fmt.Fprintf(w, `<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>WiFi 认证</title>
<style>
body{font-family:sans-serif;max-width:400px;margin:40px auto;padding:20px;background:#f5f5f5}
.card{background:#fff;border-radius:12px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,.1)}
h2{text-align:center;color:#333;margin-bottom:20px}
input{width:100%%;padding:12px;margin:8px 0;border:1px solid #ddd;border-radius:8px;box-sizing:border-box;font-size:16px}
button{width:100%%;padding:14px;margin:8px 0;border:none;border-radius:8px;font-size:16px;cursor:pointer}
.btn-primary{background:#1677ff;color:#fff}
.btn-secondary{background:#f0f0f0;color:#333}
.error{color:#ff4d4f;text-align:center;margin-bottom:12px}
.tabs{display:flex;gap:8px;margin-bottom:16px}
.tab{flex:1;text-align:center;padding:8px;cursor:pointer;border-bottom:2px solid transparent}
.tab.active{border-color:#1677ff;color:#1677ff}
</style></head><body>
<div class="card">
<h2>WiFi 上网认证</h2>
%s
<form method="POST">
<input type="hidden" name="fas" value="%s">
<div id="login-form">
<input name="username" placeholder="用户名" required>
<input name="password" type="password" placeholder="密码" required>
<input type="hidden" name="action" value="login">
<button type="submit" class="btn-primary">登录上网</button>
</div>
</form>
<form method="POST" style="margin-top:12px">
<input type="hidden" name="fas" value="%s">
<input name="username" placeholder="新用户名" required>
<input name="password" type="password" placeholder="设置密码" required>
<input type="hidden" name="action" value="register">
<button type="submit" class="btn-secondary">注册账户</button>
</form>
<p style="text-align:center;color:#999;font-size:12px;margin-top:16px">注册即送 100MB 流量</p>
</div></body></html>`,
		errHTML,
		fasEncoded,
		fasEncoded,
	)
}

func (h *Handler) renderSuccess(w http.ResponseWriter, params *FASParams) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	redirect := params.OriginURL
	if redirect == "" {
		redirect = "http://www.google.com"
	}
	fmt.Fprintf(w, `<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta http-equiv="refresh" content="2;url=%s">
<title>认证成功</title></head><body style="text-align:center;padding:40px;font-family:sans-serif">
<h2>认证成功</h2><p>正在为您开通网络...</p></body></html>`, redirect)
}

func ParseInt64(s string) int64 {
	v, _ := strconv.ParseInt(s, 10, 64)
	return v
}
