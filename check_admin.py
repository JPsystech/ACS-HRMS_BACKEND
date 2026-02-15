from sqlalchemy import create_engine, text
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
with engine.connect() as conn:
    # Check admin users
    result = conn.execute(text('SELECT email, role, first_name, last_name FROM employees WHERE role = "ADMIN"'))
    admin_users = result.fetchall()
    print('Admin users found:', len(admin_users))
    for user in admin_users:
        print(f'Email: {user[0]}, Role: {user[1]}, Name: {user[2]} {user[3]}')
        
    # Also check the roles table to see if ADMIN role exists
    result = conn.execute(text('SELECT name, role_rank FROM roles WHERE name = "ADMIN"'))
    admin_role = result.fetchall()
    print('\nAdmin role configuration:', admin_role)
    
    # Check if we have any employees at all
    result = conn.execute(text('SELECT COUNT(*) FROM employees'))
    total_employees = result.scalar()
    print(f'\nTotal employees in database: {total_employees}')