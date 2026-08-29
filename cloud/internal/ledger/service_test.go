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

// Traffic reported by a router has already been carried, so an overshoot is
// booked down to a zero balance rather than rejected.
func TestConsumeClampsOvershootToZero(t *testing.T) {
	db := setupTestDB(t)
	svc := ledger.New(db)

	user := database.User{Username: "test2", QuotaRemainingBytes: 100}
	db.Create(&user)

	balance, err := svc.Consume(user.ID, 200, "session2")
	if err != nil {
		t.Fatalf("consume: %v", err)
	}
	if balance != 0 {
		t.Fatalf("balance = %d, want 0", balance)
	}

	var entry database.QuotaLedger
	db.Where("user_id = ?", user.ID).Order("id desc").First(&entry)
	if entry.AmountBytes != -100 {
		t.Errorf("booked %d bytes, want the 100 that were actually available", entry.AmountBytes)
	}
	if entry.BalanceAfter != 0 {
		t.Errorf("balance_after = %d, want 0", entry.BalanceAfter)
	}
}

// Administrative deductions are a different matter: they must not silently
// take less than asked.
func TestAdminDeductionRejectsOverdraft(t *testing.T) {
	db := setupTestDB(t)
	svc := ledger.New(db)

	user := database.User{Username: "test2b", QuotaRemainingBytes: 100}
	db.Create(&user)

	err := db.Transaction(func(tx *gorm.DB) error {
		_, err := svc.ChangeQuota(tx, user.ID, -200, "admin_adjust", "ref", "", nil)
		return err
	})
	if err != ledger.ErrInsufficientQuota {
		t.Fatalf("expected insufficient quota, got %v", err)
	}

	var stored database.User
	db.First(&stored, user.ID)
	if stored.QuotaRemainingBytes != 100 {
		t.Errorf("balance = %d, want the rejected deduction to leave it untouched", stored.QuotaRemainingBytes)
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
