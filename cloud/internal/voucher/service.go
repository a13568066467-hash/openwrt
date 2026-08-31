package voucher

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/csv"
	"encoding/hex"
	"encoding/json"
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

func (s *Service) CreateBatch(name string, trafficMB int64, count int, validDays int, adminID uint) (*CreateBatchResult, error) {
	if validDays <= 0 {
		validDays = 90
	}
	batch := database.VoucherBatch{
		Name:      name,
		TrafficMB: trafficMB,
		Count:     count,
		ValidDays: validDays,
		CreatedBy: adminID,
	}

	result := &CreateBatchResult{}
	codes := make([]string, 0, count)
	for i := 0; i < count; i++ {
		code := generateCode()
		codes = append(codes, code)
	}

	codesJSON, err := json.Marshal(codes)
	if err != nil {
		return nil, err
	}
	batch.CodesJSON = string(codesJSON)

	if err := s.db.Create(&batch).Error; err != nil {
		return nil, err
	}

	result.BatchID = batch.ID
	result.Codes = codes
	for _, code := range codes {
		s.db.Create(&database.Voucher{
			BatchID:  batch.ID,
			CodeHash: hashCode(code),
			Status:   "unused",
		})
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
		if err != nil {
			return err
		}

		if batch.ValidDays > 0 {
			var user database.User
			if err := tx.First(&user, userID).Error; err != nil {
				return err
			}
			expires := now.AddDate(0, 0, batch.ValidDays)
			if user.QuotaExpiresAt != nil && user.QuotaExpiresAt.After(now) {
				expires = user.QuotaExpiresAt.AddDate(0, 0, batch.ValidDays)
			}
			return tx.Model(&user).Update("quota_expires_at", expires).Error
		}
		return nil
	})
	if err != nil {
		return 0, err
	}
	return balance, nil
}

func (s *Service) ListBatches() ([]BatchListItem, error) {
	var batches []database.VoucherBatch
	if err := s.db.Order("id desc").Find(&batches).Error; err != nil {
		return nil, err
	}
	items := make([]BatchListItem, len(batches))
	for i, b := range batches {
		items[i].VoucherBatch = b
		if b.Count == 1 && b.CodesJSON != "" {
			var codes []string
			if json.Unmarshal([]byte(b.CodesJSON), &codes) == nil && len(codes) > 0 {
				items[i].Code = codes[0]
			}
		}
	}
	return items, nil
}

type BatchListItem struct {
	database.VoucherBatch
	Code string `json:"code,omitempty"`
}

func (s *Service) ListByBatch(batchID uint) ([]database.Voucher, error) {
	var vouchers []database.Voucher
	err := s.db.Where("batch_id = ?", batchID).Find(&vouchers).Error
	return vouchers, err
}

type BatchDetail struct {
	Batch    database.VoucherBatch `json:"batch"`
	Codes    []string              `json:"codes"`
	Vouchers []database.Voucher    `json:"vouchers"`
}

func (s *Service) GetBatchDetail(batchID uint) (*BatchDetail, error) {
	var batch database.VoucherBatch
	if err := s.db.First(&batch, batchID).Error; err != nil {
		return nil, err
	}
	vouchers, err := s.ListByBatch(batchID)
	if err != nil {
		return nil, err
	}
	codes := []string{}
	if batch.CodesJSON != "" {
		_ = json.Unmarshal([]byte(batch.CodesJSON), &codes)
	}
	return &BatchDetail{Batch: batch, Codes: codes, Vouchers: vouchers}, nil
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
