package interceptor

import (
	"context"
	"log"
	"time"

	"github.com/Wh1teCaat/multi-agent/server/internal/auth"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
)

func CalculateTime(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
	log.Printf("[interceptor] recv request: %v", info.FullMethod)

	start := time.Now()
	resp, err := handler(ctx, req)
	duration := time.Since(start)

	if err != nil {
		log.Printf("[interceptor] method %s call failed", info.FullMethod)
		return resp, err
	}
	log.Printf("[interceptor] method %s call succeeded, duration: %v", info.FullMethod, duration)
	return resp, nil
}

func Authenticate(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
	if info.FullMethod == "/UserService/Register" ||
		info.FullMethod == "/UserService/Login" ||
		info.FullMethod == "/UserService/RefreshToken" {
		return handler(ctx, req)
	}

	md, ok := metadata.FromIncomingContext(ctx)
	if !ok {
		log.Printf("[interceptor] failed to authenticate")
		return nil, status.Error(codes.Unauthenticated, "missing metadata")
	}

	tokens := md.Get("access_token")
	if len(tokens) == 0 {
		return nil, status.Error(codes.Unauthenticated, "missing access token")
	}

	claims, err := auth.ValidateToken(tokens[0])
	if err != nil {
		log.Println("[interceptor] access token invalid")
		return nil, status.Error(codes.Unauthenticated, "invalid access token")
	}

	ctx = context.WithValue(ctx, "userID", claims.UserID)
	ctx = context.WithValue(ctx, "username", claims.Username)

	return handler(ctx, req)
}

type wrappedServerStream struct {
	grpc.ServerStream
	ctx context.Context
}

func (w *wrappedServerStream) Context() context.Context {
	return w.ctx
}

func AuthenticateStream(srv interface{}, ss grpc.ServerStream, info *grpc.StreamServerInfo, handler grpc.StreamHandler) error {
	md, ok := metadata.FromIncomingContext(ss.Context())
	if !ok {
		log.Printf("[interceptor] failed to authenticate")
		return status.Error(codes.Unauthenticated, "missing metadata")
	}

	tokens := md.Get("access_token")
	if len(tokens) == 0 {
		return status.Error(codes.Unauthenticated, "missing access token")
	}

	claims, err := auth.ValidateToken(tokens[0])
	if err != nil {
		log.Println("[interceptor] access token invalid")
		return status.Error(codes.Unauthenticated, "invalid access token")
	}

	ctx := context.WithValue(ss.Context(), "userID", claims.UserID)
	ctx = context.WithValue(ctx, "username", claims.Username)

	wrapped := &wrappedServerStream{
		ServerStream: ss,
		ctx:          ctx,
	}
	return handler(srv, wrapped)
}
