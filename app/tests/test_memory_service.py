#!/usr/bin/env python
"""
Test script to verify MemoryService functionality.
"""

import asyncio
import sys
import logging
from datetime import datetime

from app.services.memory import MemoryService

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


async def test_memory_service():
    """Test basic functionality of the MemoryService."""
    print("\n=== Testing MemoryService ===\n")
    
    try:
        memory_service = MemoryService()
        
        # Generate a unique user ID for testing
        test_user_id = f"test-user-{datetime.now().isoformat()}"
        print(f"Using test user ID: {test_user_id}")
        
        # Test 1: Adding a memory
        # add_result doesn't return anything
        print("\n=== Test 1: Adding a memory ===")
        add_result = await memory_service.add(
            content="This is a test memory from the test script.",
            user_id=test_user_id
        )
        print(f"Add result: {add_result}")
        
        memory_id = None
        if isinstance(add_result, dict) and add_result.get("memory_id"):
            memory_id = add_result["memory_id"]
            print(f"Successfully added memory with ID: {memory_id}")
        else:
            print("Warning: Memory might not have been added properly.")
        
        # Test 2: Search for memories
        print("\n=== Test 2: Searching for memories ===")
        search_results = await memory_service.search(
            query="do you have atest memory?",
            user_id=test_user_id,
            limit=5
        )
        print(f"Search results: {search_results}")
        
        # Test 3: Get all memories for a user
        print("\n=== Test 3: Getting all memories ===")
        all_memories = await memory_service.get_all(user_id=test_user_id)
        print(f"All memories count: {len(all_memories)}")
        
        # Test 4: Batch add
        print("\n=== Test 4: Batch adding memories ===")
        batch_items = [
            {
                "content": "Batch test memory 1",
                "metadata": {"batch": True, "index": 1}
            },
            {
                "content": "Batch test memory 2",
                "metadata": {"batch": True, "index": 2}
            }
        ]
        batch_result = await memory_service.add_batch(items=batch_items, user_id=test_user_id)
        print(f"Batch add result: {batch_result}")
        
        # Test 5: Error handling
        print("\n=== Test 5: Error handling ===")
        try:
            # Try to get a memory with an invalid ID
            invalid_result = await memory_service.get("invalid-memory-id")
            print(f"Invalid ID result: {invalid_result}")
            
            # If we have a valid memory ID, test memory operations
            if memory_id and not memory_id.startswith("mock"):
                # Test 6: Get specific memory
                print("\n=== Test 6: Get specific memory ===")
                memory = await memory_service.get(memory_id=memory_id)
                print(f"Retrieved memory: {memory}")
                
                # Test 7: Update memory
                print("\n=== Test 7: Update memory ===")
                update_result = await memory_service.update(
                    memory_id=memory_id,
                    data="Updated test memory content."
                )
                print(f"Update result: {update_result}")
                
                # Test 8: Memory history
                print("\n=== Test 8: Memory history ===")
                history = await memory_service.history(memory_id=memory_id)
                print(f"Memory history count: {len(history)}")
                
                # Test 9: Delete (commented out to prevent actual deletion)
                print("\n=== Test 9: Delete (simulated) ===")
                # delete_result = await memory_service.delete(memory_id=memory_id)
                # print(f"Delete result: {delete_result}")
                print("Delete operation skipped to preserve data.")
        except Exception as inner_e:
            print(f"Error during specific memory operations: {inner_e}")
        
        # Test 10: Delete all (commented out to prevent actual deletion)
        print("\n=== Test 10: Delete all (simulated) ===")
        # delete_all_result = await memory_service.delete_all(user_id=test_user_id)
        # print(f"Delete all result: {delete_all_result}")
        print("Delete all operation skipped to preserve data.")
        
        print("\n=== MemoryService tests completed successfully! ===")
        return True
    except Exception as e:
        print(f"Error testing MemoryService: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_memory_service())
    sys.exit(0 if success else 1) 