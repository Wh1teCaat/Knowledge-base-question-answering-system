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

	"github.com/Wh1teCaat/multi-agent/server/internal/auth"
	"github.com/Wh1teCaat/multi-agent/server/internal/model"
	"github.com/Wh1teCaat/multi-agent/server/internal/repository"
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
	repo *repository.Repository
}

func NewService(repo *repository.Repository) *Service {
	return &Service{repo: repo}
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

	access_token, expiresAt, err := auth.GenerateAccessToken(user.ID, user.Username)
	if err != nil {
		return "", "", 0, fmt.Errorf("failed to generate access token: %w", err)
	}

	refresh_token, err := auth.GenerateRefreshToken(user.ID, user.Username)
	if err != nil {
		return "", "", 0, fmt.Errorf("failed to generate refresh token: %w", err)
	}

	if err := s.repo.UpdateRefreshToken(user.ID, refresh_token); err != nil {
		return "", "", 0, fmt.Errorf("failed to update refresh token: %w", err)
	}

	return access_token, refresh_token, expiresAt, nil
}

func (s *Service) RefreshAccessToken(refreshToken string) (string, int64, error) {
	// 验证刷新令牌
	claims, err := auth.ValidateToken(refreshToken)
	if err != nil {
		return "", 0, err
	}

	// 验证刷新令牌是否与数据库中的匹配
	if err := s.repo.VerifyRefreshToken(claims.UserID, refreshToken); err != nil {
		return "", 0, ErrInvalidCredentials
	}

	return auth.GenerateAccessToken(claims.UserID, claims.Username)
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
