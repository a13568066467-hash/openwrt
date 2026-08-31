package admin

import (
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"time"

	"github.com/nds-billing/cloud/internal/auth"
	"github.com/nds-billing/cloud/internal/branding"
	"github.com/nds-billing/cloud/internal/database"
	"github.com/nds-billing/cloud/internal/ledger"
	"golang.org/x/crypto/bcrypt"
	"gorm.io/gorm"
)

type Handler struct {
	db     *gorm.DB
	ledger *ledger.Service
	jwt    *auth.JWTService
}

func NewHandler(db *gorm.DB, jwt *auth.JWTService) *Handler {
	return &Handler{db: db, ledger: ledger.New(db), jwt: jwt}
}

func (h *Handler) HandleLogin(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Username string `json:"username"`
		Password string `json:"password"`
	}
	json.NewDecoder(r.Body).Decode(&req)

	var admin database.Admin
	if err := h.db.Where("username = ?", req.Username).First(&admin).Error; err != nil {
		http.Error(w, "invalid credentials", http.StatusUnauthorized)
		return
	}
	if err := bcrypt.CompareHashAndPassword([]byte(admin.PasswordHash), []byte(req.Password)); err != nil {
		http.Error(w, "invalid credentials", http.StatusUnauthorized)
		return
	}

	token, _ := h.jwt.Generate(admin.ID, "admin")
	json.NewEncoder(w).Encode(map[string]string{"token": token})
}

func (h *Handler) ListRouters(w http.ResponseWriter, r *http.Request) {
	var routers []database.Router
	h.db.Find(&routers)
	json.NewEncoder(w).Encode(routers)
}

func (h *Handler) ListUsers(w http.ResponseWriter, r *http.Request) {
	var users []database.User
	h.db.Find(&users)
	json.NewEncoder(w).Encode(users)
}

func (h *Handler) AdjustQuota(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.ParseUint(r.PathValue("id"), 10, 64)
	var req struct {
		AmountMB int64  `json:"amount_mb"`
		Note     string `json:"note"`
	}
	json.NewDecoder(r.Body).Decode(&req)

	adminID := auth.GetAdminID(r.Context())
	amountBytes := req.AmountMB * 1024 * 1024
	ledgerType := "admin_add"
	if amountBytes < 0 {
		ledgerType = "admin_deduct"
	}

	balance, err := h.ledger.TopUp(uint(id), amountBytes, "admin_adjust", req.Note, &adminID)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	h.pushQuota(uint(id), balance)
	h.audit(adminID, "adjust_quota", "user", uint(id), req.Note)
	json.NewEncoder(w).Encode(map[string]interface{}{"balance_bytes": balance, "type": ledgerType})
}

func (h *Handler) GetBranding(w http.ResponseWriter, r *http.Request) {
	cfg, err := branding.Get(h.db)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	json.NewEncoder(w).Encode(cfg)
}

func (h *Handler) UpdateBranding(w http.ResponseWriter, r *http.Request) {
	var cfg branding.Config
	if err := json.NewDecoder(r.Body).Decode(&cfg); err != nil {
		http.Error(w, "invalid request", http.StatusBadRequest)
		return
	}
	if err := branding.Save(h.db, cfg); err != nil {
		if errors.Is(err, branding.ErrLogoTooLarge) || errors.Is(err, branding.ErrInvalidImage) {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	adminID := auth.GetAdminID(r.Context())
	h.audit(adminID, "update_branding", "setting", 0, "")
	json.NewEncoder(w).Encode(cfg)
}

// pushQuota tells the routers a user is currently online through to adopt a new
// balance. Without it the router keeps enforcing its cached figure until the
// next report, so a top-up would not restore service for up to a minute.
func (h *Handler) pushQuota(userID uint, balance int64) {
	var sessions []database.Session
	h.db.Where("user_id = ? AND active = ?", userID, true).Find(&sessions)

	for _, s := range sessions {
		h.db.Create(&database.RouterCommand{
			RouterID:       s.RouterID,
			Action:         "set_quota",
			MAC:            s.MAC,
			UserID:         userID,
			RemainingBytes: balance,
		})
	}
}

// KickUser ends a user's session immediately by queueing a deauth for the
// router they are on and closing the session record.
func (h *Handler) KickUser(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.ParseUint(r.PathValue("id"), 10, 64)
	adminID := auth.GetAdminID(r.Context())

	var sessions []database.Session
	h.db.Where("user_id = ? AND active = ?", uint(id), true).Find(&sessions)

	if len(sessions) == 0 {
		json.NewEncoder(w).Encode(map[string]interface{}{"ok": true, "kicked": 0})
		return
	}

	now := time.Now()
	for _, s := range sessions {
		h.db.Create(&database.RouterCommand{
			RouterID: s.RouterID,
			Action:   "deauth",
			MAC:      s.MAC,
			UserID:   uint(id),
		})
		h.db.Model(&database.Session{}).Where("id = ?", s.ID).
			Updates(map[string]interface{}{"active": false, "ended_at": now})
	}

	h.audit(adminID, "kick_user", "user", uint(id), "")
	json.NewEncoder(w).Encode(map[string]interface{}{"ok": true, "kicked": len(sessions)})
}

func (h *Handler) UpdateUserRate(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.ParseUint(r.PathValue("id"), 10, 64)
	var req struct {
		UploadRateKbps   int `json:"upload_rate_kbps"`
		DownloadRateKbps int `json:"download_rate_kbps"`
	}
	json.NewDecoder(r.Body).Decode(&req)

	h.db.Model(&database.User{}).Where("id = ?", id).Updates(map[string]interface{}{
		"upload_rate_kbps":   req.UploadRateKbps,
		"download_rate_kbps": req.DownloadRateKbps,
	})
	w.WriteHeader(http.StatusOK)
}

func (h *Handler) ListPlans(w http.ResponseWriter, r *http.Request) {
	var plans []database.Plan
	h.db.Order("sort_order asc, id asc").Find(&plans)
	json.NewEncoder(w).Encode(plans)
}

func (h *Handler) CreatePlan(w http.ResponseWriter, r *http.Request) {
	var plan database.Plan
	json.NewDecoder(r.Body).Decode(&plan)
	if plan.SortOrder <= 0 {
		var maxSort int
		h.db.Model(&database.Plan{}).Select("COALESCE(MAX(sort_order), 0)").Scan(&maxSort)
		plan.SortOrder = maxSort + 1
	}
	h.db.Create(&plan)
	json.NewEncoder(w).Encode(plan)
}

func (h *Handler) UpdatePlan(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.ParseUint(r.PathValue("id"), 10, 64)
	var plan database.Plan
	json.NewDecoder(r.Body).Decode(&plan)
	h.db.Model(&database.Plan{}).Where("id = ?", id).Updates(plan)
	w.WriteHeader(http.StatusOK)
}

func (h *Handler) DeletePlan(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.ParseUint(r.PathValue("id"), 10, 64)
	h.db.Delete(&database.Plan{}, id)
	w.WriteHeader(http.StatusOK)
}

func (h *Handler) ListAuditLogs(w http.ResponseWriter, r *http.Request) {
	var logs []database.AuditLog
	h.db.Order("id desc").Limit(200).Find(&logs)
	json.NewEncoder(w).Encode(logs)
}

func (h *Handler) UsageReport(w http.ResponseWriter, r *http.Request) {
	var records []database.UsageRecord
	h.db.Order("id desc").Limit(500).Find(&records)
	json.NewEncoder(w).Encode(records)
}

func (h *Handler) audit(adminID uint, action, targetType string, targetID uint, detail string) {
	h.db.Create(&database.AuditLog{
		AdminID:    &adminID,
		Action:     action,
		TargetType: targetType,
		TargetID:   targetID,
		Detail:     detail,
		CreatedAt:  time.Now(),
	})
}
