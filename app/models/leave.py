"""
Leave models
"""
from sqlalchemy import (
    Column,
    Integer,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    Numeric,
    Enum as SQLEnum,
    Boolean,
    UniqueConstraint,
    Index,
    CheckConstraint,
)
from sqlalchemy import func
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text
import enum
from app.db.base import Base


class LeaveType(str, enum.Enum):
    CL = "CL"
    PL = "PL"
    SL = "SL"
    RH = "RH"
    COMPOFF = "COMPOFF"
    LWP = "LWP"


class LeaveStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    CANCELLED_BY_COMPANY = "CANCELLED_BY_COMPANY"  # Company can cancel approved leave


class ApprovalAction(str, enum.Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    CANCEL = "CANCEL"


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    approver_id = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)
    approved_remark = Column(Text, nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejected_remark = Column(Text, nullable=True)
    rejected_by_id = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_remark = Column(Text, nullable=True)
    cancelled_by_id = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    leave_type = Column(SQLEnum(LeaveType), nullable=False)
    from_date = Column(Date, nullable=False)
    to_date = Column(Date, nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(SQLEnum(LeaveStatus), nullable=False, server_default=text("'PENDING'"))
    computed_days = Column(Numeric(5, 2), nullable=False)  # Supports 0.5 days - total days requested
    paid_days = Column(Numeric(5, 2), nullable=False, server_default=text("'0'"))  # Days covered by leave balance
    lwp_days = Column(Numeric(5, 2), nullable=False, server_default=text("'0'"))  # Days converted to LWP
    computed_days_by_month = Column(String, nullable=True)  # JSONB equivalent - store as JSON string for now
    override_policy = Column(Boolean, nullable=False, default=False)  # HR override flag
    override_remark = Column(Text, nullable=True)  # Mandatory remark when override_policy is true
    auto_converted_to_lwp = Column(Boolean, nullable=False, default=False)  # Flag for backdated >7 days auto-conversion
    auto_lwp_reason = Column(Text, nullable=True)  # Reason for auto-conversion (e.g., "backdated_over_limit")
    applied_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )

    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id], back_populates="leave_requests")
    approver = relationship("Employee", foreign_keys=[approver_id], back_populates="approved_leave_requests")
    rejected_by = relationship("Employee", foreign_keys=[rejected_by_id])
    cancelled_by = relationship("Employee", foreign_keys=[cancelled_by_id])
    approvals = relationship("LeaveApproval", back_populates="leave_request", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('ix_leave_requests_employee_dates', 'employee_id', 'from_date', 'to_date'),
        CheckConstraint('from_date <= to_date', name='check_from_date_le_to_date'),
    )


class LeaveApproval(Base):
    __tablename__ = "leave_approvals"

    id = Column(Integer, primary_key=True, index=True)
    leave_request_id = Column(Integer, ForeignKey("leave_requests.id"), nullable=False, index=True)
    action_by = Column(Integer, ForeignKey("employees.id"), nullable=False)
    action = Column(SQLEnum(ApprovalAction), nullable=False)
    remarks = Column(Text, nullable=True)
    action_at = Column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )

    # Relationships
    leave_request = relationship("LeaveRequest", back_populates="approvals")
    approver = relationship("Employee", foreign_keys=[action_by])


# Wallet leave types (CL, SL, PL, RH only - no COMPOFF/LWP)
WALLET_LEAVE_TYPES = (LeaveType.CL, LeaveType.SL, LeaveType.PL, LeaveType.RH)


class LeaveTransactionAction(str, enum.Enum):
    ACCRUAL = "ACCRUAL"
    APPROVE_DEDUCT = "APPROVE_DEDUCT"   # APPROVED_LEAVE
    CANCEL_RECREDIT = "CANCEL_RECREDIT"  # CANCELLED_LEAVE
    MANUAL_ADJUST = "MANUAL_ADJUST"      # ADJUSTMENT
    YEAR_CLOSE = "YEAR_CLOSE"


class LeaveBalance(Base):
    """
    Leave wallet balance: one row per (employee_id, year, leave_type).
    remaining = opening + accrued + carry_forward - used.
    """
    __tablename__ = "leave_balances"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    leave_type = Column(SQLEnum(LeaveType), nullable=False)  # CL, SL, PL, RH only
    opening = Column(Numeric(5, 2), nullable=False, default=0)
    accrued = Column(Numeric(5, 2), nullable=False, default=0)
    used = Column(Numeric(5, 2), nullable=False, default=0)
    remaining = Column(Numeric(5, 2), nullable=False, default=0)
    carry_forward = Column(Numeric(5, 2), nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )

    # Relationships
    employee = relationship("Employee", backref="leave_balances")

    __table_args__ = (
        UniqueConstraint("employee_id", "year", "leave_type", name="uq_leave_balances_employee_year_type"),
    )


class LeaveTransaction(Base):
    """Audit trail for wallet: accrual, approve deduct, cancel recredit, manual adjust."""
    __tablename__ = "leave_transactions"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    leave_id = Column(Integer, ForeignKey("leave_requests.id", ondelete="SET NULL"), nullable=True, index=True)
    year = Column(Integer, nullable=False, index=True)
    leave_type = Column(SQLEnum(LeaveType), nullable=False)
    delta_days = Column(Numeric(5, 2), nullable=False)  # + for credit, - for deduct
    action = Column(String(30), nullable=False)  # ACCRUAL, APPROVE_DEDUCT, CANCEL_RECREDIT, MANUAL_ADJUST
    remarks = Column(Text, nullable=True)
    action_by_employee_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True)
    action_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)

    employee = relationship("Employee", foreign_keys=[employee_id])
    leave_request = relationship("LeaveRequest", foreign_keys=[leave_id])
    action_by = relationship("Employee", foreign_keys=[action_by_employee_id])
