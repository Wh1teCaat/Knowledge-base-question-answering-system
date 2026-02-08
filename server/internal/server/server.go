package server

import (
	"context"
	"errors"
	"fmt"
	"io"
	"log"

	"github.com/Wh1teCaat/multi-agent/proto"
	"github.com/Wh1teCaat/multi-agent/server/internal/service"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
	"gorm.io/gorm"
)

type Server struct {
	proto.UnimplementedUserServiceServer
	proto.UnimplementedAgentServiceServer
	svc             *service.Service
	agentClient     proto.AgentServiceClient // python gRPC
	pythonConnected bool
}

func NewServer(svc *service.Service, pythonAddr string) (*Server, error) {
	conn, err := grpc.NewClient(
		pythonAddr,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithDefaultCallOptions(
			grpc.MaxCallRecvMsgSize(100*1024*1024),
			grpc.MaxCallSendMsgSize(100*1024*1024),
		),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to python agent service: %w", err)
	}

	agentClient := proto.NewAgentServiceClient(conn)

	log.Println("✅ Connected to Python agent service")

	return &Server{
		svc:             svc,
		agentClient:     agentClient,
		pythonConnected: true,
	}, nil
}

func (s *Server) Register(ctx context.Context, req *proto.RegisterReq) (*proto.RegisterResp, error) {
	if err := s.svc.Register(req.Username, req.Password, req.Email); err != nil {
		switch {
		case errors.Is(err, gorm.ErrRegistered):
			return nil, status.Error(codes.AlreadyExists, "User or email already registered")
		case errors.Is(err, service.ErrEmptyFields):
			return nil, status.Error(codes.InvalidArgument, "Username, password, and email cannot be empty")
		case errors.Is(err, service.ErrHashPassword):
			return nil, status.Error(codes.Internal, "Internal server error")
		default:
			log.Printf("🚒 failed to register user: %v", err)
			return nil, status.Error(codes.Internal, "Failed to register user")
		}
	}

	return &proto.RegisterResp{
		Username: req.Username,
	}, nil
}

func (s *Server) Login(ctx context.Context, req *proto.LoginReq) (*proto.LoginResp, error) {
	accessToken, refreshToken, expiresAt, err := s.svc.Login(req.Username, req.Password)
	if err != nil {
		switch {
		case errors.Is(err, service.ErrEmptyFields):
			return nil, status.Error(codes.InvalidArgument, "Username and password cannot be empty")
		case errors.Is(err, service.ErrInvalidCredentials):
			return nil, status.Error(codes.Unauthenticated, "Invalid username or password")
		default:
			log.Printf("🚒 failed to login: %v", err)
			return nil, status.Error(codes.Internal, "Failed to login")
		}
	}

	return &proto.LoginResp{
		AccessToken:  accessToken,
		RefreshToken: refreshToken,
		ExpiresAt:    expiresAt,
	}, nil
}

func (s *Server) RefreshToken(ctx context.Context, req *proto.RefreshTokenReq) (*proto.LoginResp, error) {
	accessToken, expiresAt, err := s.svc.RefreshAccessToken(req.RefreshToken)
	if err != nil {
		switch {
		case errors.Is(err, service.ErrInvalidCredentials):
			return nil, status.Error(codes.Unauthenticated, "Invalid refresh token")
		default:
			log.Printf("🚒 failed to refresh access token: %v", err)
			return nil, status.Error(codes.Internal, "Failed to refresh access token")
		}
	}

	return &proto.LoginResp{
		AccessToken:  accessToken,
		RefreshToken: req.RefreshToken,
		ExpiresAt:    expiresAt,
	}, nil
}

func (s *Server) Chat(stream proto.AgentService_ChatServer) error {
	// for {
	// 	// Recv
	// 	req, err := stream.Recv()
	// 	if err == io.EOF {
	// 		log.Println("Client close")
	// 		return nil
	// 	}
	// 	if err != nil {
	// 		log.Printf("🚒 failed to receive chat request: %v", err)
	// 		return err
	// 	}

	// 	// call service
	// 	answer, err := s.svc.ChatWithAgent(stream.Context(), &service.ChatRequest{
	// 		ID:       stream.Context().Value("userID").(uint),
	// 		ThreadID: req.ThreadId,
	// 		Query:    req.Query,
	// 	})
	// 	if err != nil {
	// 		log.Printf("[Error] %v", err)
	// 		if sendErr := stream.Send(&proto.ChatResp{Response: fmt.Sprintf("Error: %v", err)}); sendErr != nil {
	// 			log.Printf("[Error] %v", sendErr)
	// 			return sendErr
	// 		}
	// 		continue
	// 	}

	// 	// Send
	// 	if err := stream.Send(&proto.ChatResp{Response: answer}); err != nil {
	// 		log.Printf("[Error] %v", err)
	// 		return err
	// 	}
	// }

	pythonStream, err := s.agentClient.Chat(stream.Context())
	if err != nil {
		log.Printf("🚒 failed to create python chat stream: %v", err)
		return status.Error(codes.Unavailable, "Failed to connect to agent service")
	}
	defer pythonStream.CloseSend()

	errChan := make(chan error, 2)

	// Goroutine 1: Recv from client and send to python
	go func() {
		for {
			req, err := stream.Recv()
			if err == io.EOF {
				log.Println("Client close(EOF)")
				pythonStream.CloseSend()
				errChan <- nil
				return
			}
			if err != nil {
				errChan <- status.Error(codes.Internal, fmt.Sprintf("Failed to receive chat request: %v", err))
				return
			}

			if err := pythonStream.Send(req); err != nil {
				errChan <- status.Error(codes.Internal, fmt.Sprintf("Failed to send chat request to agent service: %v", err))
				return
			}
		}
	}()

	/*
		client				go server			python server
		quit/exit  	->      	EOF		->		  CloseSend
		close		<-			EOF		<- 			EOF
	*/

	// Goroutine 2: Recv from python and send to client
	go func() {
		for {
			resp, err := pythonStream.Recv()
			if err == io.EOF {
				log.Println("Python server close(EOF)")
				errChan <- nil
				return
			}
			if err != nil {
				errChan <- status.Error(codes.Internal, fmt.Sprintf("Failed to receive chat response from agent service: %v", err))
				return
			}

			if err := stream.Send(resp); err != nil {
				errChan <- status.Error(codes.Internal, fmt.Sprintf("Failed to send chat response to client: %v", err))
				return
			}
		}
	}()

	err1 := <-errChan
	err2 := <-errChan

	if err1 != nil {
		return err1
	}
	if err2 != nil {
		return err2
	}

	log.Println("Chat stream closed gracefully")
	return nil
}
