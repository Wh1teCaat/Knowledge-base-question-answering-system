package config

import (
	"log"

	"github.com/spf13/viper"
)

type Config struct {
	Database
	Service
}

type Database struct {
	DSN string `yaml:"dsn"`
}

type Service struct {
	HS256_SECRET string `yaml:"hs256_secret"`
}

func LoadConfig() (*Config, error) {
	viper.AddConfigPath(".")
	viper.SetConfigName("config")
	viper.SetConfigType("yaml")

	if err := viper.ReadInConfig(); err != nil {
		log.Fatalf("🚒 failed to read config file: %v", err)
		return nil, err
	}

	var config *Config
	if err := viper.Unmarshal(&config); err != nil {
		log.Fatalf("🚒 failed to unmarshal config: %v", err)
		return nil, err
	}

	return config, nil
}
