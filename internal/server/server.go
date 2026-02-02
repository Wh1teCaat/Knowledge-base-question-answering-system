package server

import (
	"context"
	"errors"
	"log"

	"github.com/Wh1teCaat/multi-agent/internal/service"
	"github.com/Wh1teCaat/multi-agent/proto"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"gorm.io/gorm"
)

type Server struct {
	proto.UnimplementedUserServiceServer
	svc *service.Service
}

func NewServer(svc *service.Service) *Server {
	return &Server{svc: svc}
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
	accessToken, refreshToken, expiresIn, err := s.svc.Login(req.Username, req.Password)
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
		ExpiresIn:    expiresIn,
	}, nil
}

func (s *Server) RefreshToken(ctx context.Context, req *proto.RefreshTokenReq) (*proto.LoginResp, error) {
	accessToken, expiresIn, err := s.svc.RefreshAccessToken(req.RefreshToken)
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
		ExpiresIn:    expiresIn,
	}, nil
}
