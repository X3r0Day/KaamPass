import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.db import store


@pytest.fixture(scope="session")
def database():
    if os.getenv("APP_ENV") not in {"local", "test"} or os.getenv("VERCEL"):
        pytest.fail("Use a local PostgreSQL instance with APP_ENV=test")
    url = store.database_url()
    if url.host not in {"127.0.0.1", "localhost"}:
        pytest.fail("Tests create temporary schemas only in a loopback database")
    name = "kp_test_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as db:
        db.execute(text(f"CREATE SCHEMA {name}"))
    isolated = url.update_query_dict({"options": f"-csearch_path={name}"}).render_as_string(
        hide_password=False
    )
    try:
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("DATABASE_URL", isolated)
            mp.setenv("MIGRATION_DATABASE_URL", isolated)
            store.engine.cache_clear()
            command.upgrade(Config("alembic.ini"), "head")
            yield store.engine()
            store.engine().dispose()
            store.engine.cache_clear()
    finally:
        with admin.begin() as db:
            db.execute(text(f"DROP SCHEMA {name} CASCADE"))
        admin.dispose()


@pytest.fixture
def db(database):
    with database.connect() as conn:
        tx = conn.begin()
        try:
            yield conn
        finally:
            tx.rollback()
