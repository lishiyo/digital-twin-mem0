#!/usr/bin/env python
"""Fix missing scope and owner_id properties in Graphiti nodes.

This script finds all nodes without scope and owner_id properties
and sets them to the provided default values.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.graph import GraphitiService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def fix_missing_properties(default_scope: str = "user", default_owner_id: str = None):
    """Fix missing scope and owner_id properties on Graphiti nodes.
    
    Args:
        default_scope: Default scope to set if missing
        default_owner_id: Default owner_id to set if missing
    """
    logger.info("Initializing GraphitiService")
    graphiti_service = GraphitiService()
    
    try:
        logger.info("Finding nodes without scope or owner_id")
        
        # Find nodes without scope
        query = """
        MATCH (n)
        WHERE n.scope IS NULL
        RETURN n.uuid as uuid, labels(n) as labels
        """
        
        nodes_without_scope = await graphiti_service.execute_cypher(query)
        logger.info(f"Found {len(nodes_without_scope)} nodes without scope")
        
        # Find nodes without owner_id
        query = """
        MATCH (n)
        WHERE n.owner_id IS NULL
        RETURN n.uuid as uuid, labels(n) as labels
        """
        
        nodes_without_owner = await graphiti_service.execute_cypher(query)
        logger.info(f"Found {len(nodes_without_owner)} nodes without owner_id")
        
        # Process nodes without scope
        for node in nodes_without_scope:
            uuid = node.get("uuid")
            if uuid:
                logger.info(f"Updating node {uuid} with scope {default_scope}")
                
                await graphiti_service.update_node_properties(
                    uuid=uuid,
                    properties={"scope": default_scope}
                )
        
        # Process nodes without owner_id
        for node in nodes_without_owner:
            uuid = node.get("uuid")
            if uuid:
                # If the node has a user_id property, use that as the owner_id
                query = """
                MATCH (n)
                WHERE n.uuid = $uuid
                RETURN n.user_id as user_id
                """
                
                result = await graphiti_service.execute_cypher(query, {"uuid": uuid})
                
                owner_id = None
                if result and len(result) > 0 and result[0].get("user_id"):
                    owner_id = result[0]["user_id"]
                else:
                    owner_id = default_owner_id
                
                logger.info(f"Updating node {uuid} with owner_id {owner_id}")
                
                await graphiti_service.update_node_properties(
                    uuid=uuid,
                    properties={"owner_id": owner_id}
                )
        
        # Now fix relationships (facts) that are missing scope and owner_id
        logger.info("Fixing relationships (facts) missing scope and owner_id")
        
        # Find relationships without scope
        query = """
        MATCH ()-[r]->()
        WHERE r.scope IS NULL
        RETURN elementId(r) as rel_id, type(r) as rel_type, r.uuid as uuid
        """
        
        rels_without_scope = await graphiti_service.execute_cypher(query)
        logger.info(f"Found {len(rels_without_scope)} relationships without scope")
        
        # Find relationships without owner_id
        query = """
        MATCH ()-[r]->()
        WHERE r.owner_id IS NULL
        RETURN elementId(r) as rel_id, type(r) as rel_type, r.uuid as uuid
        """
        
        rels_without_owner = await graphiti_service.execute_cypher(query)
        logger.info(f"Found {len(rels_without_owner)} relationships without owner_id")
        
        # Process relationships without scope
        for rel in rels_without_scope:
            rel_id = rel.get("rel_id")
            uuid = rel.get("uuid")
            if rel_id:
                logger.info(f"Updating relationship {rel_id} (uuid: {uuid}) with scope {default_scope}")
                
                # Update using elementId for relationships
                query = """
                MATCH ()-[r]->()
                WHERE elementId(r) = $rel_id
                SET r.scope = $scope
                """
                
                await graphiti_service.execute_cypher(query, {
                    "rel_id": rel_id,
                    "scope": default_scope
                })
        
        # Process relationships without owner_id
        for rel in rels_without_owner:
            rel_id = rel.get("rel_id")
            uuid = rel.get("uuid")
            if rel_id:
                # If the relationship has a user_id property, use that as the owner_id
                query = """
                MATCH ()-[r]->()
                WHERE elementId(r) = $rel_id
                RETURN r.user_id as user_id
                """
                
                result = await graphiti_service.execute_cypher(query, {"rel_id": rel_id})
                
                owner_id = None
                if result and len(result) > 0 and result[0].get("user_id"):
                    owner_id = result[0]["user_id"]
                else:
                    owner_id = default_owner_id
                
                logger.info(f"Updating relationship {rel_id} (uuid: {uuid}) with owner_id {owner_id}")
                
                # Update using elementId for relationships
                query = """
                MATCH ()-[r]->()
                WHERE elementId(r) = $rel_id
                SET r.owner_id = $owner_id
                """
                
                await graphiti_service.execute_cypher(query, {
                    "rel_id": rel_id,
                    "owner_id": owner_id
                })
        
        logger.info("Completed fixing missing properties")
        
    except Exception as e:
        logger.error(f"Error fixing missing properties: {e}")
    finally:
        await graphiti_service.close()


async def check_node_properties():
    """Check all nodes for scope and owner_id properties."""
    logger.info("Initializing GraphitiService")
    graphiti_service = GraphitiService()
    
    try:
        # Count total nodes
        query = """
        MATCH (n)
        RETURN count(n) as node_count
        """
        
        result = await graphiti_service.execute_cypher(query)
        total_nodes = result[0]["node_count"] if result else 0
        
        logger.info(f"Total nodes in database: {total_nodes}")
        
        # Count nodes with scope
        query = """
        MATCH (n)
        WHERE n.scope IS NOT NULL
        RETURN count(n) as node_count
        """
        
        result = await graphiti_service.execute_cypher(query)
        nodes_with_scope = result[0]["node_count"] if result else 0
        
        logger.info(f"Nodes with scope property: {nodes_with_scope} ({nodes_with_scope/total_nodes*100:.2f}%)")
        
        # Count nodes with owner_id
        query = """
        MATCH (n)
        WHERE n.owner_id IS NOT NULL
        RETURN count(n) as node_count
        """
        
        result = await graphiti_service.execute_cypher(query)
        nodes_with_owner = result[0]["node_count"] if result else 0
        
        logger.info(f"Nodes with owner_id property: {nodes_with_owner} ({nodes_with_owner/total_nodes*100:.2f}%)")
        
        # Count total relationships
        query = """
        MATCH ()-[r]->()
        RETURN count(r) as rel_count
        """
        
        result = await graphiti_service.execute_cypher(query)
        total_rels = result[0]["rel_count"] if result else 0
        
        logger.info(f"Total relationships in database: {total_rels}")
        
        if total_rels > 0:
            # Count relationships with scope
            query = """
            MATCH ()-[r]->()
            WHERE r.scope IS NOT NULL
            RETURN count(r) as rel_count
            """
            
            result = await graphiti_service.execute_cypher(query)
            rels_with_scope = result[0]["rel_count"] if result else 0
            
            logger.info(f"Relationships with scope property: {rels_with_scope} ({rels_with_scope/total_rels*100:.2f}%)")
            
            # Count relationships with owner_id
            query = """
            MATCH ()-[r]->()
            WHERE r.owner_id IS NOT NULL
            RETURN count(r) as rel_count
            """
            
            result = await graphiti_service.execute_cypher(query)
            rels_with_owner = result[0]["rel_count"] if result else 0
            
            logger.info(f"Relationships with owner_id property: {rels_with_owner} ({rels_with_owner/total_rels*100:.2f}%)")
        
        # List the first 5 nodes and their properties for verification
        query = """
        MATCH (n)
        RETURN n.uuid as uuid, labels(n) as labels, n.scope as scope, n.owner_id as owner_id
        LIMIT 5
        """
        
        result = await graphiti_service.execute_cypher(query)
        
        logger.info("Sample nodes for verification:")
        for i, node in enumerate(result):
            logger.info(f"Node {i+1}: {node}")
            
        # List the first 5 relationships and their properties for verification
        if total_rels > 0:
            query = """
            MATCH ()-[r]->()
            RETURN type(r) as type, r.uuid as uuid, r.scope as scope, r.owner_id as owner_id
            LIMIT 5
            """
            
            result = await graphiti_service.execute_cypher(query)
            
            logger.info("Sample relationships for verification:")
            for i, rel in enumerate(result):
                logger.info(f"Relationship {i+1}: {rel}")
        
    except Exception as e:
        logger.error(f"Error checking node properties: {e}")
    finally:
        await graphiti_service.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Fix missing scope and owner_id properties in Graphiti nodes")
    parser.add_argument("--check", action="store_true", help="Only check for missing properties without fixing")
    parser.add_argument("--scope", default="user", help="Default scope to set (default: user)")
    parser.add_argument("--owner", default=None, help="Default owner_id to set")
    
    args = parser.parse_args()
    
    if args.check:
        asyncio.run(check_node_properties())
    else:
        asyncio.run(fix_missing_properties(args.scope, args.owner))
        
        # After fixing, check the results
        print("\nAfter fixing, checking the results:")
        asyncio.run(check_node_properties()) 