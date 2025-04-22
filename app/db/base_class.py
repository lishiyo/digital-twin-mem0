"""
Base class for SQLAlchemy models.
"""
from typing import Any

from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    
    @declared_attr.directive
    def __tablename__(cls) -> str:
        """Generate table name from class name in snake_case."""
        # Convert CamelCase to snake_case
        name = cls.__name__
        # Remove "Model" suffix if present
        if name.endswith("Model"):
            name = name[:-5]
        # Convert to snake_case
        # (This is a simplified implementation, a proper one would handle
        # consecutive uppercase letters, etc.)
        result = "".join(
            "_" + c.lower() if c.isupper() else c
            for c in name
        ).lstrip("_")
        return result
        
    # Add metadata options as needed
    __table_args__ = {"extend_existing": True} 