package voucher

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/csv"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"strings"
	"time"

	"github.com/nds-billing/cloud/internal/database"
	"github.com/nds-billing/cloud/internal/ledger"
	"gorm.io/gorm"
)

var (
	ErrInvalidCode = errors.New("invalid voucher code")
	ErrAlreadyUsed = errors.New("voucher already used")
	ErrRateLimited = errors.New("too many attempts")
)

type Service struct {
	db     *gorm.DB
	ledger *ledger.Service
}

func New(db *gorm.DB) *Service {
	return &Service{db: db, ledger: ledger.New(db)}
}

func normalizeCode(code string) string {
	code = strings.TrimSpace(code)
	code = strings.ReplaceAll(code, "-", "")
	code = strings.ReplaceAll(code, " ", "")
	return strings.ToLower(code)
}

func hashCode(code string) string {
	sum := sha256.Sum256([]byte(normalizeCode(code)))
	return hex.EncodeToString(sum[:])
}

func generateCode() string {
	b := make([]byte, 8)
	rand.Read(b)
	return hex.EncodeToString(b)
}

type CreateBatchResult struct {
	BatchID uint     `json:"batch_id"`
	Codes   []string `json:"codes"`
}

func (s *Service) CreateBatch(name string, trafficMB int64, count int, adminID uint) (*CreateBatchResult, error) {
	batch := database.VoucherBatch{
		Name:      name,
		TrafficMB: trafficMB,
		Count:     count,
		CreatedBy: adminID,
	}
	if err := s.db.Create(&batch).Error; err != nil {
		return nil, err
	}

	result := &CreateBatchResult{BatchID: batch.ID}
	for i := 0; i < count; i++ {
		code := generateCode()
		s.db.Create(&database.Voucher{
			BatchID:  batch.ID,
			CodeHash: hashCode(code),
			Status:   "unused",
		})
		result.Codes = append(result.Codes, code)
	}
	return result, nil
}

func (s *Service) ExportBatchCSV(w io.Writer, batchID uint) error {
	var vouchers []database.Voucher
	s.db.Where("batch_id = ?", batchID).Find(&vouchers)

	cw := csv.NewWriter(w)
	cw.Write([]string{"id", "status", "redeemed_by", "redeemed_at"})
	for _, v := range vouchers {
		redeemedAt := ""
		if v.RedeemedAt != nil {
			redeemedAt = v.RedeemedAt.Format(time.RFC3339)
		}
		redeemedBy := ""
		if v.RedeemedBy != nil {
			redeemedBy = fmt.Sprintf("%d", *v.RedeemedBy)
		}
		cw.Write([]string{fmt.Sprintf("%d", v.ID), v.Status, redeemedBy, redeemedAt})
	}
	cw.Flush()
	return cw.Error()
}

func (s *Service) Redeem(code string, userID uint) (int64, error) {
	codeHash := hashCode(code)
	var balance int64

	err := s.db.Transaction(func(tx *gorm.DB) error {
		var voucher database.Voucher
		if err := tx.Where("code_hash = ?", codeHash).First(&voucher).Error; err != nil {
			return ErrInvalidCode
		}
		if voucher.Status != "unused" {
			return ErrAlreadyUsed
		}

		var batch database.VoucherBatch
		if err := tx.First(&batch, voucher.BatchID).Error; err != nil {
			return ErrInvalidCode
		}

		now := time.Now()
		result := tx.Model(&voucher).Where("status = ?", "unused").Updates(map[string]interface{}{
			"status":      "used",
			"redeemed_by": userID,
			"redeemed_at": now,
		})
		if result.Error != nil {
			return result.Error
		}
		if result.RowsAffected == 0 {
			return ErrAlreadyUsed
		}

		amountBytes := batch.TrafficMB * 1024 * 1024
		var err error
		balance, err = s.ledger.ChangeQuota(tx, userID, amountBytes, "topup", fmt.Sprintf("voucher:%d", voucher.ID), "卡密充值", nil)
		return err
	})
	if err != nil {
		return 0, err
	}
	return balance, nil
}

func (s *Service) ListBatches() ([]database.VoucherBatch, error) {
	var batches []database.VoucherBatch
	err := s.db.Order("id desc").Find(&batches).Error
	return batches, err
}

func (s *Service) ListByBatch(batchID uint) ([]database.Voucher, error) {
	var vouchers []database.Voucher
	err := s.db.Where("batch_id = ?", batchID).Find(&vouchers).Error
	return vouchers, err
}

type RedeemedRecord struct {
	ID         uint       `json:"id"`
	BatchName  string     `json:"batch_name"`
	TrafficMB  int64      `json:"traffic_mb"`
	RedeemedAt *time.Time `json:"redeemed_at"`
}

func (s *Service) ListRedeemedByUser(userID uint) ([]RedeemedRecord, error) {
	var vouchers []database.Voucher
	if err := s.db.Where("redeemed_by = ? AND status = ?", userID, "used").
		Order("redeemed_at desc, id desc").
		Find(&vouchers).Error; err != nil {
		return nil, err
	}

	records := make([]RedeemedRecord, 0, len(vouchers))
	for _, v := range vouchers {
		var batch database.VoucherBatch
		if err := s.db.First(&batch, v.BatchID).Error; err != nil {
			continue
		}
		records = append(records, RedeemedRecord{
			ID:         v.ID,
			BatchName:  batch.Name,
			TrafficMB:  batch.TrafficMB,
			RedeemedAt: v.RedeemedAt,
		})
	}
	return records, nil
}
