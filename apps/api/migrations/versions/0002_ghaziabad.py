"""Switch the launch district without rewriting existing people's work histories."""

import csv
from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "0002_ghaziabad"
down_revision = "0001_market"


def upgrade():
    op.execute("ALTER TABLE localities ADD COLUMN active boolean NOT NULL DEFAULT true")
    op.execute("UPDATE localities SET active=false WHERE district='Alwar'")
    op.execute("ALTER TABLE localities ALTER COLUMN district SET DEFAULT 'Ghaziabad'")
    op.execute("ALTER TABLE localities ALTER COLUMN state SET DEFAULT 'Uttar Pradesh'")
    with (Path(__file__).resolve().parents[1] / "seed/0002_places.csv").open(encoding="utf-8") as source:
        op.get_bind().execute(
            text("INSERT INTO localities(id,en,hi,pin) VALUES (:id,:en,:hi,:pin)"),
            list(csv.DictReader(source)),
        )


def downgrade():
    raise RuntimeError("Roll back application code; a district downgrade could orphan work histories.")
