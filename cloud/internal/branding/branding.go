package branding

import (
	"errors"
	"strings"

	"github.com/nds-billing/cloud/internal/database"
	"gorm.io/gorm"
)

const maxLogoBytes = 1024 * 1024 // 1 MB source image
const maxDataURLLen = maxLogoBytes*4/3 + 4096 // base64 data URL overhead

var (
	ErrLogoTooLarge = errors.New("logo image too large (max 1MB)")
	ErrInvalidImage = errors.New("logo must be a PNG, JPEG, GIF or SVG data URL")
)

type Config struct {
	SiteTitle  string `json:"site_title"`
	AdminLogo  string `json:"admin_logo"`
	UserLogo   string `json:"user_logo"`
	LoginTitle string `json:"login_title"`
}

func defaultConfig() Config {
	return Config{
		SiteTitle:  "NDS 管理",
		LoginTitle: "NDS 管理面板",
	}
}

func Get(db *gorm.DB) (Config, error) {
	cfg := defaultConfig()
	var settings []database.Setting
	if err := db.Where("`key` LIKE ?", "branding_%").Find(&settings).Error; err != nil {
		return cfg, err
	}
	for _, s := range settings {
		switch s.Key {
		case "branding_site_title":
			cfg.SiteTitle = s.Value
		case "branding_login_title":
			cfg.LoginTitle = s.Value
		case "branding_admin_logo":
			cfg.AdminLogo = s.Value
		case "branding_user_logo":
			cfg.UserLogo = s.Value
		}
	}
	return cfg, nil
}

func Save(db *gorm.DB, cfg Config) error {
	if err := validateLogo(cfg.AdminLogo); err != nil {
		return err
	}
	if err := validateLogo(cfg.UserLogo); err != nil {
		return err
	}
	pairs := map[string]string{
		"branding_site_title":  strings.TrimSpace(cfg.SiteTitle),
		"branding_login_title": strings.TrimSpace(cfg.LoginTitle),
		"branding_admin_logo":  cfg.AdminLogo,
		"branding_user_logo":   cfg.UserLogo,
	}
	if pairs["branding_site_title"] == "" {
		pairs["branding_site_title"] = defaultConfig().SiteTitle
	}
	if pairs["branding_login_title"] == "" {
		pairs["branding_login_title"] = defaultConfig().LoginTitle
	}
	return db.Transaction(func(tx *gorm.DB) error {
		for key, value := range pairs {
			var s database.Setting
			err := tx.Where("`key` = ?", key).First(&s).Error
			if errors.Is(err, gorm.ErrRecordNotFound) {
				if err := tx.Create(&database.Setting{Key: key, Value: value}).Error; err != nil {
					return err
				}
				continue
			}
			if err != nil {
				return err
			}
			if err := tx.Model(&s).Update("value", value).Error; err != nil {
				return err
			}
		}
		return nil
	})
}

func validateLogo(dataURL string) error {
	if dataURL == "" {
		return nil
	}
	if len(dataURL) > maxDataURLLen {
		return ErrLogoTooLarge
	}
	if !strings.HasPrefix(dataURL, "data:image/png;") &&
		!strings.HasPrefix(dataURL, "data:image/jpeg;") &&
		!strings.HasPrefix(dataURL, "data:image/jpg;") &&
		!strings.HasPrefix(dataURL, "data:image/gif;") &&
		!strings.HasPrefix(dataURL, "data:image/svg+xml;") {
		return ErrInvalidImage
	}
	return nil
}
