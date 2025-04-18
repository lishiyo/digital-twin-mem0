"""Service for handling file operations and ingestion."""

import os
import hashlib
import logging
import mimetypes
from typing import Dict, List, Optional, Tuple, Union, Any
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

# Supported file types
SUPPORTED_EXTENSIONS = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".pdf": "application/pdf",
    # Add more supported types as needed
}


class FileService:
    """Service for handling file operations."""

    def __init__(self):
        """Initialize the file service."""
        self.data_dir = settings.DATA_DIR
        # Ensure the data directory exists
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)
            logger.info(f"Created data directory: {self.data_dir}")

    def list_files(self, directory: Optional[str] = None) -> List[Dict[str, Any]]:
        """List files in the data directory or a subdirectory.
        
        Args:
            directory: Optional subdirectory path (relative to data_dir)
            
        Returns:
            List of file information dictionaries
        """
        target_dir = self.data_dir
        if directory:
            target_dir = os.path.join(self.data_dir, directory)
            
        if not os.path.exists(target_dir):
            logger.warning(f"Directory does not exist: {target_dir}")
            return []
            
        file_list = []
        for root, _, files in os.walk(target_dir):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, self.data_dir)
                
                # Calculate file size and hash
                try:
                    file_size = os.path.getsize(file_path)
                    file_hash = self._calculate_file_hash(file_path)
                    
                    ext = os.path.splitext(file)[1].lower()
                    mime_type = SUPPORTED_EXTENSIONS.get(ext, mimetypes.guess_type(file)[0])
                    
                    file_list.append({
                        "filename": file,
                        "path": rel_path,
                        "size": file_size,
                        "hash": file_hash,
                        "mime_type": mime_type,
                        "supported": ext in SUPPORTED_EXTENSIONS,
                    })
                except Exception as e:
                    logger.error(f"Error processing file {file_path}: {e}")
        
        return file_list
    
    def read_file(self, file_path: str) -> Tuple[Optional[str], Optional[str]]:
        """Read a file from the data directory.
        
        Args:
            file_path: Path to the file (relative to data_dir)
            
        Returns:
            Tuple of (file_content, error_message)
        """
        full_path = os.path.join(self.data_dir, file_path)
        
        if not os.path.exists(full_path):
            logger.error(f"File does not exist: {full_path}")
            return None, f"File not found: {file_path}"
            
        # Check if file type is supported
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            logger.warning(f"Unsupported file type: {ext}")
            return None, f"Unsupported file type: {ext}"
            
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
                logger.info(f"Successfully read file: {file_path}")
                return content, None
        except Exception as e:
            logger.error(f"Error reading file {full_path}: {e}")
            return None, f"Error reading file: {str(e)}"
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of a file for deduplication.
        
        Args:
            file_path: Full path to the file
            
        Returns:
            SHA256 hash of the file
        """
        if not os.path.exists(file_path):
            return ""
            
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def validate_file(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """Validate a file for processing.
        
        Args:
            file_path: Path to the file (relative to data_dir)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        full_path = os.path.join(self.data_dir, file_path)
        
        # Check if file exists
        if not os.path.exists(full_path):
            return False, f"File not found: {file_path}"
            
        # Check file extension
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            return False, f"Unsupported file type: {ext}"
            
        # Check file size (example: limit to 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        file_size = os.path.getsize(full_path)
        if file_size > max_size:
            return False, f"File too large: {file_size} bytes (max: {max_size} bytes)"
            
        # File passed all checks
        return True, None
    
    def get_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract metadata from a file.
        
        Args:
            file_path: Path to the file (relative to data_dir)
            
        Returns:
            Dictionary of file metadata
        """
        full_path = os.path.join(self.data_dir, file_path)
        
        if not os.path.exists(full_path):
            return {"error": f"File not found: {file_path}"}
            
        try:
            # Basic file metadata
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(full_path)
            file_hash = self._calculate_file_hash(full_path)
            ext = os.path.splitext(file_path)[1].lower()
            mime_type = SUPPORTED_EXTENSIONS.get(ext, mimetypes.guess_type(file_name)[0])
            
            # File timestamps
            stat_info = os.stat(full_path)
            created_at = stat_info.st_ctime
            modified_at = stat_info.st_mtime
            
            metadata = {
                "filename": file_name,
                "path": file_path,
                "size": file_size,
                "hash": file_hash,
                "mime_type": mime_type,
                "extension": ext,
                "created_at": created_at,
                "modified_at": modified_at,
            }
            
            return metadata
        except Exception as e:
            logger.error(f"Error extracting metadata from {full_path}: {e}")
            return {"error": str(e), "path": file_path} 