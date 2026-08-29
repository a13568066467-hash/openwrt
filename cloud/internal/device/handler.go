package device

import (
	"encoding/json"
	"errors"
	"net/http"
	"strings"
	"time"

	"github.com/nds-billing/cloud/internal/database"
	"github.com/nds-billing/cloud/internal/ledger"
	"golang.org/x/crypto/bcrypt"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

// Routers authenticate with credentials carried in the request body rather
// than in headers: the agent falls back to uclient-fetch on minimal images,
// and uclient-fetch cannot set custom headers.
type credentials struct {
	DeviceID     string `json:"device_id"`
	DeviceSecret string `json:"device_secret"`
}

type Handler struct {
	db     *gorm.DB
	ledger *ledger.Service
}

func NewHandler(db *gorm.DB) *Handler {
	return &Handler{db: db, ledger: ledger.New(db)}
}

type reportItem struct {
	SessionKey    string `json:"session_key"`
	Seq           int64  `json:"seq"`
	MAC           string `json:"mac"`
	IP            string `json:"ip"`
	DownloadBytes int64  `json:"download_bytes"`
	UploadBytes   int64  `json:"upload_bytes"`
	DeltaBytes    int64  `json:"delta_bytes"`
	TotalBytes    int64  `json:"total_bytes"`
	Timestamp     int64  `json:"timestamp"`
}

type reportRequest struct {
	credentials
	Reports []reportItem `json:"reports"`
	Replay  bool         `json:"replay"`
}

type quotaUpdate struct {
	MAC            string `json:"mac"`
	UserID         uint   `json:"user_id"`
	RemainingBytes int64  `json:"remaining_bytes"`
}

type reportResponse struct {
	OK           bool          `json:"ok"`
	QuotaUpdates []quotaUpdate `json:"quota_updates,omitempty"`
	Commands     []command     `json:"commands,omitempty"`
}

type heartbeatRequest struct {
	credentials
	Uptime       int64  `json:"uptime"`
	Online       bool   `json:"online"`
	AgentVersion string `json:"agent_version"`
}

type command struct {
	Action         string `json:"action"`
	MAC            string `json:"mac,omitempty"`
	UserID         uint   `json:"user_id,omitempty"`
	RemainingBytes int64  `json:"remaining_bytes,omitempty"`
}

type heartbeatResponse struct {
	OK       bool      `json:"ok"`
	Commands []command `json:"commands,omitempty"`
}

var errUnauthorized = errors.New("unauthorized")

func (h *Handler) authenticate(creds credentials) (*database.Router, error) {
	if creds.DeviceID == "" || creds.DeviceSecret == "" {
		return nil, errUnauthorized
	}

	var router database.Router
	if err := h.db.Where("device_id = ?", creds.DeviceID).First(&router).Error; err != nil {
		return nil, errUnauthorized
	}

	if bcrypt.CompareHashAndPassword([]byte(router.SecretHash), []byte(creds.DeviceSecret)) != nil {
		return nil, errUnauthorized
	}

	return &router, nil
}

func (h *Handler) markSeen(router *database.Router) {
	now := time.Now()
	h.db.Model(router).Updates(map[string]any{"online": true, "last_heartbeat": now})
}

// resolveUser answers "who is spending this traffic". The active session for
// the reporting router is authoritative; the device binding is only a fallback
// for traffic that arrives before or after a session row exists, and a MAC can
// legitimately have been bound to several accounts over time.
func (h *Handler) resolveUser(routerID uint, mac string) (uint, bool) {
	var session database.Session
	err := h.db.Where("router_id = ? AND mac = ? AND active = ?", routerID, mac, true).
		Order("started_at desc").First(&session).Error
	if err == nil {
		return session.UserID, true
	}

	var binding database.UserDevice
	if h.db.Where("mac = ?", mac).Order("last_seen desc").First(&binding).Error == nil {
		return binding.UserID, true
	}

	return 0, false
}

// recordUsage stores one delta, returning false when the record was a
// duplicate. Idempotency is enforced by the unique (session_key, seq) index
// rather than a read-then-write check, which would race between replicas.
func (h *Handler) recordUsage(item reportItem, mac string) (bool, error) {
	record := database.UsageRecord{
		SessionKey: item.SessionKey,
		Seq:        item.Seq,
		MAC:        mac,
		DeltaBytes: item.DeltaBytes,
		TotalBytes: item.TotalBytes,
		RecordedAt: time.Now(),
	}

	result := h.db.Clauses(clause.OnConflict{DoNothing: true}).Create(&record)
	if result.Error != nil {
		return false, result.Error
	}

	return result.RowsAffected > 0, nil
}

func (h *Handler) HandleReport(w http.ResponseWriter, r *http.Request) {
	var req reportRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid request", http.StatusBadRequest)
		return
	}

	router, err := h.authenticate(req.credentials)
	if err != nil {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}

	// One update per MAC: several deltas for the same client in a single
	// batch must not send the router conflicting balances.
	balances := map[string]quotaUpdate{}

	for _, item := range req.Reports {
		mac := strings.ToLower(item.MAC)

		fresh, err := h.recordUsage(item, mac)
		if err != nil {
			http.Error(w, "storage failure", http.StatusInternalServerError)
			return
		}
		if !fresh {
			continue
		}

		userID, ok := h.resolveUser(router.ID, mac)
		if !ok {
			continue
		}

		h.db.Model(&database.Session{}).
			Where("router_id = ? AND mac = ? AND active = ?", router.ID, mac, true).
			Updates(map[string]any{
				"download_bytes": item.DownloadBytes,
				"upload_bytes":   item.UploadBytes,
			})

		balance, err := h.ledger.Consume(userID, item.DeltaBytes, item.SessionKey)
		if err != nil {
			continue
		}

		balances[mac] = quotaUpdate{MAC: mac, UserID: userID, RemainingBytes: balance}

		if balance <= 0 {
			h.enqueueDeauth(router.ID, mac, userID)
		}
	}

	updates := make([]quotaUpdate, 0, len(balances))
	for _, u := range balances {
		updates = append(updates, u)
	}

	h.markSeen(router)

	json.NewEncoder(w).Encode(reportResponse{
		OK:           true,
		QuotaUpdates: updates,
		Commands:     h.takeCommands(router.ID),
	})
}

func (h *Handler) HandleHeartbeat(w http.ResponseWriter, r *http.Request) {
	var req heartbeatRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid request", http.StatusBadRequest)
		return
	}

	router, err := h.authenticate(req.credentials)
	if err != nil {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}

	h.markSeen(router)

	json.NewEncoder(w).Encode(heartbeatResponse{
		OK:       true,
		Commands: h.takeCommands(router.ID),
	})
}

// takeCommands drains the pending queue for a router. Commands are marked
// delivered as they are handed over; the agent applies them idempotently, so
// losing a response costs at most a repeated deauth.
func (h *Handler) takeCommands(routerID uint) []command {
	var pending []database.RouterCommand
	if err := h.db.Where("router_id = ? AND delivered = ?", routerID, false).
		Order("id asc").Limit(50).Find(&pending).Error; err != nil || len(pending) == 0 {
		return nil
	}

	ids := make([]uint, 0, len(pending))
	out := make([]command, 0, len(pending))

	for _, p := range pending {
		ids = append(ids, p.ID)
		out = append(out, command{
			Action:         p.Action,
			MAC:            p.MAC,
			UserID:         p.UserID,
			RemainingBytes: p.RemainingBytes,
		})
	}

	now := time.Now()
	h.db.Model(&database.RouterCommand{}).Where("id IN ?", ids).
		Updates(map[string]any{"delivered": true, "delivered_at": now})

	return out
}

func (h *Handler) enqueueDeauth(routerID uint, mac string, userID uint) {
	var existing int64
	h.db.Model(&database.RouterCommand{}).
		Where("router_id = ? AND mac = ? AND action = ? AND delivered = ?",
			routerID, mac, "deauth", false).Count(&existing)
	if existing > 0 {
		return
	}

	h.db.Create(&database.RouterCommand{
		RouterID: routerID,
		Action:   "deauth",
		MAC:      mac,
		UserID:   userID,
	})
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

	if req.DeviceID == "" || len(req.Secret) < 16 {
		http.Error(w, "device_id and a secret of at least 16 characters are required",
			http.StatusBadRequest)
		return
	}

	hash, err := bcrypt.GenerateFromPassword([]byte(req.Secret), bcrypt.DefaultCost)
	if err != nil {
		http.Error(w, "registration failed", http.StatusInternalServerError)
		return
	}

	router := database.Router{
		DeviceID:   req.DeviceID,
		Name:       req.Name,
		SecretHash: string(hash),
	}
	if err := h.db.Create(&router).Error; err != nil {
		http.Error(w, "registration failed", http.StatusConflict)
		return
	}

	json.NewEncoder(w).Encode(map[string]any{"ok": true, "id": router.ID})
}
