"""Utilities for chunking documents into manageable pieces."""

import logging
import re
from typing import Dict, List, Optional, Tuple, Any, Callable
import hashlib

import tiktoken

logger = logging.getLogger(__name__)

# Default chunking parameters
DEFAULT_CHUNK_SIZE = 1000  # tokens
DEFAULT_CHUNK_OVERLAP = 100  # tokens
DEFAULT_MODEL = "gpt-4o-mini"  # Model to use for token counting

# Section headers pattern (common in documents)
SECTION_HEADER_PATTERNS = [
    r'^#+\s+.+$',  # Markdown headers
    r'^.*?\n[=\-]{3,}$',  # Underlined headers
    r'^\s*(?:SECTION|CHAPTER|PART)\s+\d+.*$',  # Section/Chapter labels
    r'^\s*\d+\.\d*\s+[A-Z].*$',  # Numbered sections (1.1, 1.2.3, etc.)
    r'^\s*[A-Z][A-Z\s]+[A-Z]$',  # ALL CAPS HEADERS
]

# Compile patterns for efficiency
SECTION_HEADER_REGEX = re.compile('|'.join(f'({pattern})' for pattern in SECTION_HEADER_PATTERNS), re.MULTILINE)

# Metadata extraction patterns
METADATA_PATTERNS = {
    'title': [
        r'^#\s+(.+)$',  # Markdown title
        r'^Title:\s*(.+)$',  # Explicit title
        r'^(?:\s*\n)*([A-Z][^.!?]*(?:[.!?]|\n\n|\n$))',  # First sentence in ALL CAPS or Title Case
    ],
    'author': [
        r'^Author(?:s)?:\s*(.+)$',
        r'(?:written|created|compiled|prepared)\s+by\s+([^.]+)',
        r'^\s*By\s+([^.]+)'
    ],
    'date': [
        r'^Date:\s*(.+)$',
        r'(?:created|published|updated|revised)\s+on\s+([^.]+)',
        r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',  # MM/DD/YYYY or similar
        r'\d{4}[/-]\d{1,2}[/-]\d{1,2}',  # YYYY/MM/DD or similar
    ],
    'summary': [
        r'^Abstract:\s*(.+(?:\n(?!\n).+)*)$',
        r'^Summary:\s*(.+(?:\n(?!\n).+)*)$',
        r'^TL;DR:\s*(.+(?:\n(?!\n).+)*)$',
    ]
}


class DocumentChunker:
    """Class for chunking documents into smaller pieces."""
    
    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        model: str = DEFAULT_MODEL
    ):
        """Initialize the document chunker.
        
        Args:
            chunk_size: Maximum size of chunks in tokens
            chunk_overlap: Overlap between chunks in tokens
            model: Model to use for token counting
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.model = model
        
        # Initialize tokenizer
        try:
            self.tokenizer = tiktoken.encoding_for_model(model)
        except Exception as e:
            logger.warning(f"Failed to load tokenizer for {model}: {e}. Using cl100k_base instead.")
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
    
    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in text.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens
        """
        return len(self.tokenizer.encode(text))
    
    def extract_document_metadata(self, content: str) -> Dict[str, Any]:
        """Extract metadata from document content.
        
        Args:
            content: Document content
            
        Returns:
            Dictionary of extracted metadata
        """
        metadata = {}
        
        # Try to extract metadata for each type
        for meta_type, patterns in METADATA_PATTERNS.items():
            for pattern in patterns:
                matches = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
                if matches:
                    try:
                        # Try to get the first capture group
                        value = matches.group(1).strip()
                        metadata[meta_type] = value
                        break
                    except IndexError:
                        # If no capture group, use the whole match
                        metadata[meta_type] = matches.group(0).strip()
                        break
        
        # Extract sections if we can find headers
        section_headers = SECTION_HEADER_REGEX.findall(content)
        if section_headers:
            # Flatten results
            section_headers = [h for sublist in section_headers for h in sublist if h]
            # Only keep the first few
            sections = section_headers[:5]
            if sections:
                metadata["sections"] = sections
        
        # Calculate document complexity metrics
        sentences = re.split(r'[.!?]+', content)
        avg_sentence_length = sum(len(s.split()) for s in sentences) / max(1, len(sentences))
        metadata["metrics"] = {
            "sentences": len(sentences),
            "avg_sentence_length": round(avg_sentence_length, 1),
            "token_count": self.count_tokens(content),
            "char_count": len(content)
        }
        
        return metadata
        
    def get_optimized_chunk_size(self, content: str) -> int:
        """Calculate an optimized chunk size based on content length.
        
        Args:
            content: Document content
            
        Returns:
            Optimized chunk size
        """
        total_tokens = self.count_tokens(content)
        
        # For very small documents, use a smaller chunk size
        if total_tokens < self.chunk_size:
            return max(50, total_tokens)
        
        # For medium documents, use the default size
        if total_tokens < 10000:
            return self.chunk_size
            
        # For larger documents, consider increasing chunk size
        # to reduce the number of chunks
        if total_tokens < 50000:
            return min(1500, self.chunk_size * 1.5)
            
        # For very large documents, use larger chunks
        return min(2000, self.chunk_size * 2)
    
    def chunk_by_tokens(self, content: str) -> List[str]:
        """Split text into chunks based on token count.
        
        Args:
            content: Content to split into chunks
            
        Returns:
            List of text chunks
        """
        if not content.strip():
            return []
            
        tokens = self.tokenizer.encode(content)
        chunks = []
        
        # Use adaptive chunk size for efficiency
        chunk_size = min(self.get_optimized_chunk_size(content), self.chunk_size)
        
        # Create chunks
        for i in range(0, len(tokens), chunk_size - self.chunk_overlap):
            chunk_tokens = tokens[i:i + chunk_size]
            chunk_text = self.tokenizer.decode(chunk_tokens)
            
            # Ensure we don't have tiny chunks at the end
            if i > 0 and len(chunk_tokens) < self.chunk_overlap * 2:
                # This would be a very small final chunk, so just extend the previous chunk
                chunks[-1] = self.tokenizer.decode(tokens[i - (chunk_size - self.chunk_overlap):i + len(chunk_tokens)])
            else:
                chunks.append(chunk_text)
        
        return chunks
    
    def chunk_by_sections(self, content: str) -> List[str]:
        """Split text by section headers.
        
        Args:
            content: Content to split
            
        Returns:
            List of section chunks
        """
        if not content.strip():
            return []
            
        # Find all section headers
        matches = list(SECTION_HEADER_REGEX.finditer(content))
        
        # If no sections found, return the whole content
        if not matches:
            return [content]
            
        chunks = []
        for i, match in enumerate(matches):
            # For the first section, include everything before it
            if i == 0 and match.start() > 0:
                intro_text = content[:match.start()].strip()
                if intro_text:
                    chunks.append(intro_text)
                    
            # Determine section end
            if i < len(matches) - 1:
                section_end = matches[i+1].start()
            else:
                section_end = len(content)
                
            # Extract section
            section_text = content[match.start():section_end].strip()
            if section_text:
                chunks.append(section_text)
                
        return chunks
    
    def chunk_by_separator(
        self, 
        content: str, 
        separators: List[str] = ["\n\n", "\n", ". ", " ", ""],
        min_chunk_size: int = 100
    ) -> List[str]:
        """Split text into chunks using a list of separators.
        
        This tries to create chunks at natural boundaries.
        
        Args:
            content: Content to split into chunks
            separators: List of separators to use, in order of preference
            min_chunk_size: Minimum chunk size in tokens
            
        Returns:
            List of text chunks
        """
        if not content.strip():
            return []
            
        chunks = []
        current_chunk = []
        current_chunk_tokens = 0
        
        # Helper function to split text by a separator
        def split_by_separator(text: str, sep: str) -> List[str]:
            if sep == "":
                return list(text)
            return text.split(sep)
        
        # Process each separator
        remaining_text = content
        for separator in separators:
            segments = split_by_separator(remaining_text, separator)
            remaining_segments = []
            
            for segment in segments:
                if not segment:
                    continue
                    
                # Add separator back if it's not empty
                if separator:
                    segment_with_sep = segment + separator
                else:
                    segment_with_sep = segment
                    
                segment_tokens = self.count_tokens(segment_with_sep)
                
                # If adding this segment exceeds chunk size, create a new chunk
                if current_chunk_tokens + segment_tokens > self.chunk_size:
                    # If current chunk is not empty, save it
                    if current_chunk:
                        chunks.append("".join(current_chunk))
                        current_chunk = []
                        current_chunk_tokens = 0
                    
                    # If the segment itself exceeds chunk size, process it with next separator
                    if segment_tokens > self.chunk_size:
                        remaining_segments.append(segment_with_sep)
                    else:
                        current_chunk.append(segment_with_sep)
                        current_chunk_tokens += segment_tokens
                else:
                    current_chunk.append(segment_with_sep)
                    current_chunk_tokens += segment_tokens
            
            # Update remaining text for next separator
            remaining_text = "".join(remaining_segments)
            if not remaining_text:
                break
        
        # Add the last chunk if not empty
        if current_chunk:
            chunks.append("".join(current_chunk))
            
        # Handle any remaining text that couldn't be chunked
        if remaining_text:
            chunks.extend(self.chunk_by_tokens(remaining_text))
            
        # Filter out tiny chunks and combine them
        filtered_chunks = []
        current_small_chunk = ""
        current_small_tokens = 0
        
        for chunk in chunks:
            chunk_tokens = self.count_tokens(chunk)
            
            if chunk_tokens < min_chunk_size:
                current_small_chunk += chunk
                current_small_tokens += chunk_tokens
                
                if current_small_tokens >= min_chunk_size:
                    filtered_chunks.append(current_small_chunk)
                    current_small_chunk = ""
                    current_small_tokens = 0
            else:
                if current_small_chunk:
                    # Add any accumulated small chunks first
                    filtered_chunks.append(current_small_chunk)
                    current_small_chunk = ""
                    current_small_tokens = 0
                    
                filtered_chunks.append(chunk)
        
        # Add any remaining small chunks
        if current_small_chunk:
            filtered_chunks.append(current_small_chunk)
            
        return filtered_chunks
    
    def smart_chunking(self, content: str) -> List[str]:
        """Perform intelligent chunking by trying different strategies.
        
        Args:
            content: Document content
            
        Returns:
            List of text chunks
        """
        # First try to chunk by sections
        section_chunks = self.chunk_by_sections(content)
        
        # If we have multiple sections, process each section to ensure
        # it fits within our chunk size constraints
        if len(section_chunks) > 1:
            result_chunks = []
            for section in section_chunks:
                section_tokens = self.count_tokens(section)
                if section_tokens > self.chunk_size:
                    # This section is too large, chunk it further
                    result_chunks.extend(self.chunk_by_separator(section))
                else:
                    result_chunks.append(section)
            return result_chunks
            
        # If no sections or just one, use the separator approach
        return self.chunk_by_separator(content)
    
    def chunk_document(self, content: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Chunk a document and prepare it for ingestion.
        
        Args:
            content: Document content
            metadata: Document metadata
            
        Returns:
            List of chunks with metadata
        """
        if not content.strip():
            return []
            
        if metadata is None:
            metadata = {}
            
        # Extract document metadata if not already present
        doc_metadata = self.extract_document_metadata(content)
        
        # Only add metadata we don't already have
        for key, value in doc_metadata.items():
            if key not in metadata:
                metadata[key] = value
        
        # Use the smart chunking strategy
        chunks = self.smart_chunking(content)
        
        # Prepare chunks with metadata
        result = []
        for i, chunk in enumerate(chunks):
            # Create a copy of metadata for each chunk
            chunk_metadata = metadata.copy()
            
            # Add chunk-specific metadata
            chunk_metadata.update({
                "chunk_index": i,
                "total_chunks": len(chunks),
                "token_count": self.count_tokens(chunk),
                "chunk_hash": hashlib.md5(chunk.encode()).hexdigest()
            })
            
            # Extract any section headers in this chunk
            section_match = SECTION_HEADER_REGEX.search(chunk)
            if section_match:
                chunk_metadata["section"] = section_match.group(0).strip()
            
            result.append({
                "content": chunk,
                "metadata": chunk_metadata
            })
        
        return result 