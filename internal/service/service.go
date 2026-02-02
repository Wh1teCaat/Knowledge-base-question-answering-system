package service

import (
	"errors"
	"fmt"
	"time"

	"github.com/Wh1teCaat/multi-agent/internal/model"
	"github.com/Wh1teCaat/multi-agent/internal/repository"
	"github.com/golang-jwt/jwt/v5"
	"golang.org/x/crypto/bcrypt"
	"gorm.io/gorm"
)

var (
	ErrEmptyFields        = errors.New("username, password, and email cannot be empty")
	ErrHashPassword       = errors.New("failed to hash password")
	ErrInvalidCredentials = errors.New("invalid username or password")
)

type Service struct {
	repo      *repository.Repository
	jwtSecret []byte
}

func NewService(repo *repository.Repository, jwtSecret string) *Service {
	return &Service{repo: repo, jwtSecret: []byte(jwtSecret)}
}

// JWT Claims
type Claims struct {
	UserID   uint
	Username string
	jwt.RegisteredClaims
}

// generate token
func (s *Service) GenerateAccessToken(userID uint, username string) (string, int64, error) {
	claims := &Claims{
		UserID:   userID,
		Username: username,
		RegisteredClaims: jwt.RegisteredClaims{
			IssuedAt:  jwt.NewNumericDate(time.Now()),
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(15 * time.Minute)),
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	tokenString, err := token.SignedString(s.jwtSecret)
	if err != nil {
		return "", 0, err
	}

	// 返回绝对过期时间戳
	expiresAt := claims.ExpiresAt.Time.Unix()
	return tokenString, expiresAt, nil
}

func (s *Service) GenerateRefreshToken(userID uint, username string) (string, error) {
	claims := &Claims{
		UserID:   userID,
		Username: username,
		RegisteredClaims: jwt.RegisteredClaims{
			IssuedAt:  jwt.NewNumericDate(time.Now()),
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(7 * 24 * time.Hour)),
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	return token.SignedString(s.jwtSecret)
}

func (s *Service) ValidateToken(tokenString string) (*Claims, error) {
	token, err := jwt.ParseWithClaims(tokenString, &Claims{}, func(token *jwt.Token) (interface{}, error) {
		if token.Method != jwt.SigningMethodHS256 {
			return nil, jwt.ErrTokenSignatureInvalid
		}
		return s.jwtSecret, nil
	})

	if err != nil {
		switch {
		case errors.Is(err, jwt.ErrTokenExpired):
			return nil, fmt.Errorf("token has expired")
		case errors.Is(err, jwt.ErrTokenSignatureInvalid):
			return nil, fmt.Errorf("invalid token signature")
		case errors.Is(err, jwt.ErrTokenMalformed):
			return nil, fmt.Errorf("malformed token")
		default:
			return nil, fmt.Errorf("failed to parse token: %w", err)
		}
	}

	if claims, ok := token.Claims.(*Claims); ok && token.Valid {
		return claims, nil
	}

	return nil, fmt.Errorf("invalid token")

}

func (s *Service) RefreshAccessToken(refreshToken string) (string, int64, error) {
	// varify refresh token
	claims, err := s.ValidateToken(refreshToken)
	if err != nil {
		return "", 0, fmt.Errorf("invalid refresh token: %w", err)
	}

	// Generate new access token
	newAccessToken, expiresAt, err := s.GenerateAccessToken(claims.UserID, claims.Username)
	if err != nil {
		return "", 0, fmt.Errorf("failed to generate access token: %w", err)
	}

	return newAccessToken, expiresAt, nil
}

func (s *Service) Register(username, password, email string) error {
	if username == "" || password == "" || email == "" {
		return ErrEmptyFields
	}

	hash_password, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	if err != nil {
		return ErrHashPassword
	}

	newUser := &model.User{
		Username: username,
		Password: string(hash_password),
		Email:    email,
	}

	if err := s.repo.Register(newUser); err != nil {
		switch {
		case errors.Is(err, gorm.ErrRegistered):
			return fmt.Errorf("username or email already exists: %w", err)
		default:
			return fmt.Errorf("failed to register user: %w", err)
		}
	}

	return nil
}

func (s *Service) Login(username, password string) (string, string, int64, error) {
	if username == "" || password == "" {
		return "", "", 0, ErrEmptyFields
	}

	user, err := s.repo.GetUserByUsername(username)
	if err != nil {
		return "", "", 0, ErrInvalidCredentials
	}

	// verify password
	if err := bcrypt.CompareHashAndPassword([]byte(user.Password), []byte(password)); err != nil {
		return "", "", 0, ErrInvalidCredentials
	}

	access_token, expiresAt, err := s.GenerateAccessToken(user.ID, user.Username)
	if err != nil {
		return "", "", 0, fmt.Errorf("failed to generate access token: %w", err)
	}

	refresh_token, err := s.GenerateRefreshToken(user.ID, user.Username)
	if err != nil {
		return "", "", 0, fmt.Errorf("failed to generate refresh token: %w", err)
	}

	if err := s.repo.UpdateRefreshToken(user.ID, refresh_token); err != nil {
		return "", "", 0, fmt.Errorf("failed to update refresh token: %w", err)
	}

	return access_token, refresh_token, expiresAt, nil
}
