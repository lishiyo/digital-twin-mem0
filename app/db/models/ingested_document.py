"""IngestedDocument model for tracking documents ingested into memory."""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, String, Integer, DateTime, JSON
from sqlalchemy.sql import func

from app.db.base_class import Base

class IngestedDocument(Base):
    """Model for documents ingested into the memory system.
    
    This model tracks documents that have been ingested and chunked,
    storing metadata about the ingestion process and the document.
    """
    
    __tablename__ = "ingested_documents"
    
    id = Column(String, primary_key=True, index=True)
    filename = Column(String, index=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    chunk_count = Column(Integer, default=0)
    memory_ids = Column(JSON, default=list)
    
    # Additional metadata
    document_hash = Column(String, index=True, nullable=True)
    user_id = Column(String, index=True)
    content_type = Column(String, nullable=True)
    size_bytes = Column(Integer, nullable=True)
    status = Column(String, default="processed")  # processed, failed, etc.
    
    # Optional metadata fields
    document_metadata = Column(JSON, default=dict, nullable=True) 