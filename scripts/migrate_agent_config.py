"""
Migration V2.4 : Création de la table agent_configurations
(Sprint A3 — Personnalisation de l'agent IA par boutique).
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.core.asyncio_compat import use_selector_event_loop_on_windows
from app.db.session import engine

use_selector_event_loop_on_windows()


async def migrate_agent_config():
    print("=== MIGRATION AGENT CONFIGURATION (V2.4) ===")
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS agent_configurations (
                    id UUID PRIMARY KEY,
                    business_id UUID NOT NULL UNIQUE REFERENCES businesses(id) ON DELETE CASCADE,
                    agent_name VARCHAR(100) NOT NULL DEFAULT 'Assistant',
                    tone VARCHAR(50) NOT NULL DEFAULT 'chaleureux',
                    default_language VARCHAR(5) NOT NULL DEFAULT 'fr',
                    custom_rules VARCHAR(2000),
                    welcome_message VARCHAR(500),
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE UNIQUE INDEX IF NOT EXISTS ix_agent_configurations_business_id
                    ON agent_configurations(business_id);
                """
            )
        )
        print("[+] Table 'agent_configurations' et index unique créés.")
    print("[SUCCESS] Migration agent_configurations terminée avec succès !")


if __name__ == "__main__":
    asyncio.run(migrate_agent_config())
