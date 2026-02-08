package main

import (
	"log"
	"net"

	"github.com/Wh1teCaat/multi-agent/proto"
	"github.com/Wh1teCaat/multi-agent/server/internal/config"
	"github.com/Wh1teCaat/multi-agent/server/internal/database"
	"github.com/Wh1teCaat/multi-agent/server/internal/interceptor"
	"github.com/Wh1teCaat/multi-agent/server/internal/repository"
	"github.com/Wh1teCaat/multi-agent/server/internal/server"
	"github.com/Wh1teCaat/multi-agent/server/internal/service"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
)

func main() {
	cfg, err := config.LoadConfig()
	if err != nil {
		log.Println("🚒 failed to load config:", err)
	}
	log.Println("Config loaded successfully")

	db := database.InitDB(cfg.Database.DSN)
	repo := repository.NewRepository(db)
	svc := service.NewService(repo)
	srv, err := server.NewServer(svc, cfg.PythonAddr)
	if err != nil {
		log.Fatalf("failed to create server: %v", err)
	}

	// load credentials
	creds, err := credentials.NewServerTLSFromFile("server.pem", "server.key")
	if err != nil {
		log.Fatal("[Error] Credential loading failed")
	}

	// register service to server
	s := grpc.NewServer(
		grpc.Creds(creds),
		grpc.ChainUnaryInterceptor(interceptor.Authenticate, interceptor.CalculateTime),
		grpc.StreamInterceptor(interceptor.AuthenticateStream),
	)
	proto.RegisterUserServiceServer(s, srv)
	proto.RegisterAgentServiceServer(s, srv)

	log.Println("✅ gRPC server is running on port 50051")

	lis, err := net.Listen("tcp", ":50051")
	if err != nil {
		log.Fatalf("failed to listen: %v", err)
	}

	if err := s.Serve(lis); err != nil {
		log.Fatalf("failed to serve: %v", err)
	}
}
