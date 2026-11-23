"""WhatsApp drafts and idempotent webhook delivery."""

from alembic import op

revision = "0003_whatsapp"
down_revision = "0002_ghaziabad"


def upgrade():
    op.execute("""CREATE TABLE whatsapp_conversations (
        phone text PRIMARY KEY,
        draft jsonb NOT NULL DEFAULT '{}'::jsonb,
        lang text NOT NULL DEFAULT 'en' CHECK (lang IN ('en','hi')),
        assisted boolean,
        pending text,
        expected text,
        lookup jsonb NOT NULL DEFAULT '{}'::jsonb,
        updated_at timestamptz NOT NULL DEFAULT now()
    )""")
    op.execute("""CREATE TABLE whatsapp_events (
        id text PRIMARY KEY,
        reply jsonb,
        created_at timestamptz NOT NULL DEFAULT now(),
        claimed_until timestamptz,
        sent_at timestamptz
    )""")
    op.execute("CREATE INDEX whatsapp_events_retention ON whatsapp_events(created_at)")
    op.execute("CREATE INDEX whatsapp_conversations_retention ON whatsapp_conversations(updated_at)")


def downgrade():
    op.execute("DROP TABLE whatsapp_events")
    op.execute("DROP TABLE whatsapp_conversations")
