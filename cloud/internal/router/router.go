package router

import (
	"encoding/json"
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/go-chi/cors"
	"github.com/nds-billing/cloud/internal/admin"
	"github.com/nds-billing/cloud/internal/auth"
	"github.com/nds-billing/cloud/internal/config"
	"github.com/nds-billing/cloud/internal/device"
	"github.com/nds-billing/cloud/internal/fas"
	"github.com/nds-billing/cloud/internal/userapi"
	"github.com/nds-billing/cloud/internal/voucher"
	"gorm.io/gorm"
)

func New(db *gorm.DB, cfg *config.Config) http.Handler {
	r := chi.NewRouter()
	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)
	r.Use(cors.Handler(cors.Options{
		AllowedOrigins:   []string{"*"},
		AllowedMethods:   []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowedHeaders:   []string{"Accept", "Authorization", "Content-Type", "X-Device-ID", "X-Device-Secret"},
		AllowCredentials: true,
	}))

	jwtSvc := auth.NewJWTService(cfg.JWTSecret)
	fasHandler := fas.NewHandler(db, cfg)
	deviceHandler := device.NewHandler(db)
	adminHandler := admin.NewHandler(db, jwtSvc)
	userHandler := userapi.NewHandler(db, jwtSvc)
	voucherSvc := voucher.New(db)

	// FAS portal (openNDS level 4)
	r.Get("/fas", fasHandler.HandleFAS)
	r.Post("/fas", fasHandler.HandleFAS)

	// Device API
	r.Route("/api/v1/device", func(r chi.Router) {
		r.Post("/register", deviceHandler.Register)
		r.Post("/report", deviceHandler.HandleReport)
		r.Post("/heartbeat", deviceHandler.HandleHeartbeat)
	})

	// Admin API
	r.Route("/api/v1/admin", func(r chi.Router) {
		r.Post("/login", adminHandler.HandleLogin)
		r.Group(func(r chi.Router) {
			r.Use(auth.AdminMiddleware(jwtSvc))
			r.Get("/routers", adminHandler.ListRouters)
			r.Get("/users", adminHandler.ListUsers)
			r.Post("/users/{id}/quota", adminHandler.AdjustQuota)
			r.Put("/users/{id}/rate", adminHandler.UpdateUserRate)
			r.Post("/users/{id}/kick", adminHandler.KickUser)
			r.Get("/plans", adminHandler.ListPlans)
			r.Post("/plans", adminHandler.CreatePlan)
			r.Put("/plans/{id}", adminHandler.UpdatePlan)
			r.Delete("/plans/{id}", adminHandler.DeletePlan)
			r.Get("/audit-logs", adminHandler.ListAuditLogs)
			r.Get("/usage", adminHandler.UsageReport)
			r.Post("/vouchers/batch", func(w http.ResponseWriter, req *http.Request) {
				var body struct {
					Name      string `json:"name"`
					TrafficMB int64  `json:"traffic_mb"`
					Count     int    `json:"count"`
				}
				json.NewDecoder(req.Body).Decode(&body)
				adminID := auth.GetAdminID(req.Context())
				result, err := voucherSvc.CreateBatch(body.Name, body.TrafficMB, body.Count, adminID)
				if err != nil {
					http.Error(w, err.Error(), http.StatusInternalServerError)
					return
				}
				json.NewEncoder(w).Encode(result)
			})
			r.Get("/vouchers/batches", func(w http.ResponseWriter, req *http.Request) {
				batches, _ := voucherSvc.ListBatches()
				json.NewEncoder(w).Encode(batches)
			})
			r.Get("/vouchers/batch/{id}", func(w http.ResponseWriter, req *http.Request) {
				id, _ := strconv.ParseUint(chi.URLParam(req, "id"), 10, 64)
				vouchers, _ := voucherSvc.ListByBatch(uint(id))
				json.NewEncoder(w).Encode(vouchers)
			})
		})
	})

	// User API
	r.Route("/api/v1/user", func(r chi.Router) {
		r.Post("/login", userHandler.HandleLogin)
		r.Post("/register", userHandler.HandleRegister)
		r.Group(func(r chi.Router) {
			r.Use(auth.UserMiddleware(jwtSvc))
			r.Get("/profile", userHandler.GetProfile)
			r.Get("/devices", userHandler.GetDevices)
			r.Get("/usage", userHandler.GetUsage)
			r.Post("/redeem", userHandler.RedeemVoucher)
			r.Get("/plans", userHandler.ListPlans)
		})
	})

	r.Get("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"status":"ok"}`))
	})

	return r
}
