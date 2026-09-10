package userapi

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/glebarez/sqlite"
	"github.com/nds-billing/cloud/internal/auth"
	"github.com/nds-billing/cloud/internal/database"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

func TestGetUsageFiltersBySessionOwnerNotCurrentMACBinding(t *testing.T) {
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

	mac := "aa:bb:cc:dd:ee:ff"
	oldSession := database.Session{
		SessionKey: "router:" + mac + ":old:1",
		UserID:     oldUser.ID,
		MAC:        mac,
		StartedAt:  time.Now(),
	}
	newSession := database.Session{
		SessionKey: "router:" + mac + ":new:2",
		UserID:     newUser.ID,
		MAC:        mac,
		StartedAt:  time.Now(),
	}
	if err := db.Create(&oldSession).Error; err != nil {
		t.Fatal(err)
	}
	if err := db.Create(&newSession).Error; err != nil {
		t.Fatal(err)
	}
	if err := db.Create(&database.UserDevice{UserID: newUser.ID, MAC: mac}).Error; err != nil {
		t.Fatal(err)
	}
	if err := db.Create(&database.UsageRecord{
		SessionKey: oldSession.SessionKey,
		Seq:        1,
		MAC:        mac,
		DeltaBytes: 111,
		TotalBytes: 111,
		RecordedAt: time.Now(),
	}).Error; err != nil {
		t.Fatal(err)
	}
	if err := db.Create(&database.UsageRecord{
		SessionKey: newSession.SessionKey,
		Seq:        1,
		MAC:        mac,
		DeltaBytes: 222,
		TotalBytes: 222,
		RecordedAt: time.Now(),
	}).Error; err != nil {
		t.Fatal(err)
	}

	h := NewHandler(db, auth.NewJWTService("test"))
	req := httptest.NewRequest(http.MethodGet, "/api/v1/user/usage", nil)
	req = req.WithContext(context.WithValue(req.Context(), auth.UserIDKey, newUser.ID))
	rec := httptest.NewRecorder()

	h.GetUsage(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status=%d body=%s", rec.Code, rec.Body.String())
	}
	var records []database.UsageRecord
	if err := json.NewDecoder(rec.Body).Decode(&records); err != nil {
		t.Fatal(err)
	}
	if len(records) != 1 {
		t.Fatalf("expected one record, got %d: %#v", len(records), records)
	}
	if records[0].SessionKey != newSession.SessionKey || records[0].DeltaBytes != 222 {
		t.Fatalf("got wrong usage record: %#v", records[0])
	}
}
