"""
Base class for SQLAlchemy models.
"""
from typing import Any

from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    
    # NOTE: We're no longer automatically generating table names.
    # Each model should explicitly set its __tablename__ to match the database.
    
    # Add metadata options as needed
    __table_args__ = {"extend_existing": True} 