"""
Security utilities for authentication and authorization
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
import bcrypt
from app.core.config import settings
from app.core.constants import SYSTEM_CREDIT

# Configure logger
logger = logging.getLogger(__name__)

# Simple direct implementation to avoid passlib Windows issues
# We'll implement our own hashing functions that use the underlying libraries directly

# Track available backends
argon2_available = False
bcrypt_available = False

# Test backends at startup
try:
    import argon2
    # Test argon2
    hasher = argon2.PasswordHasher()
    test_hash = hasher.hash("test")
    verified = hasher.verify(test_hash, "test")
    if verified:
        argon2_available = True
        logger.info("Argon2 backend is available")
except Exception as e:
    logger.warning(f"Argon2 backend not available: {e}")

try:
    import bcrypt
    # Test bcrypt
    test_hash = bcrypt.hashpw(b"test", bcrypt.gensalt())
    verified = bcrypt.checkpw(b"test", test_hash)
    if verified:
        bcrypt_available = True
        logger.info("Bcrypt backend is available")
except Exception as e:
    logger.warning(f"Bcrypt backend not available: {e}")

# Ensure at least one backend is available
if not argon2_available and not bcrypt_available:
    error_msg = "No password hashing backends available. Please install argon2-cffi or bcrypt."
    logger.critical(error_msg)
    raise RuntimeError(error_msg)

logger.info(f"Available backends - Argon2: {argon2_available}, Bcrypt: {bcrypt_available}")

# Create simple passlib context for basic compatibility
# We'll use it only for scheme detection, not actual hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using available backend (argon2 preferred, bcrypt fallback)"""
    if argon2_available:
        try:
            import argon2
            hasher = argon2.PasswordHasher()
            return hasher.hash(password)
        except Exception as e:
            logger.warning(f"Argon2 hashing failed, falling back to bcrypt: {e}")
    
    if bcrypt_available:
        import bcrypt
        # Bcrypt has a 72-byte limit, so we need to handle this
        password_bytes = password.encode('utf-8')
        if len(password_bytes) > 72:
            # Truncate to 72 bytes for bcrypt compatibility
            password_bytes = password_bytes[:72]
        return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')
    
    raise RuntimeError("No hashing backends available")


def validate_password(password: str) -> str:
    """
    Validate and normalize password for hashing
    
    Args:
        password: Raw password string
        
    Returns:
        Normalized password (trimmed)
        
    Raises:
        ValueError: If password is invalid with specific error message
    """
    if password is None:
        raise ValueError("Password is required")
    
    # Trim whitespace
    password = password.strip()
    
    # Check if empty after trimming
    if not password:
        raise ValueError("Password cannot be empty")
    
    # Check minimum length
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters")
    
    # Check UTF-8 byte length for bcrypt compatibility
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        raise ValueError("Password cannot be longer than 72 bytes when encoded as UTF-8")
    
    return password


def normalize_password(password: Optional[str]) -> Optional[str]:
    """
    Normalize password - trim whitespace and handle empty strings
    
    Args:
        password: Raw password string or None
        
    Returns:
        Normalized password or None if empty/None
    """
    if password is None:
        return None
    
    password = password.strip()
    return password if password else None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    # Try argon2 first
    if argon2_available and hashed_password.startswith('$argon2'):
        try:
            import argon2
            hasher = argon2.PasswordHasher()
            return hasher.verify(hashed_password, plain_password)
        except Exception:
            # If argon2 verification fails, try bcrypt
            pass
    
    # Try bcrypt
    if bcrypt_available:
        try:
            import bcrypt
            return bcrypt.checkpw(
                plain_password.encode('utf-8'),
                hashed_password.encode('utf-8')
            )
        except Exception:
            pass
    
    # Fallback to passlib context (for existing hashes)
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def create_access_token(data: Dict, expires_minutes: Optional[int] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    
    if expires_minutes is None:
        expires_minutes = settings.JWT_EXPIRE_MINUTES
    
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire})
    
    # Optionally include credit in token payload
    to_encode.update({"credit": SYSTEM_CREDIT})
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_token(token: str) -> Dict:
    """Decode and verify a JWT token"""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        raise ValueError("Invalid token")


def check_hashing_backend() -> Dict[str, str]:
    """
    Runtime check for hashing backend availability
    
    Returns:
        Dict with backend status information
        
    Raises:
        RuntimeError: If no hashing backend is available
    """
    try:
        # Test current hashing context
        test_password = "test_backend_check"
        test_hash = pwd_context.hash(test_password)
        verified = pwd_context.verify(test_password, test_hash)
        
        if not verified:
            raise RuntimeError("Hashing backend verification failed")
            
        return {
            "status": "healthy",
            "available_schemes": pwd_context.schemes(),
            "argon2_available": argon2_available,
            "primary_scheme": pwd_context.schemes()[0] if pwd_context.schemes() else "none"
        }
        
    except Exception as e:
        error_msg = f"Hashing backend unavailable: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
