"""
Connexion à la base de données.

Note : les modèles métier (Business, Product, Order, Customer...) ne sont
pas encore créés — volontairement. Priorité du Sprint 1 : valider le
tool calling avec Ollama Cloud (scripts/test_tool_calling.py) avant de
construire les modèles dessus. Voir section 23.1.1 du cahier des charges.
"""

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)
