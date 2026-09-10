package config

import (
	"os"
	"strconv"
	"strings"
)

type Config struct {
	HTTPPort          int
	HTTPSPort         int
	TLSCert           string
	TLSKey            string
	DatabaseDSN       string
	RedisAddr         string
	JWTSecret         string
	FASKey              string
	AuthLogPath         string
	QuotaExpiryDays     int
	DefaultUploadRate   int
	DefaultDownloadRate int
	UserPortalURL       string
	UserWebDir          string
	AllowDeviceRegister bool
	DeviceRegisterToken string
}

func Load() *Config {
	loadDotEnv()

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
		UserPortalURL:       getEnv("USER_PORTAL_URL", ""),
		UserWebDir:          getEnv("USER_WEB_DIR", ""),
		AllowDeviceRegister: getEnv("ALLOW_DEVICE_REGISTER", "0") == "1",
		DeviceRegisterToken: getEnv("DEVICE_REGISTER_TOKEN", ""),
	}
}

func loadDotEnv() {
	for _, path := range []string{".env", "cloud/.env"} {
		data, err := os.ReadFile(path)
		if err != nil {
			continue
		}
		for _, line := range strings.Split(string(data), "\n") {
			line = strings.TrimSpace(line)
			if line == "" || strings.HasPrefix(line, "#") {
				continue
			}
			key, value, ok := strings.Cut(line, "=")
			if !ok {
				continue
			}
			key = strings.TrimSpace(key)
			value = strings.Trim(strings.TrimSpace(value), `"'`)
			if key == "" || os.Getenv(key) != "" {
				continue
			}
			os.Setenv(key, value)
		}
		return
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
