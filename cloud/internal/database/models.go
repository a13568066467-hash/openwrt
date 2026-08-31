package database

import (
	"time"

	"gorm.io/gorm"
)

func Migrate(db *gorm.DB) error {
	if err := db.AutoMigrate(
		&Router{},
		&RouterCommand{},
		&User{},
		&UserDevice{},
		&Session{},
		&UsageRecord{},
		&QuotaLedger{},
		&Plan{},
		&VoucherBatch{},
		&Voucher{},
		&Admin{},
		&AuditLog{},
		&Setting{},
		&Payment{},
	); err != nil {
		return err
	}
	// 历史套餐：用 id 作为默认排序，保证套餐一、二、三…顺序
	return db.Exec("UPDATE plans SET sort_order = id WHERE sort_order = 0").Error
}

type Router struct {
	ID           uint      `gorm:"primaryKey" json:"id"`
	DeviceID     string    `gorm:"uniqueIndex;size:64" json:"device_id"`
	Name         string    `gorm:"size:128" json:"name"`
	SecretHash   string    `gorm:"size:128" json:"-"`
	GroupName    string    `gorm:"size:64" json:"group_name"`
	Online       bool      `json:"online"`
	LastHeartbeat *time.Time `json:"last_heartbeat"`
	CreatedAt    time.Time `json:"created_at"`
	UpdatedAt    time.Time `json:"updated_at"`
}

// RouterCommand is an instruction queued for a router to collect on its next
// heartbeat. Routers poll rather than being pushed to, because they normally
// sit behind NAT with no reachable inbound address.
type RouterCommand struct {
	ID             uint       `gorm:"primaryKey" json:"id"`
	RouterID       uint       `gorm:"index:idx_router_pending" json:"router_id"`
	Action         string     `gorm:"size:32" json:"action"`
	MAC            string     `gorm:"size:17" json:"mac,omitempty"`
	UserID         uint       `json:"user_id,omitempty"`
	RemainingBytes int64      `json:"remaining_bytes,omitempty"`
	Delivered      bool       `gorm:"index:idx_router_pending" json:"delivered"`
	DeliveredAt    *time.Time `json:"delivered_at"`
	CreatedAt      time.Time  `json:"created_at"`
}

type User struct {
	ID                   uint       `gorm:"primaryKey" json:"id"`
	Username             string     `gorm:"uniqueIndex;size:64" json:"username"`
	PasswordHash         string     `gorm:"size:128" json:"-"`
	QuotaRemainingBytes  int64      `json:"quota_remaining_bytes"`
	UploadRateKbps       int        `json:"upload_rate_kbps"`
	DownloadRateKbps     int        `json:"download_rate_kbps"`
	QuotaExpiresAt       *time.Time `json:"quota_expires_at"`
	Status               string     `gorm:"size:16;default:active" json:"status"`
	CreatedAt            time.Time  `json:"created_at"`
	UpdatedAt            time.Time  `json:"updated_at"`
}

type UserDevice struct {
	ID        uint      `gorm:"primaryKey" json:"id"`
	UserID    uint      `gorm:"index" json:"user_id"`
	MAC       string    `gorm:"index;size:17" json:"mac"`
	FirstSeen time.Time `json:"first_seen"`
	LastSeen  time.Time `json:"last_seen"`
}

type Session struct {
	ID            uint       `gorm:"primaryKey" json:"id"`
	SessionKey    string     `gorm:"uniqueIndex;size:256" json:"session_key"`
	UserID        uint       `gorm:"index" json:"user_id"`
	RouterID      uint       `gorm:"index" json:"router_id"`
	MAC           string     `gorm:"size:17" json:"mac"`
	IP            string     `gorm:"size:45" json:"ip"`
	StartedAt     time.Time  `json:"started_at"`
	EndedAt       *time.Time `json:"ended_at"`
	UploadBytes   int64      `json:"upload_bytes"`
	DownloadBytes int64      `json:"download_bytes"`
	Active        bool       `gorm:"index" json:"active"`
}

type UsageRecord struct {
	ID           uint      `gorm:"primaryKey" json:"id"`
	SessionKey   string    `gorm:"index:idx_session_seq,unique;size:256" json:"session_key"`
	Seq          int64     `gorm:"index:idx_session_seq,unique" json:"seq"`
	MAC          string    `gorm:"size:17" json:"mac"`
	DeltaBytes   int64     `json:"delta_bytes"`
	TotalBytes   int64     `json:"total_bytes"`
	RecordedAt   time.Time `json:"recorded_at"`
}

type QuotaLedger struct {
	ID            uint      `gorm:"primaryKey" json:"id"`
	UserID        uint      `gorm:"index" json:"user_id"`
	Type          string    `gorm:"size:32" json:"type"`
	AmountBytes   int64     `json:"amount_bytes"`
	BalanceAfter  int64     `json:"balance_after"`
	Reference     string    `gorm:"size:128" json:"reference"`
	OperatorID    *uint     `json:"operator_id"`
	Note          string    `gorm:"size:256" json:"note"`
	CreatedAt     time.Time `json:"created_at"`
}

type Plan struct {
	ID               uint      `gorm:"primaryKey" json:"id"`
	Name             string    `gorm:"size:128" json:"name"`
	TrafficMB        int64     `json:"traffic_mb"`
	PriceCents       int64     `json:"price_cents"`
	UploadRateKbps   int       `json:"upload_rate_kbps"`
	DownloadRateKbps int       `json:"download_rate_kbps"`
	SortOrder        int       `gorm:"default:0" json:"sort_order"`
	Active           bool      `gorm:"default:true" json:"active"`
	CreatedAt        time.Time `json:"created_at"`
	UpdatedAt        time.Time `json:"updated_at"`
}

type VoucherBatch struct {
	ID          uint      `gorm:"primaryKey" json:"id"`
	Name        string    `gorm:"size:128" json:"name"`
	TrafficMB   int64     `json:"traffic_mb"`
	Count       int       `json:"count"`
	ValidDays   int       `gorm:"default:90" json:"valid_days"`
	CodesJSON   string    `gorm:"type:mediumtext" json:"-"`
	CreatedBy   uint      `json:"created_by"`
	CreatedAt   time.Time `json:"created_at"`
}

type Voucher struct {
	ID         uint       `gorm:"primaryKey" json:"id"`
	BatchID    uint       `gorm:"index" json:"batch_id"`
	CodeHash   string     `gorm:"uniqueIndex;size:128" json:"-"`
	Status     string     `gorm:"size:16;default:unused" json:"status"`
	RedeemedBy *uint      `json:"redeemed_by"`
	RedeemedAt *time.Time `json:"redeemed_at"`
	CreatedAt  time.Time  `json:"created_at"`
}

type Admin struct {
	ID           uint      `gorm:"primaryKey" json:"id"`
	Username     string    `gorm:"uniqueIndex;size:64" json:"username"`
	PasswordHash string    `gorm:"size:128" json:"-"`
	Role         string    `gorm:"size:32;default:admin" json:"role"`
	CreatedAt    time.Time `json:"created_at"`
}

type AuditLog struct {
	ID         uint      `gorm:"primaryKey" json:"id"`
	AdminID    *uint     `json:"admin_id"`
	Action     string    `gorm:"size:64" json:"action"`
	TargetType string    `gorm:"size:32" json:"target_type"`
	TargetID   uint      `json:"target_id"`
	Detail     string    `gorm:"type:text" json:"detail"`
	CreatedAt  time.Time `json:"created_at"`
}

type Setting struct {
	ID    uint   `gorm:"primaryKey" json:"id"`
	Key   string `gorm:"uniqueIndex;size:64" json:"key"`
	Value string `gorm:"type:mediumtext" json:"value"`
}

type Payment struct {
	ID        uint      `gorm:"primaryKey" json:"id"`
	UserID    uint      `gorm:"index" json:"user_id"`
	Provider  string    `gorm:"size:32" json:"provider"`
	AmountCents int64   `json:"amount_cents"`
	Status    string    `gorm:"size:16" json:"status"`
	Reference string    `gorm:"size:128" json:"reference"`
	CreatedAt time.Time `json:"created_at"`
}
