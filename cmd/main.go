package main

import (
	"log"

	"github.com/Wh1teCaat/multi-agent/internal/config"
	"github.com/Wh1teCaat/multi-agent/internal/database"
)

func main() {
	cfg, err := config.LoadConfig()
	if err != nil {
		log.Println("🚒 failed to load config:", err)
	}
	log.Println("Config loaded successfully:", cfg)

	dsn := cfg.Database.DSN
	_, err = database.InitDB(dsn)
	if err != nil {
		log.Println("🚒 failed to initialize database:", err)
	}
	log.Println("Database initialized successfully:")
}
