#!/usr/bin/env python
"""
Test script to verify Neo4j connectivity from the Graphiti service.
"""

import asyncio
import sys

from app.services.graph import GraphitiService


async def test_graphiti_connection():
    """Test connectivity to Neo4j through the Graphiti service."""
    print("Testing Graphiti connection...")
    
    try:
        graphiti_service = GraphitiService()
        # Add a test episode
        result = await graphiti_service.add_episode(
            content="This is a test episode",
            user_id="test-user",
            metadata={"test": True}
        )
        print("Successfully connected to Neo4j via Graphiti!")
        print(f"Created episode with ID: {result['episode_id']}")
        return True
    except Exception as e:
        print(f"Error connecting to Neo4j via Graphiti: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_graphiti_connection())
    sys.exit(0 if success else 1) 