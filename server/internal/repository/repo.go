package repository

import (
	"github.com/Wh1teCaat/multi-agent/server/internal/model"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

type Repository struct {
	DB *gorm.DB
}

func NewRepository(db *gorm.DB) *Repository {
	return &Repository{DB: db}
}

func (r *Repository) Register(user *model.User) error {
	return r.DB.Create(user).Error
}

func (r *Repository) GetUserByUsername(username string) (*model.User, error) {
	var user model.User
	err := r.DB.Where("username = ?", username).First(&user).Error
	if err != nil {
		return nil, err
	}
	return &user, nil
}

func (r *Repository) UpdateRefreshToken(userID uint, refreshToken string) error {
	return r.DB.Model(&model.User{}).Where("id = ?", userID).Update("refresh_token", refreshToken).Error
}

func (r *Repository) VerifyRefreshToken(userID uint, refreshToken string) error {
	return r.DB.First(&model.User{}, "id = ? AND refresh_token = ?", userID, refreshToken).Error
}

func (r *Repository) UpsertCheckpoint(checkpoint *model.Checkpoint) error {
	return r.DB.Clauses(clause.OnConflict{
		Columns:   []clause.Column{{Name: "id"}, {Name: "thread_id"}},
		DoUpdates: clause.AssignmentColumns([]string{"sampled_at"}),
	}).Create(checkpoint).Error
}
