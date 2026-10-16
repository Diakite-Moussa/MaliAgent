"""
Base de connaissances (RAG) : documents commerçants (FAQ, politique de
retour, garanties, horaires...) et leurs chunks vectorisés pour la
recherche sémantique par l'agent IA. Voir app/services/knowledge.py.
"""

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BusinessScopedMixin, TimestampMixin, UUIDPKMixin

# Dimension du modèle d'embedding utilisé (nomic-embed-text = 768).
# À ajuster si vous changez de modèle d'embedding.
EMBEDDING_DIM = 768


class KnowledgeDocument(Base, UUIDPKMixin, BusinessScopedMixin, TimestampMixin):
    __tablename__ = "knowledge_documents"

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    document_type: Mapped[str] = mapped_column(String(20), nullable=False, default="pdf")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # status : "pending" | "processing" | "ready" | "failed"
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        "KnowledgeChunk", back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<KnowledgeDocument {self.filename!r} ({self.status})>"


class KnowledgeChunk(Base, UUIDPKMixin, BusinessScopedMixin, TimestampMixin):
    __tablename__ = "knowledge_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)

    document: Mapped["KnowledgeDocument"] = relationship("KnowledgeDocument", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<KnowledgeChunk doc={self.document_id} idx={self.chunk_index}>"