package config

import (
	"os"
	"strconv"
)

type Config struct {
	HTTPPort          int
	HTTPSPort         int
	TLSCert           string
	TLSKey            string
	DatabaseDSN       string
	RedisAddr         string
	JWTSecret         string
	FASKey            string
	AuthLogPath       string
	QuotaExpiryDays   int
	DefaultUploadRate int
	DefaultDownloadRate int
}

func Load() *Config {
	return &Config{
		HTTPPort:            getEnvInt("HTTP_PORT", 8080),
		HTTPSPort:           getEnvInt("HTTPS_PORT", 8443),
		TLSCert:             os.Getenv("TLS_CERT"),
		TLSKey:              os.Getenv("TLS_KEY"),
		DatabaseDSN:         getEnv("DATABASE_DSN", "nds:nds123@tcp(localhost:3306)/nds_billing?charset=utf8mb4&parseTime=True&loc=Local"),
		RedisAddr:           getEnv("REDIS_ADDR", "localhost:6379"),
		JWTSecret:           getEnv("JWT_SECRET", "change-me-in-production"),
		FASKey:              getEnv("FAS_KEY", "nds-billing-fas-key"),
		AuthLogPath:         getEnv("AUTH_LOG_PATH", "./data/auth_queue"),
		QuotaExpiryDays:     getEnvInt("QUOTA_EXPIRY_DAYS", 90),
		DefaultUploadRate:   getEnvInt("DEFAULT_UPLOAD_RATE", 0),
		DefaultDownloadRate: getEnvInt("DEFAULT_DOWNLOAD_RATE", 0),
	}
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func getEnvInt(key string, fallback int) int {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return fallback
}
