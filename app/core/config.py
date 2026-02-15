"""
Configuration management for ACS HRMS Backend
"""
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import Optional, List
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Required settings
    DATABASE_URL: str = Field(..., description="PostgreSQL database URL")
    JWT_SECRET_KEY: str = Field(..., description="JWT secret key for token signing")
    
    # Optional settings with defaults
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    JWT_EXPIRE_MINUTES: int = Field(default=120, description="JWT token expiration in minutes")
    
    APP_ENV: str = Field(default="local", description="Application environment: local, staging, prod")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level: DEBUG, INFO, WARNING, ERROR")
    
    # CORS settings
    ALLOWED_ORIGINS: str = Field(
        default="*",
        description="Comma-separated list of allowed CORS origins. Use '*' for local only."
    )
    
    # Timezone (documentation only; code stores UTC)
    TZ: str = Field(default="Asia/Kolkata", description="Timezone for display (code uses UTC)")

    # Attendance: when is_mocked=True, True = reject punch with 403; False = allow but set session.status = SUSPICIOUS
    REJECT_MOCK_LOCATION_PUNCH: bool = Field(
        default=True,
        description="If True, reject punch-in/out with 403 when is_mocked=True; if False, allow but mark session SUSPICIOUS",
    )
    
    # Version (can be git SHA or semver)
    VERSION: Optional[str] = Field(default=None, description="Application version (git SHA or semver)")
    
    # Initial admin bootstrap settings
    INITIAL_ADMIN_EMAIL: str = Field(
        default="admin@company.com", 
        description="Email for initial admin user (used when no admin exists)"
    )
    INITIAL_ADMIN_PASSWORD: str = Field(
        default="Admin@12345", 
        description="Password for initial admin user (used when no admin exists)"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
    
    @field_validator("APP_ENV")
    @classmethod
    def validate_app_env(cls, v: str) -> str:
        """Validate APP_ENV"""
        allowed = ["local", "staging", "prod"]
        if v not in allowed:
            raise ValueError(f"APP_ENV must be one of {allowed}")
        return v
    
    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate LOG_LEVEL"""
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}")
        return v.upper()
    
    def validate_production(self) -> None:
        """
        Validate settings for production environment
        
        Raises:
            ValueError: If production settings are invalid
        """
        if self.APP_ENV == "prod":
            # JWT_SECRET_KEY must be at least 32 characters in production
            if len(self.JWT_SECRET_KEY) < 32:
                raise ValueError(
                    "JWT_SECRET_KEY must be at least 32 characters in production environment"
                )
            
            # ALLOWED_ORIGINS must not be wildcard in production
            if self.ALLOWED_ORIGINS == "*" or not self.ALLOWED_ORIGINS:
                raise ValueError(
                    "ALLOWED_ORIGINS must be explicitly set (not '*') in production environment"
                )
    
    def get_allowed_origins_list(self) -> List[str]:
        """
        Get list of allowed CORS origins
        
        Returns:
            List of allowed origins (or ['*'] for local)
        """
        if self.ALLOWED_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]


# Create settings instance
settings = Settings()

# Validate production settings if in prod
if settings.APP_ENV == "prod":
    settings.validate_production()
