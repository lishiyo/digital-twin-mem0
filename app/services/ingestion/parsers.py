"""File parsers for different document types."""

import logging
import os
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

# Dictionary mapping file extensions to parser functions
PARSER_REGISTRY = {}


def register_parser(extensions: List[str]):
    """Decorator to register a parser function for specific file extensions."""
    def decorator(func):
        for ext in extensions:
            PARSER_REGISTRY[ext.lower()] = func
        return func
    return decorator


def parse_file(file_path: str, content: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
    """Parse a file using the appropriate parser.
    
    Args:
        file_path: Path to the file
        content: Optional pre-loaded file content
        
    Returns:
        Tuple of (parsed_content, metadata)
    """
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext not in PARSER_REGISTRY:
        logger.warning(f"No parser found for extension {ext}, using text parser")
        ext = ".txt"  # Fallback to text parser
    
    parser = PARSER_REGISTRY[ext]
    
    # Load content if not provided
    if content is None:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return "", {"error": str(e)}
    
    return parser(content, file_path)


@register_parser([".txt"])
def parse_text(content: str, file_path: str) -> Tuple[str, Dict[str, Any]]:
    """Parse a plain text file.
    
    Args:
        content: The file content
        file_path: Path to the file
        
    Returns:
        Tuple of (parsed_content, metadata)
    """
    # For plain text, we just return the content as is
    # and extract minimal metadata
    metadata = {
        "title": os.path.basename(file_path),
        "format": "text",
        "lines": content.count("\n") + 1
    }
    
    return content, metadata


@register_parser([".md", ".markdown"])
def parse_markdown(content: str, file_path: str) -> Tuple[str, Dict[str, Any]]:
    """Parse a markdown file.
    
    Args:
        content: The file content
        file_path: Path to the file
        
    Returns:
        Tuple of (parsed_content, metadata)
    """
    # Extract title from first heading if available
    title = os.path.basename(file_path)
    lines = content.split("\n")
    
    # Look for a top-level heading
    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
            break
    
    metadata = {
        "title": title,
        "format": "markdown",
        "lines": len(lines)
    }
    
    return content, metadata


@register_parser([".pdf"])
def parse_pdf(content: str, file_path: str) -> Tuple[str, Dict[str, Any]]:
    """Parse a PDF file.
    
    Note: This is a stub implementation. In a real app, we would use PyPDF2, 
    pdf2text, or a similar library to extract text from PDF files.
    
    Args:
        content: The file content (ignored for PDFs, we read directly from file_path)
        file_path: Path to the PDF file
        
    Returns:
        Tuple of (parsed_content, metadata)
    """
    try:
        # Placeholder for PDF parsing
        # In a real implementation, we would use something like:
        # from PyPDF2 import PdfReader
        # reader = PdfReader(file_path)
        # text = ""
        # for page in reader.pages:
        #     text += page.extract_text() + "\n"
        
        # For now, return a stub message
        text = f"[PDF Content from {os.path.basename(file_path)}]"
        
        metadata = {
            "title": os.path.basename(file_path),
            "format": "pdf",
            "pages": 0  # Would be actual page count in real implementation
        }
        
        logger.warning(f"PDF parsing is not fully implemented. File: {file_path}")
        return text, metadata
        
    except Exception as e:
        logger.error(f"Error parsing PDF {file_path}: {e}")
        return "", {"error": str(e)} 