package interceptor

import (
	"context"
	"log"

	"github.com/Wh1teCaat/multi-agent/client/internal/tokenmanager"
	"google.golang.org/grpc"
	"google.golang.org/grpc/metadata"
)

// 注入 token
func TokenInjectUnaryInterceptor(tm *tokenmanager.TokenManager) grpc.UnaryClientInterceptor {
	return func(ctx context.Context, method string, req, reply interface{}, cc *grpc.ClientConn, invoker grpc.UnaryInvoker, opts ...grpc.CallOption) error {
		if method == "/UserService/Register" ||
			method == "/UserService/Login" ||
			method == "/UserService/RefreshToken" {
			return invoker(ctx, method, req, reply, cc, opts...)
		}

		token := tm.GetAccessToken()
		if token != "" {
			md := metadata.Pairs("access_token", token)
			ctx = metadata.NewOutgoingContext(ctx, md)
			log.Printf("[client interceptor] inject access token for method %s", method)
		}

		return invoker(ctx, method, req, reply, cc, opts...)
	}
}

func TokenInjectStreamInterceptor(tm *tokenmanager.TokenManager) grpc.StreamClientInterceptor {
	return func(ctx context.Context, desc *grpc.StreamDesc, cc *grpc.ClientConn, method string, streamer grpc.Streamer, opts ...grpc.CallOption) (grpc.ClientStream, error) {
		token := tm.GetAccessToken()
		if token != "" {
			md := metadata.Pairs("access_token", token)
			ctx = metadata.NewOutgoingContext(ctx, md)
			log.Printf("[client interceptor] inject access token for stream method %s", method)
		}

		return streamer(ctx, desc, cc, method, opts...)
	}
}
