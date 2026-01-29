.PHONY: all init gen tidy

all: init tidy gen

init:
	@go install github.com/bufbuild/buf/cmd/buf@v1.40.0
	@go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.34.2
	@go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.4.0
	@go install github.com/grpc-ecosystem/grpc-gateway/v2/protoc-gen-grpc-gateway@v2.22.0
	@buf dep update
	@echo "✅ Initialization complete."

gen:
	@echo "🚥 generating protobuf code..."
	@buf generate
	@echo "✅ Protobuf code generation complete."

tidy:
	@echo "🚥 tidying go modules..."
	@go mod tidy
	@echo "✅ Go modules tidying complete."

