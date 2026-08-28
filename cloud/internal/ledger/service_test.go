package ledger_test

import (
	"testing"

	"github.com/nds-billing/cloud/internal/database"
	"github.com/nds-billing/cloud/internal/ledger"
	"github.com/glebarez/sqlite"
	"gorm.io/gorm"
)

func setupTestDB(t *testing.T) *gorm.DB {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatal(err)
	}
	db.AutoMigrate(&database.User{}, &database.QuotaLedger{})
	return db
}

func TestTopUpAndConsume(t *testing.T) {
	db := setupTestDB(t)
	svc := ledger.New(db)

	user := database.User{Username: "test", QuotaRemainingBytes: 0}
	db.Create(&user)

	balance, err := svc.TopUp(user.ID, 1024*1024, "test", "test topup", nil)
	if err != nil {
		t.Fatal(err)
	}
	if balance != 1024*1024 {
		t.Fatalf("expected 1MB, got %d", balance)
	}

	balance, err = svc.Consume(user.ID, 512*1024, "session1")
	if err != nil {
		t.Fatal(err)
	}
	if balance != 512*1024 {
		t.Fatalf("expected 512KB, got %d", balance)
	}
}

func TestInsufficientQuota(t *testing.T) {
	db := setupTestDB(t)
	svc := ledger.New(db)

	user := database.User{Username: "test2", QuotaRemainingBytes: 100}
	db.Create(&user)

	_, err := svc.Consume(user.ID, 200, "session2")
	if err != ledger.ErrInsufficientQuota {
		t.Fatalf("expected insufficient quota, got %v", err)
	}
}

func TestIdempotentLedger(t *testing.T) {
	db := setupTestDB(t)
	svc := ledger.New(db)

	user := database.User{Username: "test3", QuotaRemainingBytes: 0}
	db.Create(&user)

	svc.TopUp(user.ID, 1000, "ref1", "note", nil)
	svc.TopUp(user.ID, 2000, "ref2", "note", nil)

	var entries []database.QuotaLedger
	db.Where("user_id = ?", user.ID).Find(&entries)
	if len(entries) != 2 {
		t.Fatalf("expected 2 ledger entries, got %d", len(entries))
	}
	if entries[1].BalanceAfter != 3000 {
		t.Fatalf("expected balance 3000, got %d", entries[1].BalanceAfter)
	}
}

func TestReconcile(t *testing.T) {
	db := setupTestDB(t)
	svc := ledger.New(db)

	user := database.User{Username: "test4", QuotaRemainingBytes: 5000}
	db.Create(&user)
	db.Create(&database.QuotaLedger{UserID: user.ID, Type: "topup", AmountBytes: 5000, BalanceAfter: 5000})

	if err := svc.Reconcile(user.ID); err != nil {
		t.Fatal(err)
	}
}
