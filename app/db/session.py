"""
Connexion à la base de données.

Note : les modèles métier (Business, Product, Order, Customer...) ne sont
pas encore créés — volontairement. Priorité du Sprint 1 : valider le
tool calling avec Ollama Cloud (scripts/test_tool_calling.py) avant de
construire les modèles dessus. Voir section 23.1.1 du cahier des charges.
"""

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings

def _get_async_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://") and not url.startswith("postgresql+"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


database_url = _get_async_database_url(settings.database_url)

engine_kwargs = {"echo": False, "pool_pre_ping": True}
if not database_url.startswith("sqlite"):
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
    })

engine = create_async_engine(database_url, **engine_kwargs)
async_session = async_sessionmaker(engine, expire_on_commit=False)


