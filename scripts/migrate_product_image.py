"""
Migration V2.3 : Ajout de la colonne image_url sur la table products
(Sprint A1 — Photos de produits).
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.core.asyncio_compat import use_selector_event_loop_on_windows
from app.db.session import async_session

use_selector_event_loop_on_windows()


async def migrate_product_image():
    print("=== MIGRATION PRODUCT IMAGE (V2.3) ===")
    async with async_session() as session:
        await session.execute(
            text(
                "ALTER TABLE products ADD COLUMN IF NOT EXISTS image_url VARCHAR(500);"
            )
        )
        print("[+] Colonne image_url ajoutée à 'products'.")

        await session.commit()
    print("[SUCCESS] Migration image_url terminée avec succès !")


if __name__ == "__main__":
    asyncio.run(migrate_product_image())