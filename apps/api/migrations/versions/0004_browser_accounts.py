"""Keep browser-only registrations separate from verified phone accounts."""

from alembic import op

revision = "0004_browser_accounts"
down_revision = "0003_whatsapp"


def upgrade():
    op.execute(
        "ALTER TABLE profiles ADD COLUMN realm text NOT NULL DEFAULT 'member' CHECK (realm IN ('member','browser'))"
    )


def downgrade():
    raise RuntimeError("Browser accounts must not be merged into the verified realm")
