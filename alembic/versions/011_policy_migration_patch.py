"""Policy Migration Patch - Update to FINAL PDF Policy

Revision ID: 011_policy_migration
Revises: 010_compoff_tables
Create Date: 2026-01-31

This migration implements the FINAL Leave Policy PDF changes:
- Annual entitlements: PL=7, CL=5, SL=6, RH=1
- Monthly credit: +1 PL, +1 CL (SL is annual grant)
- PL eligibility: 6 months (replaces probation lock)
- Backdated leave: 7 days max
- Carry forward/encashment: Max 4 PL carry forward
- WFH policy: 12 days/year, 0.5 day value
- Company events blocking leave
- HR policy actions tracking
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '011_policy_migration'
down_revision: Union[str, None] = '010_compoff_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    
    if is_sqlite:
        datetime_default = sa.text('CURRENT_TIMESTAMP')
        boolean_type = sa.Integer()
        enum_type = sa.String()
    else:
        datetime_default = sa.text('now()')
        boolean_type = sa.Boolean()
        enum_type = postgresql.ENUM
    
    # ============================================
    # 1. Update policy_settings table
    # ============================================
    # Check if columns already exist (for partial migration recovery / idempotent run)
    inspector = sa.inspect(bind)

    def add_column_if_not_exists(table_name, column_name, column_def):
        existing = [col['name'] for col in inspector.get_columns(table_name)]
        if column_name not in existing:
            op.add_column(table_name, column_def)
    
    add_column_if_not_exists('policy_settings', 'annual_pl', sa.Column('annual_pl', sa.Integer(), nullable=False, server_default='7'))
    add_column_if_not_exists('policy_settings', 'annual_cl', sa.Column('annual_cl', sa.Integer(), nullable=False, server_default='5'))
    add_column_if_not_exists('policy_settings', 'annual_sl', sa.Column('annual_sl', sa.Integer(), nullable=False, server_default='6'))
    add_column_if_not_exists('policy_settings', 'annual_rh', sa.Column('annual_rh', sa.Integer(), nullable=False, server_default='1'))
    add_column_if_not_exists('policy_settings', 'monthly_credit_pl', sa.Column('monthly_credit_pl', sa.Numeric(5, 2), nullable=False, server_default='1.0'))
    add_column_if_not_exists('policy_settings', 'monthly_credit_cl', sa.Column('monthly_credit_cl', sa.Numeric(5, 2), nullable=False, server_default='1.0'))
    add_column_if_not_exists('policy_settings', 'monthly_credit_sl', sa.Column('monthly_credit_sl', sa.Numeric(5, 2), nullable=False, server_default='0.0'))
    add_column_if_not_exists('policy_settings', 'pl_eligibility_months', sa.Column('pl_eligibility_months', sa.Integer(), nullable=False, server_default='6'))
    add_column_if_not_exists('policy_settings', 'backdated_max_days', sa.Column('backdated_max_days', sa.Integer(), nullable=False, server_default='7'))
    add_column_if_not_exists('policy_settings', 'carry_forward_pl_max', sa.Column('carry_forward_pl_max', sa.Integer(), nullable=False, server_default='4'))
    add_column_if_not_exists('policy_settings', 'wfh_max_days', sa.Column('wfh_max_days', sa.Integer(), nullable=False, server_default='12'))
    add_column_if_not_exists('policy_settings', 'wfh_day_value', sa.Column('wfh_day_value', sa.Numeric(5, 2), nullable=False, server_default='0.5'))
    add_column_if_not_exists('policy_settings', 'enforce_monthly_cap', sa.Column('enforce_monthly_cap', boolean_type, nullable=False, server_default=sa.text('0') if is_sqlite else sa.text('false')))
    add_column_if_not_exists('policy_settings', 'enforce_notice_days', sa.Column('enforce_notice_days', boolean_type, nullable=False, server_default=sa.text('0') if is_sqlite else sa.text('false')))
    add_column_if_not_exists('policy_settings', 'notice_days_cl_pl', sa.Column('notice_days_cl_pl', sa.Integer(), nullable=False, server_default='3'))
    add_column_if_not_exists('policy_settings', 'enforce_sick_intimation', sa.Column('enforce_sick_intimation', boolean_type, nullable=False, server_default=sa.text('0') if is_sqlite else sa.text('false')))
    add_column_if_not_exists('policy_settings', 'sick_intimation_min_minutes', sa.Column('sick_intimation_min_minutes', sa.Integer(), nullable=False, server_default='120'))
    add_column_if_not_exists('policy_settings', 'treat_event_as_non_working_for_sandwich', sa.Column('treat_event_as_non_working_for_sandwich', boolean_type, nullable=False, server_default=sa.text('1') if is_sqlite else sa.text('true')))
    
    # Backfill existing policy_settings rows with new defaults
    if is_sqlite:
        op.execute("""
            UPDATE policy_settings 
            SET annual_pl = 7, annual_cl = 5, annual_sl = 6, annual_rh = 1,
                monthly_credit_pl = 1.0, monthly_credit_cl = 1.0, monthly_credit_sl = 0.0,
                pl_eligibility_months = 6, backdated_max_days = 7, carry_forward_pl_max = 4,
                wfh_max_days = 12, wfh_day_value = 0.5,
                enforce_monthly_cap = 0, enforce_notice_days = 0,
                enforce_sick_intimation = 0, sick_intimation_min_minutes = 120,
                treat_event_as_non_working_for_sandwich = 1
        """)
    else:
        op.execute("""
            UPDATE policy_settings 
            SET annual_pl = 7, annual_cl = 5, annual_sl = 6, annual_rh = 1,
                monthly_credit_pl = 1.0, monthly_credit_cl = 1.0, monthly_credit_sl = 0.0,
                pl_eligibility_months = 6, backdated_max_days = 7, carry_forward_pl_max = 4,
                wfh_max_days = 12, wfh_day_value = 0.5,
                enforce_monthly_cap = false, enforce_notice_days = false,
                enforce_sick_intimation = false, sick_intimation_min_minutes = 120,
                treat_event_as_non_working_for_sandwich = true
        """)
    
    # ============================================
    # 2. Update leave_balances table
    # ============================================
    add_column_if_not_exists('leave_balances', 'pl_carried_forward', sa.Column('pl_carried_forward', sa.Numeric(5, 2), nullable=False, server_default='0'))
    add_column_if_not_exists('leave_balances', 'pl_encash_days', sa.Column('pl_encash_days', sa.Numeric(5, 2), nullable=False, server_default='0'))
    
    # ============================================
    # 3. Update leave_requests table
    # ============================================
    add_column_if_not_exists('leave_requests', 'auto_converted_to_lwp', sa.Column('auto_converted_to_lwp', boolean_type, nullable=False, server_default=sa.text('0') if is_sqlite else sa.text('false')))
    add_column_if_not_exists('leave_requests', 'auto_lwp_reason', sa.Column('auto_lwp_reason', sa.Text(), nullable=True))
    
    # Add CANCELLED_BY_COMPANY to LeaveStatus enum
    # For SQLite, we'll use String; for PostgreSQL, we need to alter the enum
    if not is_sqlite:
        # PostgreSQL: Alter enum type
        op.execute("ALTER TYPE leavestatus ADD VALUE IF NOT EXISTS 'CANCELLED_BY_COMPANY'")
    # For SQLite, the enum is stored as String, so no change needed
    
    # ============================================
    # 4. Create company_events table (if not exists)
    # ============================================
    existing_tables = inspector.get_table_names()
    if 'company_events' not in existing_tables:
        # For SQLite, include unique constraint in table creation
        if is_sqlite:
            op.create_table(
                'company_events',
                sa.Column('id', sa.Integer(), nullable=False),
                sa.Column('year', sa.Integer(), nullable=False),
                sa.Column('date', sa.Date(), nullable=False),
                sa.Column('name', sa.String(length=255), nullable=False),
                sa.Column('active', boolean_type, nullable=False, server_default=sa.text('1')),
                sa.Column('created_at', sa.DateTime(timezone=True), server_default=datetime_default, nullable=False),
                sa.Column('updated_at', sa.DateTime(timezone=True), server_default=datetime_default, nullable=False),
                sa.PrimaryKeyConstraint('id'),
                sa.UniqueConstraint('year', 'date', name='uq_event_year_date')
            )
        else:
            op.create_table(
                'company_events',
                sa.Column('id', sa.Integer(), nullable=False),
                sa.Column('year', sa.Integer(), nullable=False),
                sa.Column('date', sa.Date(), nullable=False),
                sa.Column('name', sa.String(length=255), nullable=False),
                sa.Column('active', boolean_type, nullable=False, server_default=sa.text('true')),
                sa.Column('created_at', sa.DateTime(timezone=True), server_default=datetime_default, nullable=False),
                sa.Column('updated_at', sa.DateTime(timezone=True), server_default=datetime_default, nullable=False),
                sa.PrimaryKeyConstraint('id')
            )
            op.create_unique_constraint('uq_event_year_date', 'company_events', ['year', 'date'])
        
        op.create_index(op.f('ix_company_events_id'), 'company_events', ['id'], unique=False)
        op.create_index(op.f('ix_company_events_year'), 'company_events', ['year'], unique=False)
        op.create_index(op.f('ix_company_events_date'), 'company_events', ['date'], unique=False)
    
    # ============================================
    # 5. Create wfh_requests table (if not exists)
    # ============================================
    if 'wfh_requests' not in existing_tables:
        if is_sqlite:
            wfh_status_enum = sa.String()
            # For SQLite, include unique constraint in table creation
            op.create_table(
                'wfh_requests',
                sa.Column('id', sa.Integer(), nullable=False),
                sa.Column('employee_id', sa.Integer(), nullable=False),
                sa.Column('request_date', sa.Date(), nullable=False),
                sa.Column('reason', sa.Text(), nullable=True),
                sa.Column('status', wfh_status_enum, nullable=False, server_default="PENDING"),
                sa.Column('day_value', sa.Numeric(5, 2), nullable=False, server_default='0.5'),
                sa.Column('applied_at', sa.DateTime(timezone=True), server_default=datetime_default, nullable=False),
                sa.Column('approved_by', sa.Integer(), nullable=True),
                sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
                sa.Column('created_at', sa.DateTime(timezone=True), server_default=datetime_default, nullable=False),
                sa.Column('updated_at', sa.DateTime(timezone=True), server_default=datetime_default, nullable=False),
                sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ),
                sa.ForeignKeyConstraint(['approved_by'], ['employees.id'], ),
                sa.PrimaryKeyConstraint('id'),
                sa.UniqueConstraint('employee_id', 'request_date', name='uq_wfh_employee_date')
            )
        else:
            # Create enum type idempotently
            wfh_status_enum = postgresql.ENUM('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED', name='wfhstatus')
            wfh_status_enum.create(bind, checkfirst=True)
            op.create_table(
                'wfh_requests',
                sa.Column('id', sa.Integer(), nullable=False),
                sa.Column('employee_id', sa.Integer(), nullable=False),
                sa.Column('request_date', sa.Date(), nullable=False),
                sa.Column('reason', sa.Text(), nullable=True),
                sa.Column('status', wfh_status_enum, nullable=False, server_default="PENDING"),
                sa.Column('day_value', sa.Numeric(5, 2), nullable=False, server_default='0.5'),
                sa.Column('applied_at', sa.DateTime(timezone=True), server_default=datetime_default, nullable=False),
                sa.Column('approved_by', sa.Integer(), nullable=True),
                sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
                sa.Column('created_at', sa.DateTime(timezone=True), server_default=datetime_default, nullable=False),
                sa.Column('updated_at', sa.DateTime(timezone=True), server_default=datetime_default, nullable=False),
                sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ),
                sa.ForeignKeyConstraint(['approved_by'], ['employees.id'], ),
                sa.PrimaryKeyConstraint('id')
            )
            op.create_unique_constraint('uq_wfh_employee_date', 'wfh_requests', ['employee_id', 'request_date'])
        
        op.create_index(op.f('ix_wfh_requests_id'), 'wfh_requests', ['id'], unique=False)
        op.create_index(op.f('ix_wfh_requests_employee_id'), 'wfh_requests', ['employee_id'], unique=False)
        op.create_index(op.f('ix_wfh_requests_request_date'), 'wfh_requests', ['request_date'], unique=False)
    
    # ============================================
    # 6. Create hr_policy_actions table (if not exists)
    # ============================================
    if 'hr_policy_actions' not in existing_tables:
        if is_sqlite:
            action_type_enum = sa.String()
            json_type = sa.Text()
        else:
            action_type_enum = postgresql.ENUM('DEDUCT_PL_3', 'MARK_ABSCONDED', 'MEDICAL_CERT_MISSING_PENALTY', 
                                               'CANCEL_APPROVED_LEAVE', 'OTHER', name='hrpolicyactiontype', create_type=True)
            json_type = postgresql.JSON
        
        op.create_table(
            'hr_policy_actions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('employee_id', sa.Integer(), nullable=False),
            sa.Column('action_type', action_type_enum, nullable=False),
            sa.Column('reference_entity_type', sa.String(length=50), nullable=True),
            sa.Column('reference_entity_id', sa.Integer(), nullable=True),
            sa.Column('meta_json', json_type, nullable=True),
            sa.Column('action_by', sa.Integer(), nullable=False),
            sa.Column('action_at', sa.DateTime(timezone=True), server_default=datetime_default, nullable=False),
            sa.Column('remarks', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=datetime_default, nullable=False),
            sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ),
            sa.ForeignKeyConstraint(['action_by'], ['employees.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_hr_policy_actions_id'), 'hr_policy_actions', ['id'], unique=False)
        op.create_index(op.f('ix_hr_policy_actions_employee_id'), 'hr_policy_actions', ['employee_id'], unique=False)
        op.create_index(op.f('ix_hr_policy_actions_action_type'), 'hr_policy_actions', ['action_type'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    
    # Drop new tables
    op.drop_table('hr_policy_actions')
    op.drop_table('wfh_requests')
    op.drop_table('company_events')
    
    # Remove columns from leave_requests
    op.drop_column('leave_requests', 'auto_lwp_reason')
    op.drop_column('leave_requests', 'auto_converted_to_lwp')
    
    # Remove columns from leave_balances
    op.drop_column('leave_balances', 'pl_encash_days')
    op.drop_column('leave_balances', 'pl_carried_forward')
    
    # Remove columns from policy_settings
    op.drop_column('policy_settings', 'treat_event_as_non_working_for_sandwich')
    op.drop_column('policy_settings', 'sick_intimation_min_minutes')
    op.drop_column('policy_settings', 'enforce_sick_intimation')
    op.drop_column('policy_settings', 'notice_days_cl_pl')
    op.drop_column('policy_settings', 'enforce_notice_days')
    op.drop_column('policy_settings', 'enforce_monthly_cap')
    op.drop_column('policy_settings', 'wfh_day_value')
    op.drop_column('policy_settings', 'wfh_max_days')
    op.drop_column('policy_settings', 'carry_forward_pl_max')
    op.drop_column('policy_settings', 'backdated_max_days')
    op.drop_column('policy_settings', 'pl_eligibility_months')
    op.drop_column('policy_settings', 'monthly_credit_sl')
    op.drop_column('policy_settings', 'monthly_credit_cl')
    op.drop_column('policy_settings', 'monthly_credit_pl')
    op.drop_column('policy_settings', 'annual_rh')
    op.drop_column('policy_settings', 'annual_sl')
    op.drop_column('policy_settings', 'annual_cl')
    op.drop_column('policy_settings', 'annual_pl')
    
    # Drop enum types (PostgreSQL only)
    if not is_sqlite:
        op.execute("DROP TYPE IF EXISTS hrpolicyactiontype")
        op.execute("DROP TYPE IF EXISTS wfhstatus")
