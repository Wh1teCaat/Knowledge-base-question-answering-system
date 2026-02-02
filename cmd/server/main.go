package main

import (
	"log"
	"net"

	"github.com/Wh1teCaat/multi-agent/internal/config"
	"github.com/Wh1teCaat/multi-agent/internal/database"
	"github.com/Wh1teCaat/multi-agent/internal/repository"
	"github.com/Wh1teCaat/multi-agent/internal/server"
	"github.com/Wh1teCaat/multi-agent/internal/service"
	"github.com/Wh1teCaat/multi-agent/proto"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
)

func main() {
	cfg, err := config.LoadConfig()
	if err != nil {
		log.Println("🚒 failed to load config:", err)
	}
	log.Println("Config loaded successfully:", cfg)

	db := database.InitDB(cfg.Database.DSN)
	repo := repository.NewRepository(db)
	svc := service.NewService(repo, cfg.Service.HS256_SECRET)
	srv := server.NewServer(svc)

	// load credentials
	creds, err := credentials.NewServerTLSFromFile("server.pem", "server.key")
	if err != nil {
		log.Fatal("[Error] Credential loading failed")
	}

	// register service to server
	s := grpc.NewServer(grpc.Creds(creds))
	proto.RegisterUserServiceServer(s, srv)

	log.Println("✅ gRPC server is running on port 50051")

	lis, err := net.Listen("tcp", ":50051")
	if err != nil {
		log.Fatalf("failed to listen: %v", err)
	}

	if err := s.Serve(lis); err != nil {
		log.Fatalf("failed to serve: %v", err)
	}
}
