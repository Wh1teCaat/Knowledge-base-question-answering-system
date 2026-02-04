package main

import (
	"bufio"
	"context"
	"fmt"
	"io"
	"log"
	"os"
	"strings"
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

func Chat(client proto.AgentServiceClient) {
	stream, err := client.Chat(context.Background())
	if err != nil {
		log.Println("[Error] Chat stream creation failed:", err)
		return
	}

	// control life of Send and Recv
	done := make(chan struct{})

	// send thread
	reader := bufio.NewReader(os.Stdin)
	go func() {
		for {
			fmt.Print("> ")
			line, err := reader.ReadString('\n')
			if err != nil {
				log.Println("[Error] Reading input failed, pls try again")
				continue
			}

			line = strings.TrimSpace(line)
			if line == "quit" || line == "exit" {
				stream.CloseSend() // client -> server EOF
				return
			}

			if err := stream.Send(&proto.ChatReq{Id: 1, ThreadId: "default", Query: line}); err != nil {
				log.Println("[Error] Sending chat request failed:", err)
				return
			}
		}
	}()

	// recv thread
	go func() {
		defer close(done)
		for {
			resp, err := stream.Recv()
			if err == io.EOF { // server -> client EOF
				log.Println("Server close")
				return
			}
			if err != nil {
				log.Println("[Error] Receiving chat response failed:", err)
				return
			}

			fmt.Printf("\r\033[32m🤖: %s\033[0m\n> ", resp.Response)
		}
	}()

	<-done
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

	user_client := proto.NewUserServiceClient(conn)
	agent_client := proto.NewAgentServiceClient(conn)

	resp := Login(user_client, &proto.LoginReq{
		Username: "testname",
		Password: "test",
	})
	expiresAt := time.Unix(resp.ExpiresAt, 0)

	done := make(chan struct{})
	go func() {
		time.Sleep(31 * time.Minute)
		close(done)
	}()

	go func() {
		// 提前一分钟刷新
		ticker := time.NewTicker(time.Until(expiresAt.Add(-1 * time.Minute)))
		defer ticker.Stop()

		for range ticker.C {
			log.Println("🔄 Refreshing access token...")
			newResp, err := user_client.RefreshToken(context.Background(), &proto.RefreshTokenReq{
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

	Chat(agent_client)

	<-done
}
