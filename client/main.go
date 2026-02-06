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
	"google.golang.org/grpc/metadata"
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

func Chat(ctx context.Context, client proto.AgentServiceClient) {
	stream, err := client.Chat(ctx)
	if err != nil {
		log.Println("[Error] Chat stream creation failed:", err)
		return
	}

	reader := bufio.NewReader(os.Stdin)
	for {
		// Send
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

		// Recv
		resp, err := stream.Recv()
		if err == io.EOF {
			log.Println("Server close")
			return
		}
		if err != nil {
			log.Println("[Error] Recving response failed:", err)
			return
		}

		fmt.Printf("\r\033[32m🤖: %s\033[0m\n", resp.Response)
	}
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

	// Register and login
	var login_resp *proto.LoginResp
	for {
		fmt.Println("Do you want to (l)ogin or (r)egister?")
		var choice string
		fmt.Scanln(&choice)
		if choice == "l" {
			var username, password string
			fmt.Print("Username: ")
			fmt.Scanln(&username)
			fmt.Print("Password: ")
			fmt.Scanln(&password)
			login_resp = Login(user_client, &proto.LoginReq{
				Username: username,
				Password: password,
			})

			if login_resp == nil {
				fmt.Println("Login failed, please try again.")
				continue
			}
			break
		} else if choice == "r" {
			var username, password, email string
			fmt.Print("Choose a Username: ")
			fmt.Scanln(&username)
			fmt.Print("Choose a Password: ")
			fmt.Scanln(&password)
			fmt.Print("Choose an Email: ")
			fmt.Scanln(&email)
			Register(user_client, &proto.RegisterReq{
				Username: username,
				Password: password,
				Email:    email,
			})
		} else {
			log.Println("Invalid choice, please enter 'l' or 'r'")
		}
	}

	expiresAt := time.Unix(login_resp.ExpiresAt, 0)
	access_token := login_resp.AccessToken
	ctx := metadata.NewOutgoingContext(context.Background(), metadata.Pairs("access_token", access_token))

	done := make(chan struct{})
	go func() {
		time.Sleep(15 * time.Minute)
		close(done)
	}()

	go func() {
		// 提前一分钟刷新
		ticker := time.NewTicker(time.Until(expiresAt.Add(-1 * time.Minute)))
		defer ticker.Stop()

		for range ticker.C {
			log.Println("🔄 Refreshing access token...")

			newResp, err := user_client.RefreshToken(ctx, &proto.RefreshTokenReq{RefreshToken: login_resp.RefreshToken})
			if err != nil {
				log.Println("🚒 Token refresh failed:", err)
				continue
			}

			login_resp = newResp
			log.Println("✅ Token refreshed successfully")
		}
	}()

	Chat(ctx, agent_client)

	<-done
}
