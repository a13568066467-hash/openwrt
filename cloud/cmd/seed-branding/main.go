package main

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"path/filepath"

	"github.com/nds-billing/cloud/internal/branding"
	"github.com/nds-billing/cloud/internal/config"
	"github.com/nds-billing/cloud/internal/database"
)

func main() {
	logoPath := filepath.Join("..", "admin-web", "public", "nds-logo.png")
	if len(os.Args) > 1 {
		logoPath = os.Args[1]
	}

	raw, err := os.ReadFile(logoPath)
	if err != nil {
		log.Fatal(err)
	}
	fmt.Printf("logo file: %d bytes\n", len(raw))

	dataURL := "data:image/png;base64," + base64.StdEncoding.EncodeToString(raw)
	fmt.Printf("data URL: %d bytes\n", len(dataURL))

	cfg := config.Load()
	db, err := database.Connect(cfg.DatabaseDSN)
	if err != nil {
		log.Fatal(err)
	}
	if err := database.Migrate(db); err != nil {
		log.Fatal(err)
	}

	brandingCfg := branding.Config{
		SiteTitle:  "NDS 管理菜单",
		LoginTitle: "NDS 管理平台",
		AdminLogo:  dataURL,
		UserLogo:   dataURL,
	}
	if err := branding.Save(db, brandingCfg); err != nil {
		log.Fatal(err)
	}

	out, _ := json.MarshalIndent(brandingCfg, "", "  ")
	fmt.Println("saved branding:")
	fmt.Println(string(out[:min(200, len(out))]), "...")
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
