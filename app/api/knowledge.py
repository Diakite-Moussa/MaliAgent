"""
Endpoints de gestion de la base de connaissances (RAG) du commerce.

Permet d'uploader, lister et supprimer les documents qui alimentent la base
de connaissances interne de l'agent. Les fichiers sont indexés en arrière-plan
et disponibles pour la recherche sémantique via `search_knowledge_base`.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select

from app.core.deps import get_current_business_id, get_current_user
from app.db.session import async_session
from app.models import KnowledgeDocument, User
from app.services.knowledge import ingest_document

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge Base"])

KNOWLEDGE_DIR = Path("storage") / "knowledge"
KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_TYPES = {"pdf": "pdf", "txt": "txt", "text/plain": "txt"}


@router.get("")
async def list_knowledge_documents(
    business_id: uuid.UUID = Depends(get_current_business_id),
):
    """Liste les documents de la base de connaissances du commerce."""
    async with async_session() as session:
        stmt = (
            select(KnowledgeDocument)
            .where(KnowledgeDocument.business_id == business_id)
            .order_by(KnowledgeDocument.created_at.desc())
        )
        docs = (await session.execute(stmt)).scalars().all()

        return [
            {
                "id": str(doc.id),
                "filename": doc.filename,
                "document_type": doc.document_type,
                "status": doc.status,
                "error_message": doc.error_message,
                "uploaded_by_user_id": str(doc.uploaded_by_user_id) if doc.uploaded_by_user_id else None,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "file_path": doc.file_path,
            }
            for doc in docs
        ]


@router.post("/upload")
async def upload_knowledge_document(
    file: UploadFile = File(...),
    business_id: uuid.UUID = Depends(get_current_business_id),
    user: User = Depends(get_current_user),
):
    """Téléverse un document PDF/TXT à indexer dans le RAG de la boutique."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nom de fichier manquant")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    document_type = ALLOWED_TYPES.get(ext, ALLOWED_TYPES.get((file.content_type or "").lower()))
    if document_type is None:
        raise HTTPException(
            status_code=400,
            detail="Format non autorisé. Seuls les fichiers PDF et TXT sont acceptés.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Fichier vide")

    stored_name = f"{uuid.uuid4()}.{document_type}"
    file_path = KNOWLEDGE_DIR / stored_name
    with open(file_path, "wb") as handle:
        handle.write(content)

    async with async_session() as session:
        document = KnowledgeDocument(
            business_id=business_id,
            filename=file.filename,
            file_path=str(file_path),
            document_type=document_type,
            status="pending",
            uploaded_by_user_id=user.id,
        )
        session.add(document)
        await session.commit()

        try:
            await ingest_document(session, document)
        except Exception:
            # Le service gère déjà le statut ; on évite de casser le flux upload si l'indexation fail.
            pass

        return {
            "id": str(document.id),
            "filename": document.filename,
            "document_type": document.document_type,
            "status": document.status,
            "error_message": document.error_message,
            "created_at": document.created_at.isoformat() if document.created_at else None,
        }


@router.delete("/{document_id}")
async def delete_knowledge_document(
    document_id: uuid.UUID,
    business_id: uuid.UUID = Depends(get_current_business_id),
):
    """Supprime un document et ses chunks vectorisés de la base de connaissances."""
    async with async_session() as session:
        stmt = select(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.business_id == business_id,
        )
        document = (await session.execute(stmt)).scalar_one_or_none()
        if not document:
            raise HTTPException(status_code=404, detail="Document introuvable")

        file_path = Path(document.file_path)
        if file_path.exists():
            file_path.unlink(missing_ok=True)

        await session.delete(document)
        await session.commit()

        return {"status": "deleted", "document_id": str(document_id)}