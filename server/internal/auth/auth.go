package auth

import (
	"errors"
	"fmt"
	"time"

	"github.com/Wh1teCaat/multi-agent/server/internal/config"
	"github.com/golang-jwt/jwt/v5"
)

// JWT Claims
type claims struct {
	UserID   uint
	Username string
	jwt.RegisteredClaims
}

var secret []byte

func LoadSecret(cfg *config.Config) error {
	if cfg == nil || cfg.Jwt.HS256_SECRET == "" {
		return fmt.Errorf("hs256 secret is empty")
	}
	secret = []byte(cfg.Jwt.HS256_SECRET)
	return nil
}

// generate token
func GenerateAccessToken(userID uint, username string) (string, int64, error) {
	claims := &claims{
		UserID:   userID,
		Username: username,
		RegisteredClaims: jwt.RegisteredClaims{
			IssuedAt:  jwt.NewNumericDate(time.Now()),
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(15 * time.Minute)),
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	tokenString, err := token.SignedString(secret)
	if err != nil {
		return "", 0, err
	}

	// 返回绝对过期时间戳
	expiresAt := claims.ExpiresAt.Time.Unix()
	return tokenString, expiresAt, nil
}

func GenerateRefreshToken(userID uint, username string) (string, error) {
	claims := &claims{
		UserID:   userID,
		Username: username,
		RegisteredClaims: jwt.RegisteredClaims{
			IssuedAt:  jwt.NewNumericDate(time.Now()),
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(7 * 24 * time.Hour)),
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	return token.SignedString(secret)
}

func ValidateToken(tokenString string) (*claims, error) {
	token, err := jwt.ParseWithClaims(tokenString, &claims{}, func(token *jwt.Token) (interface{}, error) {
		if token.Method == jwt.SigningMethodHS256 {
			return secret, nil
		}
		return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
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

	if claims, ok := token.Claims.(*claims); ok && token.Valid {
		return claims, nil
	}

	return nil, fmt.Errorf("invalid token")
}
