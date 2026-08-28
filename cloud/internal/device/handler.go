package device

import (
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"github.com/nds-billing/cloud/internal/database"
	"github.com/nds-billing/cloud/internal/ledger"
	"golang.org/x/crypto/bcrypt"
	"gorm.io/gorm"
)

type Handler struct {
	db     *gorm.DB
	ledger *ledger.Service
}

func NewHandler(db *gorm.DB) *Handler {
	return &Handler{db: db, ledger: ledger.New(db)}
}

type reportRequest struct {
	Reports []reportItem `json:"reports"`
}

type reportItem struct {
	SessionKey string `json:"session_key"`
	Seq        int64  `json:"seq"`
	MAC        string `json:"mac"`
	IP         string `json:"ip"`
	DeltaBytes int64  `json:"delta_bytes"`
	TotalBytes int64  `json:"total_bytes"`
	Timestamp  int64  `json:"timestamp"`
}

type reportResponse struct {
	OK           bool                   `json:"ok"`
	QuotaUpdates []quotaUpdate          `json:"quota_updates,omitempty"`
}

type quotaUpdate struct {
	MAC             string `json:"mac"`
	UserID          uint   `json:"user_id"`
	RemainingBytes  int64  `json:"remaining_bytes"`
}

type heartbeatRequest struct {
	DeviceID string `json:"device_id"`
	Uptime   int64  `json:"uptime"`
	Online   bool   `json:"online"`
}

type command struct {
	Action          string `json:"action"`
	MAC             string `json:"mac,omitempty"`
	UserID          uint   `json:"user_id,omitempty"`
	RemainingBytes  int64  `json:"remaining_bytes,omitempty"`
}

type heartbeatResponse struct {
	OK       bool      `json:"ok"`
	Commands []command `json:"commands,omitempty"`
}

func (h *Handler) authenticate(r *http.Request) (*database.Router, bool) {
	deviceID := r.Header.Get("X-Device-ID")
	secret := r.Header.Get("X-Device-Secret")
	if deviceID == "" || secret == "" {
		return nil, false
	}
	var router database.Router
	if err := h.db.Where("device_id = ?", deviceID).First(&router).Error; err != nil {
		return nil, false
	}
	if err := bcrypt.CompareHashAndPassword([]byte(router.SecretHash), []byte(secret)); err != nil {
		return nil, false
	}
	return &router, true
}

func (h *Handler) HandleReport(w http.ResponseWriter, r *http.Request) {
	router, ok := h.authenticate(r)
	if !ok {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}

	var req reportRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		var single reportItem
		if err2 := json.Unmarshal([]byte(r.URL.Query().Get("body")), &single); err2 != nil {
			http.Error(w, "invalid request", http.StatusBadRequest)
			return
		}
		req.Reports = []reportItem{single}
	}

	var quotaUpdates []quotaUpdate

	for _, rep := range req.Reports {
		var existing database.UsageRecord
		err := h.db.Where("session_key = ? AND seq = ?", rep.SessionKey, rep.Seq).First(&existing).Error
		if err == nil {
			continue // idempotent skip
		}

		h.db.Create(&database.UsageRecord{
			SessionKey: rep.SessionKey,
			Seq:        rep.Seq,
			MAC:        strings.ToLower(rep.MAC),
			DeltaBytes: rep.DeltaBytes,
			TotalBytes: rep.TotalBytes,
			RecordedAt: time.Now(),
		})

		var device database.UserDevice
		if err := h.db.Where("mac = ?", strings.ToLower(rep.MAC)).First(&device).Error; err == nil {
			balance, err := h.ledger.Consume(device.UserID, rep.DeltaBytes, rep.SessionKey)
			if err == nil {
				quotaUpdates = append(quotaUpdates, quotaUpdate{
					MAC:            rep.MAC,
					UserID:         device.UserID,
					RemainingBytes: balance,
				})
			}
		}
	}

	now := time.Now()
	h.db.Model(router).Updates(map[string]interface{}{"online": true, "last_heartbeat": now})

	json.NewEncoder(w).Encode(reportResponse{OK: true, QuotaUpdates: quotaUpdates})
}

func (h *Handler) HandleHeartbeat(w http.ResponseWriter, r *http.Request) {
	router, ok := h.authenticate(r)
	if !ok {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}

	now := time.Now()
	h.db.Model(router).Updates(map[string]interface{}{"online": true, "last_heartbeat": now})

	json.NewEncoder(w).Encode(heartbeatResponse{OK: true})
}

func (h *Handler) Register(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Name     string `json:"name"`
		DeviceID string `json:"device_id"`
		Secret   string `json:"secret"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid request", http.StatusBadRequest)
		return
	}

	hash, _ := bcrypt.GenerateFromPassword([]byte(req.Secret), bcrypt.DefaultCost)
	router := database.Router{
		DeviceID:   req.DeviceID,
		Name:       req.Name,
		SecretHash: string(hash),
	}
	if err := h.db.Create(&router).Error; err != nil {
		http.Error(w, "registration failed", http.StatusConflict)
		return
	}

	json.NewEncoder(w).Encode(map[string]interface{}{"ok": true, "id": router.ID})
}
