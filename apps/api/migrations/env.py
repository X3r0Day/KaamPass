from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from app.db.store import database_url

with create_engine(database_url(migration=True), poolclass=NullPool, hide_parameters=True).connect() as conn:
    context.configure(connection=conn, transactional_ddl=True)
    with context.begin_transaction():
        context.run_migrations()
