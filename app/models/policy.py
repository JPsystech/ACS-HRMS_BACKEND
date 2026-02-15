"""
Policy settings model
"""
from sqlalchemy import Column, Integer, DateTime, Boolean, Numeric, UniqueConstraint
from sqlalchemy.sql import func
from app.db.base import Base


class PolicySetting(Base):
    __tablename__ = "policy_settings"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False, unique=True)  # e.g., 2026
    
    # ACS annual entitlements per year (Jan–Dec): PL=7, SL=6, CL=5, RH=1
    annual_pl = Column(Integer, nullable=False, default=7)
    annual_cl = Column(Integer, nullable=False, default=6)
    annual_sl = Column(Integer, nullable=False, default=7)
    annual_rh = Column(Integer, nullable=False, default=1)
    # Public holidays (calendar display only; not deducted from leave balance)
    public_holiday_total = Column(Integer, nullable=True, default=14)
    
    # Monthly credit rates
    monthly_credit_pl = Column(Numeric(5, 2), nullable=False, default=1.0)
    monthly_credit_cl = Column(Numeric(5, 2), nullable=False, default=1.0)
    monthly_credit_sl = Column(Numeric(5, 2), nullable=False, default=0.0)  # SL is annual grant, not monthly
    
    # PL eligibility (replaces old probation lock)
    pl_eligibility_months = Column(Integer, nullable=False, default=6)  # PL allowed only after 6 months
    
    # Backdated leave rule
    backdated_max_days = Column(Integer, nullable=False, default=7)  # Emergency backdated leave allowed up to 7 days
    
    # Carry forward / encashment
    carry_forward_pl_max = Column(Integer, nullable=False, default=4)  # Max PL carry forward
    
    # WFH policy
    wfh_max_days = Column(Integer, nullable=False, default=12)  # Max WFH days per year
    wfh_day_value = Column(Numeric(5, 2), nullable=False, default=0.5)  # WFH counts as 0.5 day
    
    # Old rules (kept for backward compatibility, but OFF by default)
    probation_months = Column(Integer, nullable=False, default=3)  # DEPRECATED: Use pl_eligibility_months instead
    cl_pl_notice_days = Column(Integer, nullable=False, default=3)
    cl_pl_monthly_cap = Column(Numeric(5, 2), nullable=False, default=4.0)
    enforce_monthly_cap = Column(Boolean, nullable=False, default=False)  # OFF by default (not in PDF)
    enforce_notice_days = Column(Boolean, nullable=False, default=False)  # Configurable, default OFF
    notice_days_cl_pl = Column(Integer, nullable=False, default=3)
    
    # Sick leave intimation (shift-dependent, default OFF)
    enforce_sick_intimation = Column(Boolean, nullable=False, default=False)
    sick_intimation_min_minutes = Column(Integer, nullable=False, default=120)  # 2 hours
    
    # Sandwich rule settings
    weekly_off_day = Column(Integer, nullable=False, default=7)  # ISO weekday Sunday=7
    sandwich_enabled = Column(Boolean, nullable=False, default=True)
    sandwich_include_weekly_off = Column(Boolean, nullable=False, default=True)
    sandwich_include_holidays = Column(Boolean, nullable=False, default=True)
    sandwich_include_rh = Column(Boolean, nullable=False, default=False)
    treat_event_as_non_working_for_sandwich = Column(Boolean, nullable=False, default=True)
    
    # HR override capability
    allow_hr_override = Column(Boolean, nullable=False, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.current_timestamp(), onupdate=func.current_timestamp(), nullable=False)
