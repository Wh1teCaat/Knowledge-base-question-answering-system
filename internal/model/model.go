package model

import (
	"time"

	"gorm.io/gorm"
)

type User struct {
	gorm.Model
	Username     string `gorm:"size:25;uniqueIndex;not null" json:"username"`
	Password     string `gorm:"size:255;not null" json:"-"`
	Email        string `gorm:"uniqueIndex;not null" json:"email"`
	RefreshToken string `gorm:"size:512" json:"refresh_token"`
}

type Checkpoint struct {
	ID        uint      `gorm:"primaryKey" json:"id"`
	ThreadID  string    `gorm:"primaryKey" json:"thread_id"`
	Title     string    `gorm:"size:255;not null" json:"title"`
	SampledAt time.Time `gorm:"not null" json:"sampled_at"`

	User User `gorm:"foreignKey:ID;references:ID;"`
}
