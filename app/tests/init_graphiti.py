#!/usr/bin/env python
"""
Script to initialize Graphiti's indices and constraints in Neo4j.
"""

import asyncio
import sys

from app.services.graph import GraphitiService


async def initialize_graphiti():
    """Initialize Graphiti's indices and constraints in Neo4j."""
    print("Initializing Graphiti...")
    
    try:
        graphiti_service = GraphitiService()
        # Build indices and constraints
        await graphiti_service.client.build_indices_and_constraints()
        print("Successfully initialized Graphiti indices and constraints!")
        return True
    except Exception as e:
        print(f"Error initializing Graphiti: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(initialize_graphiti())
    sys.exit(0 if success else 1) 