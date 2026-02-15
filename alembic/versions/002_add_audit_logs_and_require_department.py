"""Add audit logs and require department

Revision ID: 002_audit_logs
Revises: 001_initial_auth
Create Date: 2026-01-31

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002_audit_logs'
down_revision: Union[str, None] = '001_initial_auth'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'audit_logs' in inspector.get_table_names():
        return
    # Create audit_logs table
    # Use CURRENT_TIMESTAMP so it works on both SQLite and Postgres
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('actor_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('meta_json', sa.JSON(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['actor_id'], ['employees.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)
    
    # Make department_id required (NOT NULL) for employees
    # First, ensure all existing employees have a department_id
    # If any exist without department_id, we'll set a default from first department
    # If no departments exist, this will fail - which is expected for fresh installs
    op.execute("""
        UPDATE employees 
        SET department_id = (SELECT id FROM departments LIMIT 1)
        WHERE department_id IS NULL
        AND EXISTS (SELECT 1 FROM departments LIMIT 1)
    """)
    
    # Now alter the column to be NOT NULL
    # SQLite doesn't support ALTER COLUMN, so we need to handle it differently
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        # SQLite workaround: create new table, copy data, drop old, rename
        op.execute("""
            CREATE TABLE employees_new (
                id INTEGER NOT NULL,
                emp_code VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                role VARCHAR NOT NULL,
                department_id INTEGER NOT NULL,
                reporting_manager_id INTEGER,
                password_hash VARCHAR NOT NULL,
                join_date DATE NOT NULL,
                active BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                FOREIGN KEY(department_id) REFERENCES departments (id),
                FOREIGN KEY(reporting_manager_id) REFERENCES employees (id),
                UNIQUE (emp_code)
            )
        """)
        op.execute("""
            INSERT INTO employees_new 
            SELECT * FROM employees WHERE department_id IS NOT NULL
        """)
        op.execute("DROP TABLE employees")
        op.execute("ALTER TABLE employees_new RENAME TO employees")
        op.execute("CREATE INDEX ix_employees_id ON employees (id)")
        op.execute("CREATE UNIQUE INDEX ix_employees_emp_code ON employees (emp_code)")
    else:
        # PostgreSQL and other databases support ALTER COLUMN
        op.alter_column('employees', 'department_id',
                        existing_type=sa.Integer(),
                        nullable=False)


def downgrade() -> None:
    # Revert department_id to nullable
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        # SQLite workaround for downgrade
        op.execute("""
            CREATE TABLE employees_old (
                id INTEGER NOT NULL,
                emp_code VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                role VARCHAR NOT NULL,
                department_id INTEGER,
                reporting_manager_id INTEGER,
                password_hash VARCHAR NOT NULL,
                join_date DATE NOT NULL,
                active BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                FOREIGN KEY(department_id) REFERENCES departments (id),
                FOREIGN KEY(reporting_manager_id) REFERENCES employees (id),
                UNIQUE (emp_code)
            )
        """)
        op.execute("INSERT INTO employees_old SELECT * FROM employees")
        op.execute("DROP TABLE employees")
        op.execute("ALTER TABLE employees_old RENAME TO employees")
        op.execute("CREATE INDEX ix_employees_id ON employees (id)")
        op.execute("CREATE UNIQUE INDEX ix_employees_emp_code ON employees (emp_code)")
    else:
        op.alter_column('employees', 'department_id',
                        existing_type=sa.Integer(),
                        nullable=True)
    
    # Drop audit_logs table
    op.drop_index(op.f('ix_audit_logs_id'), table_name='audit_logs')
    op.drop_table('audit_logs')
