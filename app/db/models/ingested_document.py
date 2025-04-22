"""IngestedDocument model for tracking documents ingested into memory."""

from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy import String, Integer, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base

class IngestedDocument(Base):
    """Model for documents ingested into the memory system.
    
    This model tracks documents that have been ingested and chunked,
    storing metadata about the ingestion process and the document.
    """
    
    # Explicitly set table name to match existing database table
    __tablename__ = "ingested_documents"
    
    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    memory_ids: Mapped[List[str]] = mapped_column(JSON, default=list)
    
    # Additional metadata
    document_hash: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    content_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, default="processed")  # processed, failed, etc.
    
    # Optional metadata fields
    document_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict, nullable=True) 