"""
Pytest configuration and fixtures
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.engine import Engine
from app.main import app
from app.db.base import Base
from app.core.deps import get_db

# Import all models to ensure they're registered with Base.metadata
from app.models import (
    Department,
    Employee,
    ManagerDepartment,
    AuditLog,
    AttendanceLog,
    LeaveRequest,
    LeaveApproval,
    LeaveBalance,
    LeaveType,
    LeaveStatus,
    ApprovalAction,
    Holiday,
    RestrictedHoliday,
    PolicySetting,
    CompoffRequest,
    CompoffLedger,
    HRPolicyAction,
    HRPolicyActionType,
)  # noqa


# Use in-memory SQLite for testing
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Enable foreign keys for SQLite
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    """Create a fresh database for each test"""
    # Drop all tables first to ensure clean state
    try:
        Base.metadata.drop_all(bind=engine)
    except Exception:
        pass  # Ignore errors if tables don't exist
    
    # Create all tables
    # SQLite doesn't support ENUM, so SQLAlchemy will use String instead
    # Ensure all models are imported before creating tables
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        # If table creation fails, try to see what went wrong
        import traceback
        print(f"Error creating tables: {e}")
        traceback.print_exc()
        raise
    
    db = TestingSessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
        try:
            Base.metadata.drop_all(bind=engine)
        except Exception:
            pass


@pytest.fixture(scope="function")
def client(db):
    """Test client fixture with database override"""
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
