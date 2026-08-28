package admin

import (
	"encoding/json"
	"net/http"
	"strconv"
	"time"

	"github.com/nds-billing/cloud/internal/auth"
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

	h.audit(adminID, "adjust_quota", "user", uint(id), req.Note)
	json.NewEncoder(w).Encode(map[string]interface{}{"balance_bytes": balance, "type": ledgerType})
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
	h.db.Find(&plans)
	json.NewEncoder(w).Encode(plans)
}

func (h *Handler) CreatePlan(w http.ResponseWriter, r *http.Request) {
	var plan database.Plan
	json.NewDecoder(r.Body).Decode(&plan)
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
