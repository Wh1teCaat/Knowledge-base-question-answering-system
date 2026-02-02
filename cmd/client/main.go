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

func Login(client proto.UserServiceClient, req *proto.LoginReq) {
	ctx, cancel := context.WithTimeout(context.Background(), time.Second*5)
	defer cancel()

	resp, err := client.Login(ctx, req)
	if err != nil {
		log.Println("🚒 Login failed:", err)
		return
	}

	log.Println("✅ Login successful:")
	log.Println("Access Token:", resp.AccessToken)
	log.Println("Refresh Token:", resp.RefreshToken)
	log.Println("Expires In:", resp.ExpiresIn)
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

	Login(client, &proto.LoginReq{
		Username: "testname",
		Password: "test",
	})
}
