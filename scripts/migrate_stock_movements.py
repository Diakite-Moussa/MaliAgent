"""
Migration : Ajout de la table stock_movements et du seuil d'alerte
personnalisable par produit (low_stock_threshold).
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.core.asyncio_compat import use_selector_event_loop_on_windows
from app.db.session import async_session

use_selector_event_loop_on_windows()


async def migrate_stock_movements():
    print("=== MIGRATION STOCK MOVEMENTS ===")
    async with async_session() as session:
        await session.execute(
            text(
                "ALTER TABLE products ADD COLUMN IF NOT EXISTS "
                "low_stock_threshold INTEGER NOT NULL DEFAULT 3;"
            )
        )
        print("[+] Colonne low_stock_threshold ajoutée à 'products'.")

        await session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS stock_movements (
                    id UUID PRIMARY KEY,
                    business_id UUID NOT NULL REFERENCES businesses(id),
                    product_id UUID NOT NULL REFERENCES products(id),
                    order_id UUID NULL REFERENCES orders(id),
                    movement_type VARCHAR(30) NOT NULL,
                    quantity_change INTEGER NOT NULL,
                    quantity_before INTEGER NOT NULL,
                    quantity_after INTEGER NOT NULL,
                    reason VARCHAR(255) NULL,
                    created_by_user_id UUID NULL REFERENCES users(id),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
        )
        await session.execute(
            text("CREATE INDEX IF NOT EXISTS ix_stock_movements_business_id ON stock_movements(business_id);")
        )
        await session.execute(
            text("CREATE INDEX IF NOT EXISTS ix_stock_movements_product_id ON stock_movements(product_id);")
        )
        await session.execute(
            text("CREATE INDEX IF NOT EXISTS ix_stock_movements_order_id ON stock_movements(order_id);")
        )
        print("[+] Table 'stock_movements' créée avec ses index.")

        await session.commit()
    print("[SUCCESS] Migration stock_movements terminée avec succès !")


if __name__ == "__main__":
    asyncio.run(migrate_stock_movements())
