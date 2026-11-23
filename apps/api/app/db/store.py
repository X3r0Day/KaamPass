import os
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Connection, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool


def database_url(migration: bool = False):
    url = make_url((os.getenv("MIGRATION_DATABASE_URL") if migration else None) or os.environ["DATABASE_URL"])
    if url.get_backend_name() not in ("postgres", "postgresql"):
        raise RuntimeError("PostgreSQL is required")
    if os.getenv("VERCEL") or os.getenv("APP_ENV", "production") not in {"local", "test"}:
        if url.query.get("sslmode") not in {"require", "verify-ca", "verify-full"}:
            raise RuntimeError("Database TLS is required")
    return url.set(drivername="postgresql+psycopg")


@lru_cache
def engine():
    return create_engine(database_url(), poolclass=NullPool, hide_parameters=True,
                         connect_args={"connect_timeout": 8, "prepare_threshold": None})


def transaction() -> Iterator[Connection]:
    with engine().begin() as db:
        yield db


def one(db, sql, **params):
    result = db.execute(text(sql), params).mappings().one_or_none()
    return dict(result) if result is not None else None


def many(db, sql, **params):
    return [dict(row) for row in db.execute(text(sql), params).mappings()]


def run(db, sql, **params):
    return db.execute(text(sql), params)
