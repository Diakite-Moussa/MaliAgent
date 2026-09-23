"""
Migration V0.5 : Ajout des colonnes preferred_language et preferred_channel_type sur customers.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.core.asyncio_compat import use_selector_event_loop_on_windows
from app.db.session import async_session

use_selector_event_loop_on_windows()


async def migrate_customer_voice():
    print("=== MIGRATION CUSTOMER VOICE FIELDS (V0.5) ===")
    async with async_session() as session:
        await session.execute(
            text(
                "ALTER TABLE customers ADD COLUMN IF NOT EXISTS preferred_language VARCHAR(10) DEFAULT 'fr' NOT NULL;"
            )
        )
        await session.execute(
            text(
                "ALTER TABLE customers ADD COLUMN IF NOT EXISTS preferred_channel_type VARCHAR(16) DEFAULT 'text' NOT NULL;"
            )
        )
        print("[+] Colonnes preferred_language et preferred_channel_type ajoutées à 'customers'.")
        await session.commit()
    print("[SUCCESS] Migration terminée avec succès !")


if __name__ == "__main__":
    asyncio.run(migrate_customer_voice())
