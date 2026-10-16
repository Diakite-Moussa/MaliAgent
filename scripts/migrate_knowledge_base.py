"""
Migration : active pgvector et crée les tables de la base de connaissances (RAG).

Usage : python scripts/migrate_knowledge_base.py
"""

import asyncio

from sqlalchemy import text

from app.core.asyncio_compat import use_selector_event_loop_on_windows
from app.db.session import engine
from app.models.base import Base
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument  # noqa: F401

use_selector_event_loop_on_windows()


async def migrate():
    async with engine.begin() as conn:
        print("[*] Activation de l'extension pgvector...")
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))

        print("[*] Création des tables knowledge_documents / knowledge_chunks...")
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn,
                tables=[KnowledgeDocument.__table__, KnowledgeChunk.__table__],
                checkfirst=True,
            )
        )

        print("[*] Création de l'index vectoriel (ivfflat, distance cosinus)...")
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_embedding "
                "ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);"
            )
        )

    print("[SUCCESS] Base de connaissances (pgvector) prête !")


if __name__ == "__main__":
    asyncio.run(migrate())