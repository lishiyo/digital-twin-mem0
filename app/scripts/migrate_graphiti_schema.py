#!/usr/bin/env python
"""Script to migrate Graphiti schema for v1.

This script performs the necessary schema changes in Graphiti for the v1 migration:
1. Removes DAO-related node types (Proposal, Vote, PolicyTopic) if they exist
2. Creates new node types (Skill, Interest, Preference, Dislike, Person, TimeSlot)
3. Defines new relationship types (HAS_SKILL, INTERESTED_IN, etc.)
"""

import asyncio
import logging
import sys
import os
from pathlib import Path
from datetime import datetime
import argparse
import json

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

# Define migration queries
DAO_REMOVAL_QUERIES = [
    # Check and remove Proposal nodes
    """
    MATCH (p:Proposal)
    RETURN count(p) as proposal_count
    """,
    """
    MATCH (p:Proposal)
    DETACH DELETE p
    RETURN count(p) as deleted_proposals
    """,
    
    # Check and remove Vote nodes
    """
    MATCH (v:Vote)
    RETURN count(v) as vote_count
    """,
    """
    MATCH (v:Vote)
    DETACH DELETE v
    RETURN count(v) as deleted_votes
    """,
    
    # Check and remove PolicyTopic nodes
    """
    MATCH (p:PolicyTopic)
    RETURN count(p) as policy_topic_count
    """,
    """
    MATCH (p:PolicyTopic)
    DETACH DELETE p
    RETURN count(p) as deleted_policy_topics
    """
]

# Define queries for creating test data
CREATE_TEST_DATA_QUERIES = [
    # Test user
    """
    MERGE (u:User {name: "Test User", user_id: "test-user-id", scope: "user", owner_id: "test-user-id"})
    RETURN u
    """,
    
    # Create test skill
    """
    MATCH (u:User {user_id: "test-user-id"})
    MERGE (s:Skill {name: "Python", description: "Programming language", proficiency: "Expert", 
                  experience_years: 5, confidence: 0.9, source: "user_input", 
                  user_id: "test-user-id", scope: "user", owner_id: "test-user-id"})
    MERGE (u)-[r:HAS_SKILL {strength: 0.9, context: "Professional work", 
                          user_id: "test-user-id", scope: "user", owner_id: "test-user-id"}]->(s)
    RETURN s, r
    """,
    
    # Create test interest
    """
    MATCH (u:User {user_id: "test-user-id"})
    MERGE (i:Interest {name: "Machine Learning", description: "AI technology", strength: 0.8, 
                     category: "Technology", confidence: 0.85, source: "chat", 
                     user_id: "test-user-id", scope: "user", owner_id: "test-user-id"})
    MERGE (u)-[r:INTERESTED_IN {strength: 0.8, since: "2020", 
                              user_id: "test-user-id", scope: "user", owner_id: "test-user-id"}]->(i)
    RETURN i, r
    """,
    
    # Create test preference
    """
    MATCH (u:User {user_id: "test-user-id"})
    MERGE (p:Preference {name: "Dark mode", description: "Prefers dark UI", strength: 0.9, 
                       category: "UI", confidence: 0.95, source: "settings", 
                       user_id: "test-user-id", scope: "user", owner_id: "test-user-id"})
    MERGE (u)-[r:PREFERS {strength: 0.9, context: "All applications", 
                        user_id: "test-user-id", scope: "user", owner_id: "test-user-id"}]->(p)
    RETURN p, r
    """,
    
    # Create test dislike
    """
    MATCH (u:User {user_id: "test-user-id"})
    MERGE (d:Dislike {name: "Spicy food", description: "Dislikes spicy food", strength: 0.7, 
                    category: "Food", confidence: 0.8, source: "chat", 
                    user_id: "test-user-id", scope: "user", owner_id: "test-user-id"})
    MERGE (u)-[r:DISLIKES {strength: 0.7, reason: "Causes discomfort", 
                         user_id: "test-user-id", scope: "user", owner_id: "test-user-id"}]->(d)
    RETURN d, r
    """,
    
    # Create test person connection
    """
    MATCH (u:User {user_id: "test-user-id"})
    MERGE (p:Person {name: "Jane Doe", relationship: "Colleague", 
                   user_id: "test-user-id", scope: "user", owner_id: "test-user-id"})
    MERGE (u)-[r:KNOWS {relationship_type: "Professional", strength: 0.6, 
                      user_id: "test-user-id", scope: "user", owner_id: "test-user-id"}]->(p)
    RETURN p, r
    """,
    
    # Create test timeslot
    """
    MATCH (u:User {user_id: "test-user-id"})
    MERGE (t:TimeSlot {name: "Morning Meeting", start_time: "09:00", end_time: "10:00", 
                     day_of_week: "Monday", recurrence: "Weekly", 
                     user_id: "test-user-id", scope: "user", owner_id: "test-user-id"})
    MERGE (u)-[r:AVAILABILITY {status: "Busy", priority: "High", 
                            user_id: "test-user-id", scope: "user", owner_id: "test-user-id"}]->(t)
    RETURN t, r
    """
]

# Define rollback queries to remove test data
ROLLBACK_QUERIES = [
    # Remove test nodes and relationships
    """
    MATCH (n)
    WHERE n.user_id = "test-user-id"
    DETACH DELETE n
    RETURN count(n) as deleted_nodes
    """
]

async def run_migration(graphiti_service, apply_schema_only=False, test_data=False, rollback=False, backup=True):
    """Run the Graphiti schema migration.
    
    Args:
        graphiti_service: The GraphitiService instance
        apply_schema_only: Whether to only apply schema changes without test data
        test_data: Whether to create test data
        rollback: Whether to roll back changes
        backup: Whether to create a backup before migration
    """
    logger.info("Starting Graphiti schema migration")
    
    # Create a backup if requested
    if backup:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"graphiti_backup_{timestamp}.json"
        logger.info(f"Creating backup to {backup_file}")
        
        try:
            # Get all nodes and relationships
            all_nodes_query = """
            MATCH (n)
            RETURN n, labels(n) as labels
            """
            all_rels_query = """
            MATCH ()-[r]->()
            RETURN r, type(r) as type
            """
            
            nodes = await graphiti_service.execute_cypher(all_nodes_query)
            rels = await graphiti_service.execute_cypher(all_rels_query)
            
            # Prepare backup data
            backup_data = {
                "timestamp": timestamp,
                "nodes": [{"labels": node["labels"], "properties": dict(node["n"])} for node in nodes],
                "relationships": [{"type": rel["type"], "properties": dict(rel["r"])} for rel in rels]
            }
            
            # Save to file
            with open(backup_file, "w") as f:
                json.dump(backup_data, f, default=str, indent=2)
            
            logger.info(f"Backup created with {len(nodes)} nodes and {len(rels)} relationships")
            
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            if input("Backup failed. Continue with migration anyway? (y/n): ").lower() != "y":
                logger.info("Migration aborted")
                return
    
    # If rollback is requested, run rollback queries and return
    if rollback:
        logger.info("Rolling back changes")
        
        for query in ROLLBACK_QUERIES:
            try:
                logger.info(f"Executing rollback query: {query[:50]}...")
                result = await graphiti_service.execute_cypher(query)
                logger.info(f"Rollback result: {result}")
            except Exception as e:
                logger.error(f"Error running rollback query: {e}")
        
        logger.info("Rollback completed")
        return
    
    # Remove DAO-related nodes if they exist
    logger.info("Removing DAO-related nodes")
    
    for query in DAO_REMOVAL_QUERIES:
        try:
            logger.info(f"Executing query: {query[:50]}...")
            result = await graphiti_service.execute_cypher(query)
            logger.info(f"Query result: {result}")
        except Exception as e:
            logger.error(f"Error running DAO removal query: {e}")
    
    # If test data is requested, create it
    if test_data and not apply_schema_only:
        logger.info("Creating test data")
        
        for query in CREATE_TEST_DATA_QUERIES:
            try:
                logger.info(f"Executing test data query: {query[:50]}...")
                result = await graphiti_service.execute_cypher(query)
                logger.info(f"Test data result: {result}")
            except Exception as e:
                logger.error(f"Error creating test data: {e}")
    
    logger.info("Graphiti schema migration completed successfully")

async def main():
    """Main script function."""
    parser = argparse.ArgumentParser(description="Migrate Graphiti schema for v1")
    parser.add_argument("--schema-only", action="store_true", help="Only apply schema changes without test data")
    parser.add_argument("--test-data", action="store_true", help="Create test data")
    parser.add_argument("--rollback", action="store_true", help="Roll back changes")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup creation")
    
    args = parser.parse_args()
    
    # Initialize GraphitiService
    graphiti_service = GraphitiService()
    
    try:
        await run_migration(
            graphiti_service,
            apply_schema_only=args.schema_only,
            test_data=args.test_data,
            rollback=args.rollback,
            backup=not args.no_backup
        )
    finally:
        # Close connections
        await graphiti_service.close()

if __name__ == "__main__":
    asyncio.run(main()) 