"""
Employee model
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.db.base import Base


class Role(str, enum.Enum):
    EMPLOYEE = "EMPLOYEE"
    MANAGER = "MANAGER"
    HR = "HR"
    MD = "MD"
    VP = "VP"
    ADMIN = "ADMIN"


class WorkMode(str, enum.Enum):
    OFFICE = "OFFICE"
    SITE = "SITE"


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    emp_code = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    mobile_number = Column(String, nullable=True)
    role = Column(String, nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)  # Required
    reporting_manager_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    password_hash = Column(String, nullable=True)
    join_date = Column(Date, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    work_mode = Column(String, default="OFFICE", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.current_timestamp(), onupdate=func.current_timestamp(), nullable=False)

    # Relationships
    department = relationship("Department", backref="employees")
    reporting_manager = relationship("Employee", remote_side=[id], backref="direct_reports")
    managed_departments = relationship("ManagerDepartment", back_populates="manager", cascade="all, delete-orphan")
    leave_requests = relationship("LeaveRequest", foreign_keys="LeaveRequest.employee_id", back_populates="employee")
    approved_leave_requests = relationship("LeaveRequest", foreign_keys="LeaveRequest.approver_id", back_populates="approver")
