"""
Migration : Crée les tables categories et product_variants,
ajoute les colonnes de liaison et effectue l'auto-seeding des catégories existantes.

Usage : python scripts/migrate_categories_and_variants.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text

from app.core.asyncio_compat import use_selector_event_loop_on_windows
from app.db.session import engine, async_session
from app.models.base import Base
from app.models.category import Category
from app.models.product_variant import ProductVariant
from app.models.product import Product

use_selector_event_loop_on_windows()


async def migrate():
    print("=== MIGRATION : CATÉGORIES ET VARIANTES DE PRODUITS ===")

    async with engine.begin() as conn:
        print("[1/3] Création des tables 'categories' et 'product_variants'...")
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn,
                tables=[Category.__table__, ProductVariant.__table__],
                checkfirst=True,
            )
        )

        print("[2/3] Ajout des colonnes de liaison avec ALTER TABLE IF NOT EXISTS...")
        await conn.execute(
            text(
                "ALTER TABLE products ADD COLUMN IF NOT EXISTS category_id UUID "
                "REFERENCES categories(id) ON DELETE SET NULL;"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS variant_id UUID "
                "REFERENCES product_variants(id) ON DELETE SET NULL;"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS variant_name VARCHAR(200);"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE stock_movements ADD COLUMN IF NOT EXISTS variant_id UUID "
                "REFERENCES product_variants(id) ON DELETE SET NULL;"
            )
        )

    print("[3/3] Migration des données : Auto-seeding des catégories depuis le catalogue existant...")
    async with async_session() as session:
        # Récupère tous les produits sans category_id
        products = (await session.execute(select(Product))).scalars().all()
        categories_created = 0
        products_linked = 0

        # Cache pour éviter les doublons par boutique
        # key: (business_id, category_name.lower()) -> Category
        existing_cats = (await session.execute(select(Category))).scalars().all()
        cat_map = {(c.business_id, c.name.strip().lower()): c for c in existing_cats}

        for prod in products:
            cat_name = (prod.category or "Général").strip()
            key = (prod.business_id, cat_name.lower())

            category = cat_map.get(key)
            if not category:
                category = Category(
                    business_id=prod.business_id,
                    name=cat_name.title(),
                    description=f"Catégorie {cat_name.title()}",
                )
                session.add(category)
                await session.flush()
                cat_map[key] = category
                categories_created += 1

            if prod.category_id != category.id:
                prod.category_id = category.id
                products_linked += 1

        await session.commit()
        print(f"-> {categories_created} catégorie(s) créée(s).")
        print(f"-> {products_linked} produit(s) rattaché(s) à leur catégorie formelle.")

    print("\n[SUCCESS] Migration Catégories & Variantes terminée avec succès !")


if __name__ == "__main__":
    asyncio.run(migrate())
