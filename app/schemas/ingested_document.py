"""Pydantic schemas for ingested documents."""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, ClassVar
from pydantic import BaseModel, Field, ConfigDict
import logging

logger = logging.getLogger(__name__)

class IngestedDocument(BaseModel):
    """Schema for documents ingested into memory."""
    
    id: str = Field(..., description="Document ID (often derived from filename)")
    filename: str = Field(..., description="Original filename")
    created_at: str = Field(..., description="When the document was ingested")
    chunk_count: int = Field(..., description="Number of chunks the document was split into")
    memory_ids: List[str] = Field(default_factory=list, description="IDs of memory chunks (limited to first few)")
    
    # Optional fields that may be present
    document_hash: Optional[str] = Field(None, description="Hash of the document content")
    user_id: Optional[str] = Field(None, description="ID of the user who owns the document")
    content_type: Optional[str] = Field(None, description="MIME type of the document")
    size_bytes: Optional[int] = Field(None, description="Size of the document in bytes")
    status: Optional[str] = Field("processed", description="Processing status")
    
    # Generic metadata fields
    document_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional document metadata")
    
    # Use ConfigDict for Pydantic v2 compatibility
    model_config = ConfigDict(from_attributes=True)
    
    @classmethod
    def from_memories(cls, memories: List[Dict[str, Any]], user_id: str) -> List["IngestedDocument"]:
        """
        Process raw memory data into structured IngestedDocument records.
        
        Args:
            memories: List of memory records from the memory service
            user_id: Current user ID for assigning ownership
            
        Returns:
            List of IngestedDocument objects
        """
        # Group memories by document ID
        document_map = {}
        document_metadata = {}
        
        for memory in memories:
            # Check for valid memory format
            if not isinstance(memory, dict):
                continue
                
            # Get memory ID with fallbacks
            memory_id = memory.get("memory_id")
            if not memory_id:
                memory_id = memory.get("id")
            if not memory_id:
                # Skip memories without IDs
                continue
                
            # Get document ID from metadata or memory ID
            metadata = memory.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            
            # Extract useful metadata 
            filename = metadata.get("filename", "Untitled Document")
            document_id = metadata.get("document_id")
            original_filename = metadata.get("original_filename", filename)
            chunk_index = metadata.get("chunk_index")
            total_chunks = metadata.get("total_chunks")
            
            # Try to get a meaningful document ID
            if not document_id:
                # If there's a chunk pattern in the memory ID, extract the base document ID
                if "_chunk_" in memory_id:
                    document_id = memory_id.split("_chunk_")[0]
                # If filename contains a hash or unique ID, use that for grouping
                elif original_filename and original_filename != "Untitled Document":
                    # Use original filename as document ID for better grouping
                    document_id = original_filename
                else:
                    # Last resort - use the memory ID itself
                    document_id = memory_id
            
            # Log ID extraction process
            logger.debug(f"Memory: {memory_id}, Document ID: {document_id}, Filename: {filename}, Original: {original_filename}")
            
            # Prefer original names over hashed names
            display_filename = original_filename or filename
            
            # If the filename looks like a hash, try to use title from metadata
            if (display_filename.endswith(".md") and len(display_filename) >= 30) or "hash" in display_filename:
                if metadata.get("title"):
                    display_filename = metadata.get("title")
                elif metadata.get("document_metadata", {}).get("title"):
                    display_filename = metadata.get("document_metadata", {}).get("title")
                else:
                    # Still looks like a hash, create a friendly name
                    display_filename = "Document " + display_filename[:8]
            
            # Ensure the filename has an extension if it's missing
            if not any(display_filename.endswith(ext) for ext in ['.md', '.txt', '.pdf', '.docx', '.html']):
                mime_type = metadata.get("mime_type") or metadata.get("content_type")
                if mime_type == "text/markdown":
                    display_filename += ".md"
                elif mime_type == "text/plain":
                    display_filename += ".txt"
                elif mime_type == "application/pdf":
                    display_filename += ".pdf"
                elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                    display_filename += ".docx"
                elif mime_type == "text/html":
                    display_filename += ".html"
            
            # Get or set user_id
            doc_user_id = metadata.get("user_id")
            if not doc_user_id:
                # Use the current user ID if available
                doc_user_id = user_id
            
            # Store metadata for document
            if document_id not in document_metadata:
                # Get created_at with proper format conversion
                created_at = metadata.get("created_at")
                # Convert timestamp to ISO format if it's a number
                if isinstance(created_at, (int, float)):
                    created_at = datetime.fromtimestamp(created_at, tz=timezone.utc).isoformat()
                elif not created_at:
                    created_at = datetime.now(timezone.utc).isoformat()
                
                document_metadata[document_id] = {
                    "filename": display_filename,
                    "created_at": created_at,
                    "chunk_count": 1,
                    "memory_ids": [memory_id],
                    # Store additional metadata that might be useful
                    "user_id": doc_user_id,
                    "size_bytes": metadata.get("size_bytes") or metadata.get("file_size") or metadata.get("size"),
                    "document_hash": metadata.get("document_hash") or metadata.get("hash"),
                    "content_type": metadata.get("content_type") or metadata.get("mime_type"),
                    "document_metadata": {k: v for k, v in metadata.items() 
                                         if k not in ["created_at", "user_id", "filename", "chunk_index", "total_chunks"]},
                }
            else:
                # Update existing document metadata
                document_metadata[document_id]["chunk_count"] += 1
                document_metadata[document_id]["memory_ids"].append(memory_id)
                
                # Fill in missing metadata if this chunk has it
                if not document_metadata[document_id]["user_id"] and metadata.get("user_id"):
                    document_metadata[document_id]["user_id"] = metadata.get("user_id")
                if not document_metadata[document_id]["size_bytes"] and (metadata.get("size_bytes") or metadata.get("file_size")):
                    document_metadata[document_id]["size_bytes"] = metadata.get("size_bytes") or metadata.get("file_size")
                if not document_metadata[document_id]["document_hash"] and (metadata.get("document_hash") or metadata.get("hash")):
                    document_metadata[document_id]["document_hash"] = metadata.get("document_hash") or metadata.get("hash")
                if not document_metadata[document_id]["content_type"] and (metadata.get("content_type") or metadata.get("mime_type")):
                    document_metadata[document_id]["content_type"] = metadata.get("content_type") or metadata.get("mime_type")
                
        # Create document objects from grouped metadata
        documents = []
        for doc_id, meta in document_metadata.items():
            documents.append(cls(
                id=doc_id,
                filename=meta["filename"],
                created_at=meta["created_at"],
                chunk_count=meta["chunk_count"],
                memory_ids=meta["memory_ids"][:5],  # Include some memory IDs for debugging
                document_hash=meta.get("document_hash"),
                user_id=meta.get("user_id"),
                content_type=meta.get("content_type"),
                size_bytes=meta.get("size_bytes"),
                status="processed",
                document_metadata=meta.get("document_metadata"),
            ))
            
        return documents 