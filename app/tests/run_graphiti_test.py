#!/usr/bin/env python
"""
Script to run the Graphiti pipeline test directly.
This is useful for manual verification during development.
"""

import asyncio
import time
from app.tests.integration.test_graphiti_pipeline import test_graphiti_and_mem0_pipeline


async def main():
    """Run the Graphiti pipeline test."""
    print("Starting Graphiti and Mem0 pipeline test...")
    
    start_time = time.time()
    
    try:
        result = await test_graphiti_and_mem0_pipeline()
        print(f"\nTest completed successfully in {time.time() - start_time:.2f} seconds")
        print("\nTest result summary:")
        print(f"  Test ID: {result['test_id']}")
        print(f"  User ID: {result['user_id']}")
        print(f"  Mem0 Memory ID: {result['mem0_memory_id']}")
        print(f"  Graphiti Episode ID: {result['graphiti_episode_id']}")
        print(f"  Number of entities created: {len(result['entities'])}")
        print(f"  Number of relationships created: {len(result['relationships'])}")
    except Exception as e:
        print(f"\n❌ Test failed after {time.time() - start_time:.2f} seconds")
        print(f"Error: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main()) 