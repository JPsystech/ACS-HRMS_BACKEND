"""
Tests for configuration validation
"""
import pytest
from pydantic import ValidationError
from app.core.config import Settings


def test_prod_settings_rejects_wildcard_origins():
    """Test that production settings reject wildcard origins"""
    # This should raise ValidationError when validate_production is called
    # We'll test the validation method directly
    
    # Create settings with prod env and wildcard origins
    try:
        settings = Settings(
            DATABASE_URL="postgresql://test",
            JWT_SECRET_KEY="a" * 32,  # Valid length
            APP_ENV="prod",
            ALLOWED_ORIGINS="*"
        )
        
        # This should raise ValueError
        with pytest.raises(ValueError, match="ALLOWED_ORIGINS"):
            settings.validate_production()
    except ValidationError:
        # If validation happens at creation time, that's also fine
        pass


def test_prod_settings_rejects_short_jwt_secret():
    """Test that production settings reject short JWT secret"""
    try:
        settings = Settings(
            DATABASE_URL="postgresql://test",
            JWT_SECRET_KEY="short",  # Too short
            APP_ENV="prod",
            ALLOWED_ORIGINS="https://example.com"
        )
        
        # This should raise ValueError
        with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
            settings.validate_production()
    except ValidationError:
        # If validation happens at creation time, that's also fine
        pass


def test_local_settings_allows_wildcard_origins():
    """Test that local settings allow wildcard origins"""
    settings = Settings(
        DATABASE_URL="postgresql://test",
        JWT_SECRET_KEY="test-key",
        APP_ENV="local",
        ALLOWED_ORIGINS="*"
    )
    
    # Should not raise error
    settings.validate_production()  # Should pass for local
    
    # Should return wildcard in list
    origins = settings.get_allowed_origins_list()
    assert origins == ["*"]


def test_get_allowed_origins_list():
    """Test parsing of ALLOWED_ORIGINS"""
    # Test wildcard
    settings = Settings(
        DATABASE_URL="postgresql://test",
        JWT_SECRET_KEY="test-key",
        ALLOWED_ORIGINS="*"
    )
    assert settings.get_allowed_origins_list() == ["*"]
    
    # Test comma-separated list
    settings = Settings(
        DATABASE_URL="postgresql://test",
        JWT_SECRET_KEY="test-key",
        ALLOWED_ORIGINS="https://example.com,https://app.example.com"
    )
    origins = settings.get_allowed_origins_list()
    assert len(origins) == 2
    assert "https://example.com" in origins
    assert "https://app.example.com" in origins
