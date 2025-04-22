#!/usr/bin/env python
"""Test script for validating Graphiti schema changes.

This script creates test entities and relationships for all new node types
and verifies that they conform to the expected schema.
"""

import asyncio
import logging
import sys
import os
from pathlib import Path
import json
from datetime import datetime

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.graph import GraphitiService
from app.core.config import settings
from app.core.constants import DEFAULT_USER_ID

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Define test entities and relationships
TEST_ENTITIES = [
    {
        "type": "Skill",
        "name": "JavaScript",
        "properties": {
            "description": "Programming language for web development",
            "proficiency": "Advanced",
            "experience_years": 3,
            "confidence": 0.85,
            "source": "profile_input"
        }
    },
    {
        "type": "Interest",
        "name": "Photography",
        "properties": {
            "description": "Taking and editing photos",
            "strength": 0.7,
            "category": "Hobbies",
            "since": "2018",
            "confidence": 0.9,
            "source": "chat"
        }
    },
    {
        "type": "Preference",
        "name": "Morning meetings",
        "properties": {
            "description": "Prefers meetings in the morning",
            "strength": 0.8,
            "category": "Work",
            "context_applies": "Scheduling",
            "confidence": 0.75,
            "source": "calendar"
        }
    },
    {
        "type": "Dislike",
        "name": "Long meetings",
        "properties": {
            "description": "Dislikes meetings over 1 hour",
            "strength": 0.9,
            "reason": "Reduced productivity",
            "category": "Work",
            "confidence": 0.85,
            "source": "chat"
        }
    },
    {
        "type": "Person",
        "name": "Alex Smith",
        "properties": {
            "relationship": "Friend",
            "profession": "Designer",
            "contact_info": "alex@example.com" 
        }
    },
    {
        "type": "TimeSlot",
        "name": "Weekly Team Sync",
        "properties": {
            "start_time": "14:00",
            "end_time": "15:00",
            "day_of_week": "Tuesday",
            "recurrence": "Weekly",
            "availability": "Busy"
        }
    }
]

TEST_RELATIONSHIPS = [
    {
        "source_type": "User",
        "source_name": "Test User",
        "target_type": "Skill",
        "target_name": "JavaScript",
        "rel_type": "HAS_SKILL",
        "properties": {
            "strength": 0.85,
            "context": "Professional"
        }
    },
    {
        "source_type": "User",
        "source_name": "Test User",
        "target_type": "Interest",
        "target_name": "Photography",
        "rel_type": "INTERESTED_IN",
        "properties": {
            "strength": 0.7,
            "since": "2018"
        }
    },
    {
        "source_type": "User",
        "source_name": "Test User",
        "target_type": "Preference",
        "target_name": "Morning meetings",
        "rel_type": "PREFERS",
        "properties": {
            "strength": 0.8,
            "context": "Work scheduling"
        }
    },
    {
        "source_type": "User",
        "source_name": "Test User",
        "target_type": "Dislike",
        "target_name": "Long meetings",
        "rel_type": "DISLIKES",
        "properties": {
            "strength": 0.9,
            "reason": "Reduced productivity"
        }
    },
    {
        "source_type": "User",
        "source_name": "Test User",
        "target_type": "Person",
        "target_name": "Alex Smith",
        "rel_type": "KNOWS",
        "properties": {
            "relationship_type": "Friend",
            "strength": 0.75
        }
    },
    {
        "source_type": "User",
        "source_name": "Test User",
        "target_type": "TimeSlot",
        "target_name": "Weekly Team Sync",
        "rel_type": "AVAILABILITY",
        "properties": {
            "status": "Busy",
            "priority": "Medium"
        }
    }
]

async def run_test(graphiti_service, cleanup=True):
    """Run tests for Graphiti schema.
    
    Args:
        graphiti_service: The GraphitiService instance
        cleanup: Whether to clean up test data after running tests
    """
    logger.info("Starting Graphiti schema tests")
    
    # Track created entities and relationships for cleanup
    created_entities = []
    created_relationships = []
    user_id = "test-graphiti-schema-" + datetime.now().strftime("%Y%m%d%H%M%S")
    
    try:
        # Create test user
        user_properties = {
            "name": "Test User",
            "user_id": user_id,
            "scope": "user",
            "owner_id": user_id
        }
        
        user_id_in_graph = await graphiti_service.create_entity(
            entity_type="User",
            properties=user_properties,
            scope="user",
            owner_id=user_id
        )
        
        logger.info(f"Created test user with ID: {user_id_in_graph}")
        created_entities.append(user_id_in_graph)
        
        # Create test entities
        for entity in TEST_ENTITIES:
            try:
                # Add common properties
                properties = {
                    "name": entity["name"],
                    "user_id": user_id,
                    "scope": "user",
                    "owner_id": user_id,
                    **entity["properties"]
                }
                
                entity_id = await graphiti_service.create_entity(
                    entity_type=entity["type"],
                    properties=properties,
                    scope="user",
                    owner_id=user_id
                )
                
                logger.info(f"Created {entity['type']} '{entity['name']}' with ID: {entity_id}")
                created_entities.append(entity_id)
                
                # Store entity id for relationships
                entity["id"] = entity_id
                
            except Exception as e:
                logger.error(f"Error creating {entity['type']} '{entity['name']}': {e}")
        
        # Create test relationships
        for rel in TEST_RELATIONSHIPS:
            try:
                # Find source entity
                source_id = user_id_in_graph
                if rel["source_type"] != "User":
                    source_entity = next((e for e in TEST_ENTITIES if e["type"] == rel["source_type"] and e["name"] == rel["source_name"]), None)
                    if source_entity:
                        source_id = source_entity["id"]
                    else:
                        logger.error(f"Source entity not found: {rel['source_type']} '{rel['source_name']}'")
                        continue
                
                # Find target entity
                target_entity = next((e for e in TEST_ENTITIES if e["type"] == rel["target_type"] and e["name"] == rel["target_name"]), None)
                if not target_entity:
                    logger.error(f"Target entity not found: {rel['target_type']} '{rel['target_name']}'")
                    continue
                    
                target_id = target_entity["id"]
                
                # Add common properties
                properties = {
                    "user_id": user_id,
                    "scope": "user",
                    "owner_id": user_id,
                    **rel["properties"]
                }
                
                rel_id = await graphiti_service.create_relationship(
                    source_id=source_id,
                    target_id=target_id,
                    rel_type=rel["rel_type"],
                    properties=properties,
                    scope="user",
                    owner_id=user_id
                )
                
                logger.info(f"Created relationship {rel['rel_type']} between {rel['source_type']} and {rel['target_type']} with ID: {rel_id}")
                created_relationships.append(rel_id)
                
            except Exception as e:
                logger.error(f"Error creating relationship {rel['rel_type']}: {e}")
        
        # Validate retrieval
        logger.info("Testing node retrieval...")
        for entity in TEST_ENTITIES:
            try:
                query = f"""
                MATCH (n:{entity['type']}) 
                WHERE n.name = $name AND n.user_id = $user_id
                RETURN n
                """
                
                result = await graphiti_service.execute_cypher(
                    query, {"name": entity["name"], "user_id": user_id}
                )
                
                if result and len(result) > 0:
                    logger.info(f"Successfully retrieved {entity['type']} '{entity['name']}'")
                else:
                    logger.error(f"Failed to retrieve {entity['type']} '{entity['name']}'")
                    
            except Exception as e:
                logger.error(f"Error retrieving {entity['type']} '{entity['name']}': {e}")
                
        # Test relationship retrieval
        logger.info("Testing relationship retrieval...")
        for rel in TEST_RELATIONSHIPS:
            try:
                query = f"""
                MATCH (s)-[r:{rel['rel_type']}]->(t)
                WHERE s.user_id = $user_id AND t.name = $target_name
                RETURN r, s, t
                """
                
                result = await graphiti_service.execute_cypher(
                    query, {"user_id": user_id, "target_name": rel["target_name"]}
                )
                
                if result and len(result) > 0:
                    logger.info(f"Successfully retrieved relationship {rel['rel_type']} to {rel['target_name']}")
                else:
                    logger.error(f"Failed to retrieve relationship {rel['rel_type']} to {rel['target_name']}")
                    
            except Exception as e:
                logger.error(f"Error retrieving relationship {rel['rel_type']}: {e}")
        
        logger.info("Graphiti schema tests completed successfully")
        
    finally:
        # Clean up test data if requested
        if cleanup:
            logger.info("Cleaning up test data")
            
            cleanup_query = f"""
            MATCH (n)
            WHERE n.user_id = "{user_id}"
            DETACH DELETE n
            RETURN count(n) as deleted_nodes
            """
            
            try:
                result = await graphiti_service.execute_cypher(cleanup_query)
                logger.info(f"Cleanup result: {result}")
            except Exception as e:
                logger.error(f"Error cleaning up test data: {e}")

async def main():
    """Main script function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Graphiti schema changes")
    parser.add_argument("--no-cleanup", action="store_true", help="Skip cleanup of test data")
    
    args = parser.parse_args()
    
    # Initialize GraphitiService
    graphiti_service = GraphitiService()
    
    try:
        await run_test(
            graphiti_service,
            cleanup=not args.no_cleanup
        )
    finally:
        # Close connections
        await graphiti_service.close()

if __name__ == "__main__":
    asyncio.run(main()) 