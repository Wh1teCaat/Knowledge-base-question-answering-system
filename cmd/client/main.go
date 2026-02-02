package main

import (
	"context"
	"log"
	"time"

	"github.com/Wh1teCaat/multi-agent/proto"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
)

func Register(client proto.UserServiceClient, req *proto.RegisterReq) {
	ctx, cancel := context.WithTimeout(context.Background(), time.Second*5)
	defer cancel()

	resp, err := client.Register(ctx, req)
	if err != nil {
		log.Println("🚒 Registration failed:", err)
		return
	}

	log.Println("✅ Registration successful:", resp.Username)
}

func Login(client proto.UserServiceClient, req *proto.LoginReq) *proto.LoginResp {
	ctx, cancel := context.WithTimeout(context.Background(), time.Second*5)
	defer cancel()

	resp, err := client.Login(ctx, req)
	if err != nil {
		log.Println("🚒 Login failed:", err)
		return nil
	}

	log.Println("✅ Login successful")
	return resp
}

func main() {
	creds, err := credentials.NewClientTLSFromFile("server.pem", "localhost")
	if err != nil {
		log.Fatalf("[Error] Credential loading failed: %v", err)
	}

	conn, err := grpc.NewClient("localhost:50051", grpc.WithTransportCredentials(creds))
	if err != nil {
		log.Fatalf("[Error] Connection failed: %v", err)
	}
	defer conn.Close()

	log.Println("✅ gRPC client connected successfully")

	client := proto.NewUserServiceClient(conn)

	resp := Login(client, &proto.LoginReq{
		Username: "testname",
		Password: "test",
	})
	expiresAt := time.Unix(resp.ExpiresAt, 0)

	done := make(chan struct{})
	go func() {
		time.Sleep(31 * time.Minute)
		done <- struct{}{}
	}()

	go func() {
		// 提前一分钟刷新
		ticker := time.NewTicker(time.Until(expiresAt.Add(-1 * time.Minute)))
		defer ticker.Stop()

		for range ticker.C {
			log.Println("🔄 Refreshing access token...")
			newResp, err := client.RefreshToken(context.Background(), &proto.RefreshTokenReq{
				RefreshToken: resp.RefreshToken,
			})
			if err != nil {
				log.Println("🚒 Token refresh failed:", err)
				continue
			}

			resp = newResp
			log.Println("✅ Token refreshed successfully")
		}
	}()

	<-done
}
