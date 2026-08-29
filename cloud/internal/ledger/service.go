package ledger

import (
	"errors"
	"fmt"

	"github.com/nds-billing/cloud/internal/database"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

var (
	ErrInsufficientQuota = errors.New("insufficient quota")
	ErrUserNotFound      = errors.New("user not found")
)

type Service struct {
	db *gorm.DB
}

func New(db *gorm.DB) *Service {
	return &Service{db: db}
}

func (s *Service) ChangeQuota(tx *gorm.DB, userID uint, amountBytes int64, ledgerType, reference, note string, operatorID *uint) (int64, error) {
	var user database.User
	if err := tx.Clauses(clause.Locking{Strength: "UPDATE"}).First(&user, userID).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return 0, ErrUserNotFound
		}
		return 0, err
	}

	newBalance := user.QuotaRemainingBytes + amountBytes
	if newBalance < 0 {
		return user.QuotaRemainingBytes, ErrInsufficientQuota
	}

	if err := tx.Model(&user).Update("quota_remaining_bytes", newBalance).Error; err != nil {
		return 0, err
	}

	entry := database.QuotaLedger{
		UserID:       userID,
		Type:         ledgerType,
		AmountBytes:  amountBytes,
		BalanceAfter: newBalance,
		Reference:    reference,
		OperatorID:   operatorID,
		Note:         note,
	}
	if err := tx.Create(&entry).Error; err != nil {
		return 0, err
	}

	return newBalance, nil
}

func (s *Service) TopUp(userID uint, amountBytes int64, reference, note string, operatorID *uint) (int64, error) {
	var balance int64
	err := s.db.Transaction(func(tx *gorm.DB) error {
		var err error
		balance, err = s.ChangeQuota(tx, userID, amountBytes, "topup", reference, note, operatorID)
		return err
	})
	return balance, err
}

// Consume books traffic that has already been carried, so it clamps at zero
// instead of failing on an overdraft. A router reports every 60 seconds and
// only stops a client once its own copy of the balance runs out, so the final
// delta of a session routinely overshoots; rejecting it would leave that
// traffic unbilled and the balance stuck above zero forever.
func (s *Service) Consume(userID uint, amountBytes int64, reference string) (int64, error) {
	var balance int64

	err := s.db.Transaction(func(tx *gorm.DB) error {
		var user database.User
		if err := tx.Clauses(clause.Locking{Strength: "UPDATE"}).First(&user, userID).Error; err != nil {
			if errors.Is(err, gorm.ErrRecordNotFound) {
				return ErrUserNotFound
			}
			return err
		}

		booked := amountBytes
		if booked > user.QuotaRemainingBytes {
			booked = user.QuotaRemainingBytes
		}
		if booked < 0 {
			booked = 0
		}

		var err error
		balance, err = s.ChangeQuota(tx, userID, -booked, "consume", reference, "", nil)
		return err
	})

	return balance, err
}

func (s *Service) Reconcile(userID uint) error {
	var user database.User
	if err := s.db.First(&user, userID).Error; err != nil {
		return err
	}

	var lastEntry database.QuotaLedger
	err := s.db.Where("user_id = ?", userID).Order("id desc").First(&lastEntry).Error
	if errors.Is(err, gorm.ErrRecordNotFound) {
		return nil
	}
	if err != nil {
		return err
	}

	if user.QuotaRemainingBytes != lastEntry.BalanceAfter {
		return fmt.Errorf("quota mismatch: cache=%d ledger=%d", user.QuotaRemainingBytes, lastEntry.BalanceAfter)
	}
	return nil
}
