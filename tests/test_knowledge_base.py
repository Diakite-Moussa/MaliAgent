import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.db.session import async_session
from app.models import KnowledgeChunk, KnowledgeDocument
from app.tools.executor import execute_tool


@pytest.mark.asyncio
async def test_knowledge_base_flow(client, two_businesses):
    tb = two_businesses
    headers_a = {"Authorization": f"Bearer {tb['token_a']}"}
    headers_b = {"Authorization": f"Bearer {tb['token_b']}"}

    # Dummy embedding vector of dimension 768
    dummy_vector = [0.05] * 768

    with patch("app.services.knowledge.get_llm_provider") as mock_provider_func:
        mock_provider = AsyncMock()
        mock_provider.embed.return_value = [dummy_vector]
        mock_provider_func.return_value = mock_provider

        # 1. Upload d'un document pour Boutique A
        doc_content = b"Politique de retour: les articles peuvent etre retournes sous 14 jours en magasin."
        files = {"file": ("faq_boutique.txt", doc_content, "text/plain")}

        res_upload = await client.post("/api/knowledge/upload", files=files, headers=headers_a)
        assert res_upload.status_code == 200, res_upload.text
        doc_data = res_upload.json()
        doc_id = doc_data["id"]
        assert doc_data["filename"] == "faq_boutique.txt"
        assert doc_data["status"] == "ready"

        # 2. Liste des documents pour Boutique A
        res_list_a = await client.get("/api/knowledge", headers=headers_a)
        assert res_list_a.status_code == 200
        docs_a = res_list_a.json()
        assert len(docs_a) >= 1
        assert any(d["id"] == doc_id for d in docs_a)

        # 3. Isolation multi-tenant : Boutique B ne voit pas le document de Boutique A
        res_list_b = await client.get("/api/knowledge", headers=headers_b)
        assert res_list_b.status_code == 200
        docs_b = res_list_b.json()
        assert not any(d["id"] == doc_id for d in docs_b)

        # 4. Exécution du tool search_knowledge_base pour Boutique A
        async with async_session() as session:
            tool_res = await execute_tool(
                session=session,
                business_id=tb["biz_a"].id,
                customer_id=uuid.uuid4(),
                tool_name="search_knowledge_base",
                arguments={"query": "Quelle est la politique de retour ?"},
            )
            assert "Politique de retour" in tool_res

        # 5. Tentative de suppression par Boutique B -> 404
        res_del_b = await client.delete(f"/api/knowledge/{doc_id}", headers=headers_b)
        assert res_del_b.status_code == 404

        # 6. Suppression par Boutique A -> 200
        res_del_a = await client.delete(f"/api/knowledge/{doc_id}", headers=headers_a)
        assert res_del_a.status_code == 200

        # Vérification en base que les chunks associés ont été supprimés en cascade
        async with async_session() as session:
            chunks = (await session.execute(
                select(KnowledgeChunk).where(KnowledgeChunk.document_id == uuid.UUID(doc_id))
            )).scalars().all()
            assert len(chunks) == 0
