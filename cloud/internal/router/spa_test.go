package router

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"

	"github.com/glebarez/sqlite"
	"github.com/nds-billing/cloud/internal/config"
	"github.com/nds-billing/cloud/internal/database"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

func TestUserPortalSPA(t *testing.T) {
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, "index.html"), []byte("<html>portal-home</html>"), 0644); err != nil {
		t.Fatal(err)
	}

	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{Logger: logger.Default.LogMode(logger.Silent)})
	if err != nil {
		t.Fatal(err)
	}
	if err := database.Migrate(db); err != nil {
		t.Fatal(err)
	}

	h := New(db, &config.Config{JWTSecret: "x", UserWebDir: dir})
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/portal/", nil))
	if rec.Code != http.StatusOK || rec.Body.String() != "<html>portal-home</html>" {
		t.Fatalf("index status=%d body=%s", rec.Code, rec.Body.String())
	}
	if got := rec.Header().Get("Cache-Control"); got != "no-store" {
		t.Fatalf("index cache-control=%q", got)
	}

	rec2 := httptest.NewRecorder()
	h.ServeHTTP(rec2, httptest.NewRequest(http.MethodGet, "/portal/login", nil))
	if rec2.Code != http.StatusOK || rec2.Body.String() != "<html>portal-home</html>" {
		t.Fatalf("spa fallback status=%d body=%s", rec2.Code, rec2.Body.String())
	}
	if got := rec2.Header().Get("Cache-Control"); got != "no-store" {
		t.Fatalf("fallback cache-control=%q", got)
	}
}
