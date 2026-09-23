"""
Migration V2.2 : Ajout des colonnes de géolocalisation GPS client sur orders et delivery_missions.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.core.asyncio_compat import use_selector_event_loop_on_windows
from app.db.session import async_session

use_selector_event_loop_on_windows()


async def migrate_gps():
    print("=== MIGRATION GPS FIELDS (V2.2) ===")
    async with async_session() as session:
        # 1. Orders
        await session.execute(
            text(
                "ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_latitude NUMERIC(10, 7);"
            )
        )
        await session.execute(
            text(
                "ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_longitude NUMERIC(10, 7);"
            )
        )
        print("[+] Colonnes delivery_latitude et delivery_longitude ajoutées à 'orders'.")

        # 2. Delivery Missions
        await session.execute(
            text(
                "ALTER TABLE delivery_missions ADD COLUMN IF NOT EXISTS destination_latitude NUMERIC(10, 7);"
            )
        )
        await session.execute(
            text(
                "ALTER TABLE delivery_missions ADD COLUMN IF NOT EXISTS destination_longitude NUMERIC(10, 7);"
            )
        )
        print("[+] Colonnes destination_latitude et destination_longitude ajoutées à 'delivery_missions'.")

        await session.commit()
    print("[SUCCESS] Migration des champs GPS terminée avec succès !")


if __name__ == "__main__":
    asyncio.run(migrate_gps())
