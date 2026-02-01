package main

import (
	"log"

	"github.com/Wh1teCaat/multi-agent/internal/config"
	"github.com/Wh1teCaat/multi-agent/internal/database"
	"github.com/Wh1teCaat/multi-agent/internal/repository"
	"github.com/Wh1teCaat/multi-agent/internal/service"
)

func main() {
	cfg, err := config.LoadConfig()
	if err != nil {
		log.Println("🚒 failed to load config:", err)
	}
	log.Println("Config loaded successfully:", cfg)

	db := database.InitDB(cfg.Database.DSN)
	repo := repository.NewRepository(db)
	svc := service.NewService(repo, cfg.Service.HS256_SECRET)

	// err = svc.Register("testuser", "testpassword", "testemail@example.com")
	// if err != nil {
	// 	log.Println("🚒 failed to register user:", err)
	// } else {
	// 	log.Println("✅ User registered successfully")
	// }

	_, _, _, err = svc.Login("testuser", "testpassword")
	if err != nil {
		log.Println("🚒 failed to login:", err)
	} else {
		log.Println("✅ User logged in successfully")
	}
}
