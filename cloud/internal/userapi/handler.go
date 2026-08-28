package userapi

import (
	"encoding/json"
	"net/http"
	"time"

	"github.com/nds-billing/cloud/internal/auth"
	"github.com/nds-billing/cloud/internal/database"
	"github.com/nds-billing/cloud/internal/ledger"
	"github.com/nds-billing/cloud/internal/voucher"
	"golang.org/x/crypto/bcrypt"
	"gorm.io/gorm"
)

type Handler struct {
	db      *gorm.DB
	ledger  *ledger.Service
	jwt     *auth.JWTService
	voucher *voucher.Service
}

func NewHandler(db *gorm.DB, jwt *auth.JWTService) *Handler {
	return &Handler{
		db:      db,
		ledger:  ledger.New(db),
		jwt:     jwt,
		voucher: voucher.New(db),
	}
}

func (h *Handler) HandleLogin(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Username string `json:"username"`
		Password string `json:"password"`
	}
	json.NewDecoder(r.Body).Decode(&req)

	var user database.User
	if err := h.db.Where("username = ?", req.Username).First(&user).Error; err != nil {
		http.Error(w, "invalid credentials", http.StatusUnauthorized)
		return
	}
	if err := bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(req.Password)); err != nil {
		http.Error(w, "invalid credentials", http.StatusUnauthorized)
		return
	}

	token, _ := h.jwt.Generate(user.ID, "user")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"token": token,
		"user":  user,
	})
}

func (h *Handler) HandleRegister(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Username string `json:"username"`
		Password string `json:"password"`
	}
	json.NewDecoder(r.Body).Decode(&req)

	hash, _ := bcrypt.GenerateFromPassword([]byte(req.Password), bcrypt.DefaultCost)
	expires := time.Now().AddDate(0, 0, 90)
	user := database.User{
		Username:            req.Username,
		PasswordHash:        string(hash),
		QuotaRemainingBytes: 100 * 1024 * 1024,
		Status:              "active",
		QuotaExpiresAt:      &expires,
	}
	if err := h.db.Create(&user).Error; err != nil {
		http.Error(w, "username taken", http.StatusConflict)
		return
	}
	h.ledger.TopUp(user.ID, 100*1024*1024, "register_trial", "注册赠送", nil)

	token, _ := h.jwt.Generate(user.ID, "user")
	json.NewEncoder(w).Encode(map[string]interface{}{"token": token, "user": user})
}

func (h *Handler) GetProfile(w http.ResponseWriter, r *http.Request) {
	userID := auth.GetUserID(r.Context())
	var user database.User
	h.db.First(&user, userID)
	json.NewEncoder(w).Encode(user)
}

func (h *Handler) GetDevices(w http.ResponseWriter, r *http.Request) {
	userID := auth.GetUserID(r.Context())
	var devices []database.UserDevice
	h.db.Where("user_id = ?", userID).Find(&devices)
	json.NewEncoder(w).Encode(devices)
}

func (h *Handler) GetUsage(w http.ResponseWriter, r *http.Request) {
	userID := auth.GetUserID(r.Context())
	var devices []database.UserDevice
	h.db.Where("user_id = ?", userID).Find(&devices)

	var macs []string
	for _, d := range devices {
		macs = append(macs, d.MAC)
	}

	var records []database.UsageRecord
	if len(macs) > 0 {
		h.db.Where("mac IN ?", macs).Order("id desc").Limit(100).Find(&records)
	}
	json.NewEncoder(w).Encode(records)
}

func (h *Handler) RedeemVoucher(w http.ResponseWriter, r *http.Request) {
	userID := auth.GetUserID(r.Context())
	var req struct {
		Code string `json:"code"`
	}
	json.NewDecoder(r.Body).Decode(&req)

	balance, err := h.voucher.Redeem(req.Code, userID)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	json.NewEncoder(w).Encode(map[string]interface{}{"balance_bytes": balance})
}

func (h *Handler) ListPlans(w http.ResponseWriter, r *http.Request) {
	var plans []database.Plan
	h.db.Where("active = ?", true).Find(&plans)
	json.NewEncoder(w).Encode(plans)
}
