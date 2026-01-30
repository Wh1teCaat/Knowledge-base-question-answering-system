package model

import "gorm.io/gorm"

type User struct {
	gorm.Model
	Username     string `gorm:"size:25;uniqueIndex;not null" json:"username"`
	Password     string `gorm:"size:255;not null" json:"-"`
	Email        string `gorm:"uniqueIndex;not null" json:"email"`
	RefreshToken string `gorm:"size:512" json:"refresh_token"`
}

type Checkpoint struct {
	ID       uint   `gorm:"primaryKey" json:"id"`
	Username string `gorm:"uniqueIndex;not null" json:"username"`
	ThreadID string `gorm:"not null" json:"thread_id"`

	User User `gorm:"foreignKey:Username;references:Username;"`
}
