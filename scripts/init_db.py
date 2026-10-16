"""
Crée les tables en base à partir des modèles SQLAlchemy.

Usage :
    python scripts/init_db.py

Note : pas de migrations Alembic pour l'instant, volontairement — le schéma
va encore bouger pendant les premiers sprints. Ce script suffit pour le
développement local. Alembic sera introduit dès que le schéma se stabilise
(avant le premier pilote réel, au plus tard), pour ne pas perdre de données
en production lors d'un changement de schéma.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app.core.asyncio_compat import use_selector_event_loop_on_windows  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.models import Base  # noqa: E402

use_selector_event_loop_on_windows()


async def main():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.run_sync(Base.metadata.create_all)
    print("Tables créées.")


if __name__ == "__main__":
    asyncio.run(main())
