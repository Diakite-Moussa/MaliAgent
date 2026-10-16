"""
Ingestion et recherche sémantique dans la base de connaissances (RAG)
d'une boutique : extraction de texte, découpage en chunks, génération
d'embeddings, recherche par similarité cosinus via pgvector.
"""

import uuid
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.factory import get_llm_provider
from app.models import KnowledgeChunk, KnowledgeDocument

CHUNK_SIZE_CHARS = 1800       # ~ 400-500 tokens
CHUNK_OVERLAP_CHARS = 200
MAX_COSINE_DISTANCE = 0.7     # 0 = identique, 2 = opposé — seuil de pertinence


def _extract_text(file_path: str, document_type: str) -> str:
    if document_type == "pdf":
        reader = PdfReader(file_path)
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    return Path(file_path).read_text(encoding="utf-8", errors="ignore")


def _split_into_chunks(text_content: str) -> list[str]:
    text_content = " ".join(text_content.split())
    if not text_content:
        return []
    chunks = []
    start = 0
    while start < len(text_content):
        end = start + CHUNK_SIZE_CHARS
        chunks.append(text_content[start:end])
        start = end - CHUNK_OVERLAP_CHARS
    return chunks


async def ingest_document(session: AsyncSession, document: KnowledgeDocument) -> None:
    """
    Extrait le texte du document, le découpe, génère les embeddings et les
    enregistre. Met à jour document.status ("processing" -> "ready"/"failed").
    """
    try:
        document.status = "processing"
        await session.commit()

        raw_text = _extract_text(document.file_path, document.document_type)
        chunks_text = _split_into_chunks(raw_text)

        if not chunks_text:
            document.status = "failed"
            document.error_message = "Aucun texte exploitable extrait du document."
            await session.commit()
            return

        provider = get_llm_provider()
        vectors = await provider.embed(chunks_text)

        for idx, (chunk_text, vector) in enumerate(zip(chunks_text, vectors)):
            session.add(
                KnowledgeChunk(
                    business_id=document.business_id,
                    document_id=document.id,
                    content=chunk_text,
                    chunk_index=idx,
                    embedding=vector,
                )
            )

        document.status = "ready"
        document.error_message = None
        await session.commit()

    except Exception as exc:
        document.status = "failed"
        document.error_message = str(exc)[:500]
        await session.commit()


async def search_knowledge(
    session: AsyncSession,
    business_id: uuid.UUID,
    question: str,
    top_k: int = 3,
) -> list[str]:
    """
    Retourne les chunks les plus pertinents pour la question, filtrés
    STRICTEMENT par business_id (isolation multi-tenant).
    """
    provider = get_llm_provider()
    query_vectors = await provider.embed([question])
    if not query_vectors:
        return []
    query_vector = query_vectors[0]

    distance_col = KnowledgeChunk.embedding.cosine_distance(query_vector).label("distance")
    stmt = (
        select(KnowledgeChunk, distance_col)
        .where(KnowledgeChunk.business_id == business_id)
        .order_by(text("distance ASC"))
        .limit(top_k)
    )
    rows = (await session.execute(stmt)).all()

    return [chunk.content for chunk, distance in rows if distance <= MAX_COSINE_DISTANCE]