package database

import (
	"log"

	"github.com/Wh1teCaat/multi-agent/internal/model"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
)

func InitDB(dsn string) (*gorm.DB, error) {
	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{})
	if err != nil {
		log.Fatalf("🚒 failed to connect database: %v", err)
		return nil, err
	}

	log.Println("Starting database migration...")
	// 先迁移 User 表，再迁移 Checkpoint 表，避免外键约束问题
	err = db.AutoMigrate(&model.User{})
	if err != nil {
		log.Fatalf("🚒 failed to migrate User table: %v", err)
		return nil, err
	}

	err = db.AutoMigrate(&model.Checkpoint{})
	if err != nil {
		log.Fatalf("🚒 failed to migrate Checkpoint table: %v", err)
		return nil, err
	}
	log.Println("✅ Database migration completed.")

	return db, nil
}
