package main

import (
	"fmt"
	"log"
	"os"

	"github.com/nds-billing/cloud/internal/config"
	"github.com/nds-billing/cloud/internal/database"
	"golang.org/x/crypto/bcrypt"
)

func main() {
	cfg := config.Load()
	db, err := database.Connect(cfg.DatabaseDSN)
	if err != nil {
		log.Fatal(err)
	}
	if err := database.Migrate(db); err != nil {
		log.Fatal(err)
	}

	hash, _ := bcrypt.GenerateFromPassword([]byte("admin123"), bcrypt.DefaultCost)
	admin := database.Admin{Username: "admin", PasswordHash: string(hash), Role: "admin"}
	result := db.Where("username = ?", "admin").FirstOrCreate(&admin)
	if result.Error != nil {
		log.Fatal(result.Error)
	}

	db.Where(database.Setting{Key: "quota_expiry_days"}).FirstOrCreate(&database.Setting{
		Key: "quota_expiry_days", Value: "90",
	})

	fmt.Println("Seed complete:")
	fmt.Println("  Admin: admin / admin123")
	fmt.Println("  Database:", os.Getenv("DATABASE_DSN"))
}
