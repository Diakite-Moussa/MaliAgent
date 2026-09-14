import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.asyncio_compat import use_selector_event_loop_on_windows

use_selector_event_loop_on_windows()

from sqlalchemy import text
from app.db.session import engine


async def migrate_audit_logs():
    print("Execution de la migration pour la table audit_logs...")
    async with engine.begin() as conn:
        await conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id UUID PRIMARY KEY,
                actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
                action VARCHAR(64) NOT NULL,
                resource_type VARCHAR(32) NOT NULL,
                resource_id VARCHAR(64),
                business_id UUID REFERENCES businesses(id) ON DELETE SET NULL,
                ip_address VARCHAR(45),
                details JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS ix_audit_logs_actor ON audit_logs(actor_user_id);
            CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs(action);
            CREATE INDEX IF NOT EXISTS ix_audit_logs_resource ON audit_logs(resource_type);
            CREATE INDEX IF NOT EXISTS ix_audit_logs_business ON audit_logs(business_id);
            CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs(created_at DESC);
        """)
        )
    print("Table audit_logs et index crees avec succes.")


if __name__ == "__main__":
    asyncio.run(migrate_audit_logs())
