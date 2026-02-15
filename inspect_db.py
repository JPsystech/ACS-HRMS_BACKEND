from sqlalchemy import create_engine, inspect
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
inspector = inspect(engine)

print('Existing tables:')
for table in inspector.get_table_names():
    print(f'  - {table}')
    if table == 'leave_balances':
        print('    Indexes:')
        for idx in inspector.get_indexes(table):
            print(f'      - {idx["name"]}')