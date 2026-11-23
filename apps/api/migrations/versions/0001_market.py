"""The first Alwar work board."""

import csv
from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "0001_market"
down_revision = None


def upgrade():
    root = Path(__file__).resolve().parents[2]
    for statement in (root / "migrations/sql/0001.sql").read_text().split(";"):
        if statement.strip():
            op.execute(statement)
    conn = op.get_bind()
    for table, columns in [("localities", "id,en,hi,pin"), ("skills", "id,en,hi,aliases")]:
        with (root / f"migrations/seed/0001/{table}.csv").open(encoding="utf-8") as file:
            rows = list(csv.DictReader(file))
        fields = ", ".join(":" + key for key in columns.split(","))
        conn.execute(text(f"INSERT INTO {table} ({columns}) VALUES ({fields})"), rows)


def downgrade():
    for name in (
        "rate_buckets",
        "assignments",
        "interests",
        "invitations",
        "jobs",
        "worker_work_areas",
        "worker_skills",
        "identity_bindings",
        "profiles",
        "skills",
        "localities",
    ):
        op.execute(f"DROP TABLE {name}")
