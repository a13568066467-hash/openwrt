package cron

import (
	"context"
	"log/slog"
	"time"

	"github.com/nds-billing/cloud/internal/config"
	"github.com/nds-billing/cloud/internal/database"
	"github.com/nds-billing/cloud/internal/ledger"
	"gorm.io/gorm"
)

func Start(ctx context.Context, db *gorm.DB, cfg *config.Config) {
	ledgerSvc := ledger.New(db)

	go func() {
		ticker := time.NewTicker(5 * time.Minute)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				expireQuotas(db, ledgerSvc)
				markOfflineRouters(db)
				cleanupSessions(db)
				reconcileAll(db, ledgerSvc)
			}
		}
	}()
}

func expireQuotas(db *gorm.DB, ledgerSvc *ledger.Service) {
	now := time.Now()
	var users []database.User
	db.Where("quota_expires_at IS NOT NULL AND quota_expires_at < ? AND quota_remaining_bytes > 0", now).Find(&users)
	for _, u := range users {
		amount := -u.QuotaRemainingBytes
		ledgerSvc.TopUp(u.ID, amount, "expiry", "额度到期清零", nil)
		slog.Info("quota expired", "user_id", u.ID)
	}
}

func markOfflineRouters(db *gorm.DB) {
	threshold := time.Now().Add(-3 * time.Minute)
	db.Model(&database.Router{}).Where("last_heartbeat < ? AND online = ?", threshold, true).
		Update("online", false)
}

func cleanupSessions(db *gorm.DB) {
	threshold := time.Now().Add(-24 * time.Hour)
	db.Model(&database.Session{}).Where("active = ? AND started_at < ?", true, threshold).
		Updates(map[string]interface{}{"active": false, "ended_at": time.Now()})
}

func reconcileAll(db *gorm.DB, ledgerSvc *ledger.Service) {
	var users []database.User
	db.Find(&users)
	for _, u := range users {
		if err := ledgerSvc.Reconcile(u.ID); err != nil {
			slog.Warn("reconcile mismatch", "user_id", u.ID, "error", err)
		}
	}
}
