"""
ACS HRMS Backend - Main Application Entry Point
Developed & Designed by JPSystech
"""
import logging
from urllib.parse import urlparse, urlunparse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.errors import (
    http_exception_handler,
    validation_exception_handler,
    generic_exception_handler
)
from app.core.logging import setup_logging
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.employee import Employee, Role, WorkMode
from app.models.department import Department
from app.models.role import RoleModel
from datetime import date
from sqlalchemy.exc import OperationalError

# Setup logging first
setup_logging()
logger = logging.getLogger(__name__)


def _mask_database_url(url: str) -> str:
    """Mask password in DATABASE_URL for safe logging; show full path for sqlite."""
    try:
        parsed = urlparse(url)
        if parsed.scheme == "sqlite":
            return url  # Safe to log path
        if parsed.password:
            netloc = f"{parsed.username}:****@{parsed.hostname or ''}"
            if parsed.port:
                netloc += f":{parsed.port}"
            return urlunparse(parsed._replace(netloc=netloc))
    except Exception:
        return "***"
    return url


# Create FastAPI app
app = FastAPI(
    title="ACS HRMS Backend",
    description="Attendance + Leave Management System - Developed & Designed by JPSystech",
    version=settings.VERSION or "1.0.0"
)

# Configure CORS - must be before other middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Register exception handlers
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Include all API routes under /api/v1
app.include_router(api_router, prefix="/api/v1")


@app.on_event("startup")
def startup_log_config() -> None:
    """Log DATABASE_URL at startup so it can be verified against Alembic."""
    masked = _mask_database_url(settings.DATABASE_URL)
    logger.info("DATABASE_URL (app): %s", masked)


@app.on_event("startup")
def bootstrap_initial_admin() -> None:
    """
    Create initial admin user, roles, and department if they don't exist.
    This ensures the system always has at least one admin user.
    """
    try:
        db = SessionLocal()
        try:
            # Check if any admin user exists by emp_code OR role OR role_rank
            admin_exists = db.query(Employee).filter(
                (Employee.emp_code == "ADM-001") | 
                (Employee.role == Role.ADMIN)
            ).first()
            
            # Also check if any user has role_rank=1 through roles table
            from sqlalchemy import cast, String
            admin_by_rank = db.query(Employee).join(RoleModel, cast(Employee.role, String) == RoleModel.name).filter(
                RoleModel.role_rank == 1
            ).first()
            
            if admin_exists or admin_by_rank:
                logger.info("Admin user already exists, skipping initial bootstrap")
                return
            
            logger.info("No admin user found, creating initial admin setup...")
            
            # Create ADMIN role if it doesn't exist
            admin_role = db.query(RoleModel).filter(RoleModel.name == "ADMIN").first()
            if not admin_role:
                admin_role = RoleModel(
                    name="ADMIN",
                    role_rank=1,  # Highest authority
                    wfh_enabled=True,
                    is_active=True
                )
                db.add(admin_role)
                db.flush()
                logger.info("Created ADMIN role with role_rank=1")
            
            # Create default departments if they don't exist
            default_departments = ["Administration", "HR", "QA/QC", "Accounts", "Operations"]
            department_map = {}
            
            for dept_name in default_departments:
                existing_dept = db.query(Department).filter(Department.name == dept_name).first()
                if not existing_dept:
                    new_dept = Department(
                        name=dept_name,
                        active=True
                    )
                    db.add(new_dept)
                    logger.info("Created department: %s", dept_name)
                else:
                    department_map[dept_name] = existing_dept
            
            db.flush()
            
            # Get Administration department for admin user (re-query to ensure we have the object)
            admin_dept = db.query(Department).filter(Department.name == "Administration").first()
            if not admin_dept:
                logger.error("Administration department not found after creation attempt")
                return
            
            # Create initial admin user
            initial_admin = Employee(
                emp_code="ADM-001",
                name="System Administrator",
                mobile_number="",
                role=Role.ADMIN,
                department_id=admin_dept.id,
                password_hash=hash_password(settings.INITIAL_ADMIN_PASSWORD),
                join_date=date.today(),
                active=True,
                work_mode=WorkMode.OFFICE
            )
            db.add(initial_admin)
            db.commit()
            
            logger.info("Initial admin user created successfully")
            logger.info("Employee Code: ADM-001")
            logger.info("Password: [set via INITIAL_ADMIN_PASSWORD environment variable]")
            
        except OperationalError as e:
            # Handle database not ready yet (tables might not exist)
            if "no such table" in str(e).lower():
                logger.warning("Database tables not ready yet, skipping initial bootstrap")
            else:
                logger.error("Database error during admin bootstrap: %s", e)
        except Exception as e:
            logger.error("Error during initial admin bootstrap: %s", e)
            db.rollback()
        finally:
            db.close()
    except Exception as e:
        logger.error("Failed to initialize database session for admin bootstrap: %s", e)


# Handle missing table errors with a clear message (sqlite3 / SQLAlchemy OperationalError)
def _is_no_such_table(err: BaseException) -> bool:
    msg = str(err).lower()
    return "no such table" in msg or "attendance_sessions" in msg


def _handle_operational_error(request, exc: Exception):
    if _is_no_such_table(exc):
        return JSONResponse(
            status_code=500,
            content={"detail": "Run alembic upgrade head"},
        )
    from app.core.errors import generic_exception_handler
    return generic_exception_handler(request, exc)


try:
    import sqlite3
    app.add_exception_handler(sqlite3.OperationalError, _handle_operational_error)
except ImportError:
    pass
try:
    from sqlalchemy.exc import OperationalError as SAOperationalError
    app.add_exception_handler(SAOperationalError, _handle_operational_error)
except ImportError:
    pass
