package service

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
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
	ErrArgumentNull       = errors.New("argument cannot be null")
	ErrCreateRequest      = errors.New("failed to create req")
	ErrAgentService       = errors.New("agent service error")
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

// chat module
type ChatRequest struct {
	ID       uint   `json:"id"`
	ThreadID string `json:"thread_id"`
	Query    string `json:"query"`
}

type ChatResponse struct {
	Reason string   `json:"reason"`
	Answer string   `json:"answer"`
	Source []string `json:"source"`
}

func (s *Service) ChatWithAgent(ctx context.Context, req *ChatRequest) (string, error) {
	if req.Query == "" {
		return "", ErrArgumentNull
	}

	if err := s.repo.UpsertCheckpoint(&model.Checkpoint{
		ID:        req.ID,
		ThreadID:  req.ThreadID,
		Title:     req.Query,
		SampledAt: time.Now(),
	}); err != nil {
		return "", fmt.Errorf("failed to upsert checkpoint: %w", err)
	}

	body, err := json.Marshal(req)
	if err != nil {
		return "", fmt.Errorf("failed to marshal request: %w", err)
	}

	httpCtx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()

	http_req, err := http.NewRequestWithContext(httpCtx, "POST", "http://localhost:8000/chat", bytes.NewReader(body))
	if err != nil {
		return "", fmt.Errorf("failed to create request: %w", err)
	}
	http_req.Header.Set("Content-Type", "application/json")

	client := &http.Client{}

	resp, err := client.Do(http_req)
	if err != nil {
		return "", fmt.Errorf("agent service error: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("agent service returned status %d: %s", resp.StatusCode, string(body))
	}

	var chatresp ChatResponse
	if err := json.NewDecoder(resp.Body).Decode(&chatresp); err != nil {
		return "", fmt.Errorf("failed to decode response: %w, body: %s", err, string(chatresp.Answer))
	}

	return chatresp.Answer, nil
}
