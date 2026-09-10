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

	"github.com/nds-billing/cloud/internal/auth"
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
	jwt    *auth.JWTService
}

func NewHandler(db *gorm.DB, cfg *config.Config, jwt *auth.JWTService) *Handler {
	return &Handler{db: db, cfg: cfg, ledger: ledger.New(db), jwt: jwt}
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
	Tok            string
}

func (h *Handler) decodeFAS(encoded string) (*FASParams, error) {
	raw, err := base64.StdEncoding.DecodeString(encoded)
	if err != nil {
		return nil, err
	}
	params := parseFASPairs(string(raw))
	return &FASParams{
		ClientIP:       params["clientip"],
		ClientMAC:      params["clientmac"],
		GatewayName:    params["gatewayname"],
		ClientHID:      firstNonEmpty(params["client_hid"], params["hid"]),
		GatewayAddress: params["gatewayaddress"],
		AuthDir:        params["authdir"],
		OriginURL:      params["originurl"],
		ClientIF:       params["clientif"],
		Tok:            firstNonEmpty(params["tok"], params["token"]),
	}, nil
}

func parseFASPairs(raw string) map[string]string {
	params := make(map[string]string)
	for _, part := range strings.Split(raw, ",") {
		part = strings.TrimSpace(part)
		kv := strings.SplitN(part, "=", 2)
		if len(kv) == 2 {
			params[strings.TrimSpace(kv[0])] = strings.TrimSpace(kv[1])
		}
	}
	return params
}

func firstNonEmpty(values ...string) string {
	for _, v := range values {
		if v != "" {
			return v
		}
	}
	return ""
}

func (h *Handler) gatewayHash(gatewayName string) string {
	// openNDS authmon hashes the already-urlencoded gatewayname string.
	// FAS payloads arrive pre-encoded (e.g. "Name%20Node%3a..."); hashing
	// again with QueryEscape double-encodes and authmon never finds the queue.
	name := gatewayName
	if !strings.Contains(name, "%") {
		name = url.QueryEscape(name)
		name = strings.ReplaceAll(name, "%3A", "%3a")
		name = strings.ReplaceAll(name, "%2F", "%2f")
	}
	sum := sha256.Sum256([]byte(name))
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
		if r.URL.Query().Get("status") == "authenticated" {
			if redir := strings.TrimSpace(r.URL.Query().Get("redir")); redir != "" {
				http.Redirect(w, r, redir, http.StatusFound)
				return
			}
		}
		// openNDS probes the FAS URL at startup. A 400 here makes the
		// daemon treat the portal as down and refuse to stay running.
		if r.Method != http.MethodPost {
			w.Header().Set("Content-Type", "text/plain; charset=utf-8")
			w.WriteHeader(http.StatusOK)
			w.Write([]byte("FAS OK\n"))
			return
		}
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
	if action == "token" {
		h.handleTokenLogin(w, r, params)
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
		// Do not grant network access; send the user to the recharge portal.
		h.renderQuotaExhausted(w, r, &user)
		return
	}

	h.authorizeClient(w, r, params, &user)
}

func (h *Handler) handleTokenLogin(w http.ResponseWriter, r *http.Request, params *FASParams) {
	fasEncoded := r.FormValue("fas")
	if fasEncoded == "" {
		fasEncoded = r.URL.Query().Get("fas")
	}

	token := strings.TrimSpace(r.FormValue("token"))
	if token == "" || h.jwt == nil {
		h.renderPortal(w, params, fasEncoded, "登录已过期，请重新输入账号密码")
		return
	}
	claims, err := h.jwt.Parse(token)
	if err != nil || claims.Role != "user" || claims.ID == 0 {
		h.renderPortal(w, params, fasEncoded, "登录已过期，请重新输入账号密码")
		return
	}

	var user database.User
	if err := h.db.First(&user, claims.ID).Error; err != nil {
		h.renderPortal(w, params, fasEncoded, "登录已过期，请重新输入账号密码")
		return
	}
	if user.Status != "active" {
		h.renderPortal(w, params, fasEncoded, "账户已被禁用")
		return
	}
	if user.QuotaRemainingBytes <= 0 {
		h.renderQuotaExhausted(w, r, &user)
		return
	}

	h.authorizeClient(w, r, params, &user)
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
	h.authorizeClient(w, r, params, &user)
}

func (h *Handler) bindMAC(userID uint, mac string) {
	mac = strings.ToLower(mac)
	if mac == "" {
		return
	}

	// A handset can be reused with a different account. Keep ownership
	// deterministic so "My devices" and usage views do not leak the same MAC
	// across old accounts after a later login.
	h.db.Where("mac = ? AND user_id <> ?", mac, userID).Delete(&database.UserDevice{})

	now := time.Now()
	result := h.db.Model(&database.UserDevice{}).
		Where("user_id = ? AND mac = ?", userID, mac).
		Update("last_seen", now)
	if result.Error != nil {
		return
	}
	if result.RowsAffected == 0 {
		h.db.Create(&database.UserDevice{UserID: userID, MAC: mac, FirstSeen: now, LastSeen: now})
	}
}

func (h *Handler) authorizeClient(w http.ResponseWriter, r *http.Request, params *FASParams, user *database.User) {
	h.bindMAC(user.ID, params.ClientMAC)
	h.openSession(params, user)

	quotaC := h.computeAuthQuota(user.QuotaRemainingBytes)

	customData, _ := json.Marshal(map[string]interface{}{
		"user_id":        user.ID,
		"sessiontimeout": 0,
		"upload_rate":    user.UploadRateKbps,
		"download_rate":  user.DownloadRateKbps,
		"upload_quota":   quotaC / 1024,
		"download_quota": quotaC / 1024,
	})
	customB64 := base64.StdEncoding.EncodeToString(customData)

	rhid := h.computeRHID(params.ClientHID)
	logLine := fmt.Sprintf("%s 0 %d %d %d %d %s",
		rhid, user.UploadRateKbps, user.DownloadRateKbps,
		quotaC/1024, quotaC/1024, customB64)

	queueDir := h.authQueueDir(params.GatewayName)
	os.MkdirAll(queueDir, 0700)
	h.pruneAuthQueue(queueDir, 10*time.Minute)
	os.WriteFile(filepath.Join(queueDir, rhid), []byte(logLine), 0600)

	// Level 1 FAS: browser must hit gateway authdir with tok=rhid.
	// Auth queue is still written for level 3/4 authmon.
	h.renderSuccess(w, r, params, user, rhid, customB64)
}

func (h *Handler) pruneAuthQueue(queueDir string, maxAge time.Duration) {
	entries, err := os.ReadDir(queueDir)
	if err != nil {
		return
	}

	cutoff := time.Now().Add(-maxAge)
	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}
		info, err := entry.Info()
		if err != nil {
			continue
		}
		if info.ModTime().Before(cutoff) {
			os.Remove(filepath.Join(queueDir, entry.Name()))
		}
	}
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
	deviceID := params.GatewayName
	if decoded, err := url.QueryUnescape(deviceID); err == nil {
		deviceID = decoded
	}
	// openNDS appends " Node:<mac>" to gatewayname; lab device_id is the base name.
	if base, _, ok := strings.Cut(deviceID, " Node:"); ok {
		deviceID = strings.TrimSpace(base)
	}
	if err := h.db.Where("device_id = ?", deviceID).First(&router).Error; err != nil {
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

func (h *Handler) portalURL(r *http.Request, user *database.User, portalPath string) string {
	base := strings.TrimSpace(h.cfg.UserPortalURL)
	if base == "" {
		scheme := "http"
		if r.TLS != nil {
			scheme = "https"
		}
		host := r.Host
		if host == "" {
			host = "127.0.0.1:8080"
		}
		base = scheme + "://" + host + "/portal/"
	}
	if !strings.HasSuffix(base, "/") && !strings.Contains(base, "?") {
		base += "/"
	}

	u, err := url.Parse(base)
	if err != nil {
		u = &url.URL{Scheme: "http", Host: "127.0.0.1:8080", Path: "/portal/"}
	}
	if portalPath == "" {
		portalPath = "/"
	}
	if !strings.HasPrefix(portalPath, "/") {
		portalPath = "/" + portalPath
	}
	// Keep /portal basename and append app path (e.g. /recharge).
	root := strings.TrimSuffix(u.Path, "/")
	if root == "" {
		root = "/portal"
	}
	u.Path = root + portalPath

	if h.jwt != nil && user != nil {
		if token, err := h.jwt.Generate(user.ID, "user"); err == nil && token != "" {
			q := u.Query()
			q.Set("token", token)
			u.RawQuery = q.Encode()
		}
	}
	return u.String()
}

func gatewayAuthURL(params *FASParams, redir, rhid, customB64 string) string {
	if params == nil || params.GatewayAddress == "" {
		return ""
	}
	// Level 0 sends the client token; level 1/4 send rhid=sha256(hid+faskey).
	tok := firstNonEmpty(params.Tok, rhid)
	if tok == "" {
		return ""
	}
	authdir := params.AuthDir
	if authdir == "" {
		authdir = "/opennds_auth/"
	}
	if !strings.HasPrefix(authdir, "/") {
		authdir = "/" + authdir
	}
	if !strings.HasSuffix(authdir, "/") {
		authdir += "/"
	}
	raw := "http://" + params.GatewayAddress + authdir
	u, err := url.Parse(raw)
	if err != nil {
		return ""
	}
	q := u.Query()
	q.Set("tok", tok)
	q.Set("redir", redir)
	if customB64 != "" {
		q.Set("custom", customB64)
	}
	u.RawQuery = q.Encode()
	return u.String()
}

func ParseInt64(s string) int64 {
	v, _ := strconv.ParseInt(s, 10, 64)
	return v
}
