"""
Comp-off models
"""
from sqlalchemy import Column, Integer, Date, DateTime, ForeignKey, Text, Numeric, Enum as SQLEnum, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text
import enum
from app.db.base import Base


class CompoffRequestStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class CompoffLedgerType(str, enum.Enum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"


class CompoffRequest(Base):
    __tablename__ = "compoff_requests"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    worked_date = Column(Date, nullable=False, index=True)
    reason = Column(Text, nullable=True)
    status = Column(SQLEnum(CompoffRequestStatus), nullable=False, server_default=text("'PENDING'"))
    requested_at = Column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.current_timestamp(), onupdate=func.current_timestamp(), nullable=False)

    # Relationships
    employee = relationship("Employee", backref="compoff_requests")

    __table_args__ = (
        UniqueConstraint('employee_id', 'worked_date', name='uq_compoff_employee_worked_date'),
    )


class CompoffLedger(Base):
    __tablename__ = "compoff_ledger"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    entry_type = Column(SQLEnum(CompoffLedgerType), nullable=False)
    days = Column(Numeric(5, 2), nullable=False)  # 1.0 for credits, variable for debits
    worked_date = Column(Date, nullable=True)  # Set for CREDIT entries
    expires_on = Column(Date, nullable=True)  # Set for CREDIT entries = worked_date + 60 days
    leave_request_id = Column(Integer, ForeignKey("leave_requests.id"), nullable=True)  # Set for DEBIT entries
    reference_id = Column(Integer, nullable=True)  # compoff_request_id for credit linkage
    created_at = Column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)

    # Relationships
    employee = relationship("Employee", backref="compoff_ledger_entries")
    leave_request = relationship("LeaveRequest", backref="compoff_debits")

    __table_args__ = (
        Index('ix_compoff_ledger_employee_type', 'employee_id', 'entry_type'),
        Index('ix_compoff_ledger_employee_expires', 'employee_id', 'expires_on'),
    )
