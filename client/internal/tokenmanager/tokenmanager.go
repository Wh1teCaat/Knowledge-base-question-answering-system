package tokenmanager

import (
	"context"
	"log"
	"sync"
	"time"

	"github.com/Wh1teCaat/multi-agent/proto"
)

type TokenManager struct {
	mu           sync.RWMutex
	accessToken  string
	refreshToken string
	expiresAt    int64
}

func NewTokenManager(accessToken string, refreshToken string, expiresAt int64) *TokenManager {
	return &TokenManager{
		accessToken:  accessToken,
		refreshToken: refreshToken,
		expiresAt:    expiresAt,
	}
}

func (tm *TokenManager) GetAccessToken() string {
	tm.mu.RLock()
	defer tm.mu.RUnlock()
	return tm.accessToken
}

func (tm *TokenManager) GetRefreshToken() string {
	tm.mu.RLock()
	defer tm.mu.RUnlock()
	return tm.refreshToken
}

func (tm *TokenManager) GetExpiresAt() int64 {
	tm.mu.RLock()
	defer tm.mu.RUnlock()
	return tm.expiresAt
}

func (tm *TokenManager) UpdateTokens(accessToken string, refreshToken string, expiresAt int64) {
	tm.mu.Lock()
	defer tm.mu.Unlock()
	tm.accessToken = accessToken
	tm.refreshToken = refreshToken
	tm.expiresAt = expiresAt
}

// 启动一个 goroutine 定时刷新 token
func (tm *TokenManager) StartTokenRefresher(userClient proto.UserServiceClient) {
	go func() {
		for {
			expiresIn := time.Unix(tm.GetExpiresAt(), 0)
			sleepTime := time.Until(expiresIn.Add(-1 * time.Minute))

			// 过期直接刷新
			if sleepTime > 0 {
				time.Sleep(sleepTime)
			}

			log.Println("🎈 Access token is about to expire, refreshing...")

			refreshToken := tm.GetRefreshToken()
			if refreshToken == "" {
				log.Println("No refresh token available, cannot refresh access token")
				return
			}

			log.Println("🔄 Refreshing access token...")

			resp, err := userClient.RefreshToken(context.Background(), &proto.RefreshTokenReq{RefreshToken: refreshToken})
			if err != nil {
				log.Printf("Failed to refresh: %v", err)
				return
			}
			tm.UpdateTokens(resp.AccessToken, resp.RefreshToken, resp.ExpiresAt)
		}
	}()
}
