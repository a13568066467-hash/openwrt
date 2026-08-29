package device

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/glebarez/sqlite"
	"github.com/nds-billing/cloud/internal/database"
	"golang.org/x/crypto/bcrypt"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

const deviceSecret = "correct-horse-battery-staple"

func newTestHandler(t *testing.T) (*Handler, *gorm.DB, database.Router, database.User) {
	t.Helper()

	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{
		Logger: logger.Default.LogMode(logger.Silent),
	})
	if err != nil {
		t.Fatalf("open database: %v", err)
	}
	if err := database.Migrate(db); err != nil {
		t.Fatalf("migrate: %v", err)
	}

	hash, _ := bcrypt.GenerateFromPassword([]byte(deviceSecret), bcrypt.MinCost)
	router := database.Router{DeviceID: "router-1", Name: "lobby", SecretHash: string(hash)}
	if err := db.Create(&router).Error; err != nil {
		t.Fatalf("seed router: %v", err)
	}

	user := database.User{Username: "alice", QuotaRemainingBytes: 10 * 1024 * 1024}
	if err := db.Create(&user).Error; err != nil {
		t.Fatalf("seed user: %v", err)
	}

	db.Create(&database.Session{
		SessionKey: "router-1:aa:bb:cc:dd:ee:ff:1",
		UserID:     user.ID,
		RouterID:   router.ID,
		MAC:        "aa:bb:cc:dd:ee:ff",
		StartedAt:  time.Now(),
		Active:     true,
	})

	return NewHandler(db), db, router, user
}

func postJSON(t *testing.T, h http.HandlerFunc, body any) *httptest.ResponseRecorder {
	t.Helper()

	encoded, err := json.Marshal(body)
	if err != nil {
		t.Fatalf("encode request: %v", err)
	}

	req := httptest.NewRequest(http.MethodPost, "/api/v1/device/report", bytes.NewReader(encoded))
	rec := httptest.NewRecorder()
	h(rec, req)

	return rec
}

// The agent sends credentials inside the JSON body because uclient-fetch,
// its fallback transport, cannot set custom headers.
func reportBody(reports []map[string]any) map[string]any {
	return map[string]any{
		"device_id":     "router-1",
		"device_secret": deviceSecret,
		"reports":       reports,
	}
}

func TestReportRejectsWrongSecret(t *testing.T) {
	h, _, _, _ := newTestHandler(t)

	body := reportBody(nil)
	body["device_secret"] = "wrong"

	rec := postJSON(t, h.HandleReport, body)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401 for a bad secret, got %d", rec.Code)
	}
}

func TestReportRejectsMissingCredentials(t *testing.T) {
	h, _, _, _ := newTestHandler(t)

	rec := postJSON(t, h.HandleReport, map[string]any{"reports": []any{}})
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401 without credentials, got %d", rec.Code)
	}
}

func TestReportDeductsAndReturnsBalance(t *testing.T) {
	h, db, _, user := newTestHandler(t)

	rec := postJSON(t, h.HandleReport, reportBody([]map[string]any{{
		"session_key": "router-1:aa:bb:cc:dd:ee:ff:tok:1",
		"seq":         1,
		"mac":         "AA:BB:CC:DD:EE:FF",
		"delta_bytes": 1024 * 1024,
		"total_bytes": 1024 * 1024,
	}}))

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d (%s)", rec.Code, rec.Body.String())
	}

	var resp reportResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("decode response: %v", err)
	}

	if !resp.OK {
		t.Fatal("expected ok=true")
	}
	if len(resp.QuotaUpdates) != 1 {
		t.Fatalf("expected one quota update, got %d", len(resp.QuotaUpdates))
	}

	update := resp.QuotaUpdates[0]
	if want := int64(9 * 1024 * 1024); update.RemainingBytes != want {
		t.Errorf("remaining_bytes = %d, want %d", update.RemainingBytes, want)
	}
	if update.MAC != "aa:bb:cc:dd:ee:ff" {
		t.Errorf("mac = %q, want it normalised to lowercase", update.MAC)
	}
	if update.UserID != user.ID {
		t.Errorf("user_id = %d, want %d", update.UserID, user.ID)
	}

	var stored database.User
	db.First(&stored, user.ID)
	if want := int64(9 * 1024 * 1024); stored.QuotaRemainingBytes != want {
		t.Errorf("stored balance = %d, want %d", stored.QuotaRemainingBytes, want)
	}
}

// A router that reboots or replays its backlog resends deltas it already
// delivered; those must not be billed twice.
func TestReportIsIdempotentPerSessionAndSeq(t *testing.T) {
	h, db, _, user := newTestHandler(t)

	report := reportBody([]map[string]any{{
		"session_key": "router-1:aa:bb:cc:dd:ee:ff:tok:1",
		"seq":         1,
		"mac":         "aa:bb:cc:dd:ee:ff",
		"delta_bytes": 2 * 1024 * 1024,
		"total_bytes": 2 * 1024 * 1024,
	}})

	postJSON(t, h.HandleReport, report)
	postJSON(t, h.HandleReport, report)
	postJSON(t, h.HandleReport, report)

	var stored database.User
	db.First(&stored, user.ID)

	if want := int64(8 * 1024 * 1024); stored.QuotaRemainingBytes != want {
		t.Fatalf("balance = %d after three identical reports, want %d charged once",
			stored.QuotaRemainingBytes, want)
	}

	var records int64
	db.Model(&database.UsageRecord{}).Count(&records)
	if records != 1 {
		t.Errorf("stored %d usage records, want 1", records)
	}
}

// The final delta of a session almost always overshoots the balance, since the
// router only stops a client once its own copy runs out.
func TestReportClampsOvershootAndQueuesDeauth(t *testing.T) {
	h, db, router, user := newTestHandler(t)

	rec := postJSON(t, h.HandleReport, reportBody([]map[string]any{{
		"session_key": "router-1:aa:bb:cc:dd:ee:ff:tok:1",
		"seq":         1,
		"mac":         "aa:bb:cc:dd:ee:ff",
		"delta_bytes": 50 * 1024 * 1024,
		"total_bytes": 50 * 1024 * 1024,
	}}))

	var resp reportResponse
	json.Unmarshal(rec.Body.Bytes(), &resp)

	if len(resp.QuotaUpdates) != 1 || resp.QuotaUpdates[0].RemainingBytes != 0 {
		t.Fatalf("expected the balance to floor at 0, got %+v", resp.QuotaUpdates)
	}

	var stored database.User
	db.First(&stored, user.ID)
	if stored.QuotaRemainingBytes != 0 {
		t.Errorf("stored balance = %d, want 0", stored.QuotaRemainingBytes)
	}

	var queued database.RouterCommand
	if err := db.Where("router_id = ? AND action = ?", router.ID, "deauth").
		First(&queued).Error; err != nil {
		t.Fatalf("expected a deauth command to be queued: %v", err)
	}
	if queued.MAC != "aa:bb:cc:dd:ee:ff" {
		t.Errorf("queued deauth for %q, want the reporting client", queued.MAC)
	}
}

func TestHeartbeatDeliversQueuedCommandsExactlyOnce(t *testing.T) {
	h, db, router, user := newTestHandler(t)

	db.Create(&database.RouterCommand{
		RouterID: router.ID, Action: "deauth", MAC: "aa:bb:cc:dd:ee:ff", UserID: user.ID,
	})
	db.Create(&database.RouterCommand{
		RouterID: router.ID, Action: "set_quota", MAC: "aa:bb:cc:dd:ee:ff",
		UserID: user.ID, RemainingBytes: 4096,
	})

	beat := map[string]any{
		"device_id": "router-1", "device_secret": deviceSecret,
		"online": true, "agent_version": "1.0.0",
	}

	rec := postJSON(t, h.HandleHeartbeat, beat)
	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d (%s)", rec.Code, rec.Body.String())
	}

	var resp heartbeatResponse
	json.Unmarshal(rec.Body.Bytes(), &resp)

	if len(resp.Commands) != 2 {
		t.Fatalf("expected 2 commands, got %d", len(resp.Commands))
	}
	if resp.Commands[0].Action != "deauth" || resp.Commands[1].Action != "set_quota" {
		t.Errorf("commands delivered out of order: %+v", resp.Commands)
	}
	if resp.Commands[1].RemainingBytes != 4096 {
		t.Errorf("set_quota carried %d bytes, want 4096", resp.Commands[1].RemainingBytes)
	}

	second := postJSON(t, h.HandleHeartbeat, beat)
	var again heartbeatResponse
	json.Unmarshal(second.Body.Bytes(), &again)

	if len(again.Commands) != 0 {
		t.Errorf("delivered commands a second time: %+v", again.Commands)
	}
}

func TestHeartbeatMarksRouterOnline(t *testing.T) {
	h, db, router, _ := newTestHandler(t)

	postJSON(t, h.HandleHeartbeat, map[string]any{
		"device_id": "router-1", "device_secret": deviceSecret, "online": true,
	})

	var stored database.Router
	db.First(&stored, router.ID)

	if !stored.Online {
		t.Error("router was not marked online")
	}
	if stored.LastHeartbeat == nil {
		t.Error("last_heartbeat was not recorded")
	}
}

// Traffic is attributed through the active session, because a MAC may have
// been bound to several accounts over time.
func TestReportAttributesTrafficViaActiveSession(t *testing.T) {
	h, db, router, first := newTestHandler(t)

	second := database.User{Username: "bob", QuotaRemainingBytes: 5 * 1024 * 1024}
	db.Create(&second)

	// Both accounts have used this MAC; only bob's session is current.
	db.Create(&database.UserDevice{UserID: first.ID, MAC: "11:22:33:44:55:66",
		FirstSeen: time.Now().Add(-time.Hour), LastSeen: time.Now().Add(-time.Hour)})
	db.Create(&database.UserDevice{UserID: second.ID, MAC: "11:22:33:44:55:66",
		FirstSeen: time.Now(), LastSeen: time.Now()})
	db.Create(&database.Session{
		SessionKey: "router-1:11:22:33:44:55:66:2", UserID: second.ID,
		RouterID: router.ID, MAC: "11:22:33:44:55:66", StartedAt: time.Now(), Active: true,
	})

	postJSON(t, h.HandleReport, reportBody([]map[string]any{{
		"session_key": "router-1:11:22:33:44:55:66:tok:1",
		"seq":         1,
		"mac":         "11:22:33:44:55:66",
		"delta_bytes": 1024 * 1024,
		"total_bytes": 1024 * 1024,
	}}))

	var alice, bob database.User
	db.First(&alice, first.ID)
	db.First(&bob, second.ID)

	if alice.QuotaRemainingBytes != 10*1024*1024 {
		t.Errorf("charged the wrong account: alice's balance changed to %d",
			alice.QuotaRemainingBytes)
	}
	if want := int64(4 * 1024 * 1024); bob.QuotaRemainingBytes != want {
		t.Errorf("bob's balance = %d, want %d", bob.QuotaRemainingBytes, want)
	}
}
