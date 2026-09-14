import asyncio
import sys
from pathlib import Path

# Ajouter la racine du projet au sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.asyncio_compat import use_selector_event_loop_on_windows
use_selector_event_loop_on_windows()

from sqlalchemy import text
from app.db.session import engine


async def migrate():
    print("Application des mises à jour du schéma PostgreSQL...")
    async with engine.begin() as conn:
        res = await conn.execute(text("SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid WHERE pg_type.typname = 'user_role';"))
        labels = [r[0] for r in res.fetchall()]
        print(f"Labels actuels dans user_role : {labels}")

        for val in ("SUPER_ADMIN", "super_admin"):
            if val not in labels:
                try:
                    await conn.execute(text(f"ALTER TYPE user_role ADD VALUE '{val}';"))
                    print(f" -> Valeur '{val}' ajoutée à l'enum user_role.")
                except Exception as e:
                    print(f" -> Erreur ajout {val}: {e}")

        # 2. Ajouter la colonne is_active sur businesses
        await conn.execute(
            text("ALTER TABLE businesses ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;")
        )
        print(" -> Colonne businesses.is_active vérifiée/créée.")

        # 3. Rendre users.business_id nullable
        await conn.execute(
            text("ALTER TABLE users ALTER COLUMN business_id DROP NOT NULL;")
        )
        print(" -> users.business_id rendu NULLABLE pour le super admin.")

    print("Migration terminée avec succès !")


if __name__ == "__main__":
    asyncio.run(migrate())
