package fas

import (
	"encoding/base64"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"testing"

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
