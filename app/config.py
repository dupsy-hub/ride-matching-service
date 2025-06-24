from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # Application
    app_name: str = "Ride Matching Service"
    debug: bool = False
    port: int = 8002
    log_level: str = "INFO"
    
    # Database
    database_url: str = "postgresql+asyncpg://rideshare:password@localhost:5432/rideshare_db"
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # External Services
    user_service_url: str = "http://user-service:8001"
    payment_service_url: str = "http://payment-service:8003"
    notification_service_url: str = "http://notification-service:8004"
    
    # Matching Algorithm Settings
    max_drivers_to_notify: int = 3
    driver_response_timeout: int = 30  # seconds
    matching_radius_km: float = 5.0
    
    # Business Logic
    base_fare: float = 2.50
    per_km_rate: float = 1.20
    per_minute_rate: float = 0.25
    
    # JWT Settings (for validating tokens from User Service)
    jwt_secret: str = "your-secret-key"
    jwt_algorithm: str = "HS256"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()