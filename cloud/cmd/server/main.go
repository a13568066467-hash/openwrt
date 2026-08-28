package main

import (
	"context"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/nds-billing/cloud/internal/config"
	"github.com/nds-billing/cloud/internal/cron"
	"github.com/nds-billing/cloud/internal/database"
	"github.com/nds-billing/cloud/internal/router"
)

func main() {
	cfg := config.Load()

	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	slog.SetDefault(logger)

	db, err := database.Connect(cfg.DatabaseDSN)
	if err != nil {
		slog.Error("database connect failed", "error", err)
		os.Exit(1)
	}

	if err := database.Migrate(db); err != nil {
		slog.Error("database migrate failed", "error", err)
		os.Exit(1)
	}

	r := router.New(db, cfg)

	srv := &http.Server{
		Addr:         fmt.Sprintf(":%d", cfg.HTTPPort),
		Handler:      r,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 30 * time.Second,
	}

	go cron.Start(context.Background(), db, cfg)

	go func() {
		slog.Info("server starting", "port", cfg.HTTPPort)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			slog.Error("server error", "error", err)
			os.Exit(1)
		}
	}()

	if cfg.TLSCert != "" && cfg.TLSKey != "" {
		tlsSrv := &http.Server{
			Addr:         fmt.Sprintf(":%d", cfg.HTTPSPort),
			Handler:      r,
			ReadTimeout:  30 * time.Second,
			WriteTimeout: 30 * time.Second,
		}
		go func() {
			slog.Info("TLS server starting", "port", cfg.HTTPSPort)
			if err := tlsSrv.ListenAndServeTLS(cfg.TLSCert, cfg.TLSKey); err != nil && err != http.ErrServerClosed {
				slog.Error("TLS server error", "error", err)
			}
		}()
	}

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	_ = srv.Shutdown(ctx)
	slog.Info("server stopped")
}
