package fas

import (
	"encoding/base64"
	"html"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/glebarez/sqlite"
	"github.com/nds-billing/cloud/internal/auth"
	"github.com/nds-billing/cloud/internal/config"
	"github.com/nds-billing/cloud/internal/database"
	"golang.org/x/crypto/bcrypt"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

func TestDecodeFASCommaVariants(t *testing.T) {
	raw := "clientip=192.168.100.10, clientmac=aa:bb:cc:dd:ee:ff,tok=abc123,authdir=/opennds_auth/,gatewayaddress=192.168.100.1:2050,originurl=http://status.client/"
	encoded := base64.StdEncoding.EncodeToString([]byte(raw))
	params, err := (&Handler{}).decodeFAS(encoded)
	if err != nil {
		t.Fatal(err)
	}
	if params.Tok != "abc123" {
		t.Fatalf("tok=%q", params.Tok)
	}
	if params.GatewayAddress != "192.168.100.1:2050" {
		t.Fatalf("gateway=%q", params.GatewayAddress)
	}
	if params.OriginURL != "http://status.client/" {
		t.Fatalf("origin=%q", params.OriginURL)
	}
}

func TestGatewayAuthURL(t *testing.T) {
	got := gatewayAuthURL(&FASParams{
		Tok:            "tok1",
		GatewayAddress: "192.168.100.1:2050",
		AuthDir:        "/opennds_auth/",
	}, "http://192.168.1.125:8080/portal/?token=abc", "", "")
	if !strings.Contains(got, "tok=tok1") || !strings.Contains(got, "redir=") {
		t.Fatalf("auth url=%s", got)
	}
}

func TestGatewayAuthURLLevel1UsesRHID(t *testing.T) {
	got := gatewayAuthURL(&FASParams{
		GatewayAddress: "192.168.100.1:2050",
	}, "http://192.168.10.125:8080/portal/", "rhiddeadbeef", "Y3VzdG9t")
	if !strings.Contains(got, "tok=rhiddeadbeef") {
		t.Fatalf("expected rhid tok, got %s", got)
	}
	if !strings.Contains(got, "/opennds_auth/") {
		t.Fatalf("expected default authdir, got %s", got)
	}
	if !strings.Contains(got, "custom=Y3VzdG9t") {
		t.Fatalf("expected custom, got %s", got)
	}
}

func TestGatewayHashUsesPreencodedName(t *testing.T) {
	h := &Handler{}
	encoded := "NDS-Billing-Gateway%20Node%3a2076934462fe%20"
	got := h.gatewayHash(encoded)
	// Must NOT double-encode; sha256 of the string as openNDS sends it.
	want := "2b1ff6f100a690f0360fd48d8e375ac1db46a5d7191aaa3f827271d818646319"
	if got != want {
		t.Fatalf("gatewayHash=%s want=%s", got, want)
	}
}

func TestFASProbeOK(t *testing.T) {
	h := NewHandler(nil, &config.Config{}, nil)
	req := httptest.NewRequest(http.MethodGet, "/fas", nil)
	rec := httptest.NewRecorder()
	h.HandleFAS(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("status=%d body=%s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), "FAS OK") {
		t.Fatalf("body=%s", rec.Body.String())
	}
}

func TestLoginZeroQuotaRedirectsToRecharge(t *testing.T) {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{Logger: logger.Default.LogMode(logger.Silent)})
	if err != nil {
		t.Fatal(err)
	}
	if err := database.Migrate(db); err != nil {
		t.Fatal(err)
	}
	hash, _ := bcrypt.GenerateFromPassword([]byte("secret"), bcrypt.MinCost)
	user := database.User{
		Username:            "broke",
		PasswordHash:        string(hash),
		Status:              "active",
		QuotaRemainingBytes: 0,
	}
	if err := db.Create(&user).Error; err != nil {
		t.Fatal(err)
	}

	cfg := &config.Config{
		JWTSecret:     "test-jwt",
		UserPortalURL: "http://192.168.1.125:8080/portal/",
		AuthLogPath:   t.TempDir(),
	}
	h := NewHandler(db, cfg, auth.NewJWTService(cfg.JWTSecret))

	fasRaw := "clientip=192.168.100.10,clientmac=aa:bb:cc:dd:ee:ff,gatewayname=NDS-Billing-Gateway,client_hid=hid1,originurl=http://status.client/"
	fasEnc := base64.StdEncoding.EncodeToString([]byte(fasRaw))
	form := url.Values{}
	form.Set("username", "broke")
	form.Set("password", "secret")
	form.Set("action", "login")
	form.Set("fas", fasEnc)

	req := httptest.NewRequest(http.MethodPost, "/fas?fas="+url.QueryEscape(fasEnc), strings.NewReader(form.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Host = "192.168.1.125:8080"
	rec := httptest.NewRecorder()
	h.HandleFAS(rec, req)

	body := rec.Body.String()
	if rec.Code != http.StatusOK {
		t.Fatalf("status=%d body=%s", rec.Code, body)
	}
	if !strings.Contains(body, "/portal/recharge") || !strings.Contains(body, "token=") {
		t.Fatalf("expected recharge portal redirect, got %s", body)
	}
	if strings.Contains(body, "opennds_auth") {
		t.Fatalf("must not grant network when quota is zero: %s", body)
	}
}

func TestLoginRedirectsToPortal(t *testing.T) {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{Logger: logger.Default.LogMode(logger.Silent)})
	if err != nil {
		t.Fatal(err)
	}
	if err := database.Migrate(db); err != nil {
		t.Fatal(err)
	}
	hash, _ := bcrypt.GenerateFromPassword([]byte("secret"), bcrypt.MinCost)
	user := database.User{
		Username:            "alice",
		PasswordHash:        string(hash),
		Status:              "active",
		QuotaRemainingBytes: 200 * 1024 * 1024,
	}
	if err := db.Create(&user).Error; err != nil {
		t.Fatal(err)
	}

	cfg := &config.Config{
		JWTSecret:     "test-jwt",
		UserPortalURL: "http://192.168.1.125:8080/portal/",
		AuthLogPath:   t.TempDir(),
	}
	h := NewHandler(db, cfg, auth.NewJWTService(cfg.JWTSecret))

	fasRaw := "clientip=192.168.100.10,clientmac=aa:bb:cc:dd:ee:ff,gatewayname=NDS-Billing-Gateway,client_hid=hid1,originurl=http://status.client/"
	fasEnc := base64.StdEncoding.EncodeToString([]byte(fasRaw))
	form := url.Values{}
	form.Set("username", "alice")
	form.Set("password", "secret")
	form.Set("action", "login")
	form.Set("fas", fasEnc)

	req := httptest.NewRequest(http.MethodPost, "/fas?fas="+url.QueryEscape(fasEnc), strings.NewReader(form.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Host = "192.168.1.125:8080"
	rec := httptest.NewRecorder()
	h.HandleFAS(rec, req)

	body := rec.Body.String()
	if rec.Code != http.StatusOK {
		t.Fatalf("status=%d body=%s", rec.Code, body)
	}
	if strings.Contains(body, "status.client") {
		t.Fatalf("should not bounce to captive origin: %s", body)
	}
	if !strings.Contains(body, "/portal/") || !strings.Contains(body, "token=") {
		t.Fatalf("expected portal+token redirect, got %s", body)
	}
}

func TestTokenLoginRedirectsToPortal(t *testing.T) {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{Logger: logger.Default.LogMode(logger.Silent)})
	if err != nil {
		t.Fatal(err)
	}
	if err := database.Migrate(db); err != nil {
		t.Fatal(err)
	}
	user := database.User{
		Username:            "alice",
		PasswordHash:        "x",
		Status:              "active",
		QuotaRemainingBytes: 200 * 1024 * 1024,
	}
	if err := db.Create(&user).Error; err != nil {
		t.Fatal(err)
	}

	cfg := &config.Config{
		JWTSecret:     "test-jwt",
		UserPortalURL: "http://192.168.1.125:8080/portal/",
		AuthLogPath:   t.TempDir(),
	}
	jwtSvc := auth.NewJWTService(cfg.JWTSecret)
	token, err := jwtSvc.Generate(user.ID, "user")
	if err != nil {
		t.Fatal(err)
	}
	h := NewHandler(db, cfg, jwtSvc)

	fasRaw := "clientip=192.168.100.10,clientmac=aa:bb:cc:dd:ee:ff,gatewayname=NDS-Billing-Gateway,gatewayaddress=192.168.100.1:2050,authdir=/opennds_auth/,client_hid=hid1,originurl=http://status.client/"
	fasEnc := base64.StdEncoding.EncodeToString([]byte(fasRaw))
	form := url.Values{}
	form.Set("token", token)
	form.Set("action", "token")
	form.Set("fas", fasEnc)

	req := httptest.NewRequest(http.MethodPost, "/fas?fas="+url.QueryEscape(fasEnc), strings.NewReader(form.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Host = "192.168.1.125:8080"
	rec := httptest.NewRecorder()
	h.HandleFAS(rec, req)

	body := rec.Body.String()
	decodedBody := html.UnescapeString(body)
	if rec.Code != http.StatusOK {
		t.Fatalf("status=%d body=%s", rec.Code, body)
	}
	if strings.Contains(body, "用户名或密码错误") || strings.Contains(body, "登录已过期") {
		t.Fatalf("token login should not ask for password: %s", body)
	}
	if !strings.Contains(decodedBody, "/opennds_auth/") || !strings.Contains(decodedBody, "redir=") || !strings.Contains(decodedBody, "token%3D") {
		t.Fatalf("expected gateway auth and portal token redirect, got %s", body)
	}
}

func TestTokenLoginZeroQuotaRedirectsToRecharge(t *testing.T) {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{Logger: logger.Default.LogMode(logger.Silent)})
	if err != nil {
		t.Fatal(err)
	}
	if err := database.Migrate(db); err != nil {
		t.Fatal(err)
	}
	user := database.User{
		Username:            "broke",
		PasswordHash:        "x",
		Status:              "active",
		QuotaRemainingBytes: 0,
	}
	if err := db.Create(&user).Error; err != nil {
		t.Fatal(err)
	}

	cfg := &config.Config{
		JWTSecret:     "test-jwt",
		UserPortalURL: "http://192.168.1.125:8080/portal/",
		AuthLogPath:   t.TempDir(),
	}
	jwtSvc := auth.NewJWTService(cfg.JWTSecret)
	token, err := jwtSvc.Generate(user.ID, "user")
	if err != nil {
		t.Fatal(err)
	}
	h := NewHandler(db, cfg, jwtSvc)

	fasRaw := "clientip=192.168.100.10,clientmac=aa:bb:cc:dd:ee:ff,gatewayname=NDS-Billing-Gateway,gatewayaddress=192.168.100.1:2050,authdir=/opennds_auth/,client_hid=hid1,originurl=http://status.client/"
	fasEnc := base64.StdEncoding.EncodeToString([]byte(fasRaw))
	form := url.Values{}
	form.Set("token", token)
	form.Set("action", "token")
	form.Set("fas", fasEnc)

	req := httptest.NewRequest(http.MethodPost, "/fas?fas="+url.QueryEscape(fasEnc), strings.NewReader(form.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Host = "192.168.1.125:8080"
	rec := httptest.NewRecorder()
	h.HandleFAS(rec, req)

	body := rec.Body.String()
	if rec.Code != http.StatusOK {
		t.Fatalf("status=%d body=%s", rec.Code, body)
	}
	if !strings.Contains(body, "/portal/recharge") || !strings.Contains(body, "token=") {
		t.Fatalf("expected recharge portal redirect, got %s", body)
	}
	if strings.Contains(body, "opennds_auth") {
		t.Fatalf("zero quota token login must not grant network: %s", body)
	}
}

func TestBindMACMovesDeviceFromPreviousUser(t *testing.T) {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{Logger: logger.Default.LogMode(logger.Silent)})
	if err != nil {
		t.Fatal(err)
	}
	if err := database.Migrate(db); err != nil {
		t.Fatal(err)
	}

	oldUser := database.User{Username: "old", PasswordHash: "x", Status: "active"}
	newUser := database.User{Username: "new", PasswordHash: "x", Status: "active"}
	if err := db.Create(&oldUser).Error; err != nil {
		t.Fatal(err)
	}
	if err := db.Create(&newUser).Error; err != nil {
		t.Fatal(err)
	}
	if err := db.Create(&database.UserDevice{UserID: oldUser.ID, MAC: "aa:bb:cc:dd:ee:ff"}).Error; err != nil {
		t.Fatal(err)
	}

	h := NewHandler(db, &config.Config{}, nil)
	h.bindMAC(newUser.ID, "AA:BB:CC:DD:EE:FF")

	var devices []database.UserDevice
	if err := db.Where("mac = ?", "aa:bb:cc:dd:ee:ff").Find(&devices).Error; err != nil {
		t.Fatal(err)
	}
	if len(devices) != 1 {
		t.Fatalf("expected one MAC owner, got %d", len(devices))
	}
	if devices[0].UserID != newUser.ID {
		t.Fatalf("MAC remained on user %d, want %d", devices[0].UserID, newUser.ID)
	}
}

func TestPruneAuthQueueRemovesOnlyExpiredFiles(t *testing.T) {
	dir := t.TempDir()
	oldPath := filepath.Join(dir, "old")
	newPath := filepath.Join(dir, "new")
	if err := os.WriteFile(oldPath, []byte("old"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(newPath, []byte("new"), 0600); err != nil {
		t.Fatal(err)
	}
	oldTime := time.Now().Add(-20 * time.Minute)
	if err := os.Chtimes(oldPath, oldTime, oldTime); err != nil {
		t.Fatal(err)
	}

	(&Handler{}).pruneAuthQueue(dir, 10*time.Minute)

	if _, err := os.Stat(oldPath); !os.IsNotExist(err) {
		t.Fatalf("expired auth entry still exists: %v", err)
	}
	if _, err := os.Stat(newPath); err != nil {
		t.Fatalf("fresh auth entry was removed: %v", err)
	}
}
