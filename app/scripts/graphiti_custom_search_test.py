"""
This scripts tests our custom entity, relationship, and trait extraction with Graphiti.
Given a few docs and chat logs, belonging to different users, we want to extract entities, relationships, and traits and store them in Graphiti with our custom pipeline (extraction_pipeline.py), which uses Gemini's EntityExtractor for entities and relations and our TraitExtractionService for traits. This is essentially `process_document` for document sources and `process_chat_message` for chat sources.

Then we want to test searching via our GraphitiService, using its search (general graph search) and node_search (entity search).

Crucially we are interested in extracting and processing into Graphiti entities and relationships from different users and scopes like:
- (user scope, user_1, conversation_1): "I've lived in both SF and NYC, but I really like SF more than NYC" 
- (user scope, user_1, document_1): "I moved to SF two years ago and I love it here"
- (user scope, user_1, document_2): "Just walking down Hayes and seeing my friends is the best" (same user, unrelated))
- (user scope, user_2, conversation_1): "I've lived in NYC my whole life and I love it here" (different user, same convo)
- (user scope, user_2, conversation_2): "The best pizza is in Brooklyn" (different user, unrelated convo)
- (user scope, user_2, document_1): "I always go to the gym in Williamsburg" (different user, same-name document but actually belongs to user 2)
- (global scope, no user, document_123): "SF has a really good pizza spot in Mission." (global scope, same-name document but belongs to user 2)

These all have a variety of sources, two different users, and two scopes (user vs global)
When querying, users should search everything that was in their user id, as well everything in global scope.
SO our queries always need to filter by user id, and retrieve from global scope as well:
- If you query "which city should I go to?" for *user 1*, you should get SF back.
- If you query "which city should I go to?" for *user 2*, you should get NYC back.
- If you query "where is the best pizza?" for *user 1*, you should get "downtown SF" back because that was in the global scope.
- If you query "where is the best pizza?" for *user 2*, you should get Brooklyn back (because their own preference overrode the global scope)
"""

import os
import sys
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
import uuid

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.services.extraction_pipeline import ExtractionPipeline, ENABLE_GRAPHITI_INGESTION
from app.services.graph import GraphitiService, ContentScope
from app.services.ingestion.entity_extraction_factory import get_entity_extractor
from app.services.traits.service import TraitExtractionService

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.getLogger("neo4j.notifications").setLevel(logging.WARNING)  # Reduce Neo4j noise
logger = logging.getLogger(__name__)

# Define test users
USER_1_ID = "test_user_1"
USER_2_ID = "test_user_2"

# Define content scopes
USER_SCOPE: ContentScope = "user"
GLOBAL_SCOPE: ContentScope = "global"

async def clean_test_data():
    """Clean up previous test data for our test users"""
    logger.info("Cleaning up previous test data...")
    graph_service = GraphitiService()
    
    try:
        # Clear data for test users
        await graph_service.clear_for_user(USER_1_ID)
        await graph_service.clear_for_user(USER_2_ID)
        
        # Clear global data related to our test
        # This requires a custom query as clear_for_user doesn't handle global scope
        global_query = """
        MATCH (n)
        WHERE n.scope = 'global'
        DETACH DELETE n
        """
        await graph_service.execute_cypher(global_query)
        
        # Verify cleanup was successful
        verify_query = """
        MATCH (n) 
        WHERE (n.owner_id = $user1_id OR n.owner_id = $user2_id OR n.scope = 'global')
        RETURN count(n) as remaining_count
        """
        
        result = await graph_service.execute_cypher(verify_query, {
            "user1_id": USER_1_ID,
            "user2_id": USER_2_ID
        })
        
        remaining_count = result[0]["remaining_count"] if result else -1
        if remaining_count > 0:
            logger.warning(f"Cleanup may not be complete - {remaining_count} nodes still remain. Waiting...")
            # Give the database a moment to complete deletions
            await asyncio.sleep(1)
        
        logger.info("Test data cleanup complete")
    finally:
        await graph_service.close()

async def process_test_data():
    """Create and process test data using the extraction pipeline"""
    logger.info(f"Starting test data processing (ENABLE_GRAPHITI_INGESTION={ENABLE_GRAPHITI_INGESTION})")
    
    # Create extraction pipeline
    extractor = get_entity_extractor()
    pipeline = ExtractionPipeline(
        entity_extractor=extractor, 
        trait_service=TraitExtractionService()
    )
    
    # Test data definitions
    test_data = [
        # User 1 conversation
        {
            "content": "I've lived in both SF and NYC, but I really like SF more than NYC",
            "user_id": USER_1_ID,
            "source_id": "conv_1_msg_1",
            "metadata": {"conversation_title": "City Preferences Conversation"},
            "source_type": "chat",
            "scope": USER_SCOPE,
            "owner_id": USER_1_ID
        },
        # User 1 document 1
        {
            "content": "I moved to SF two years ago and I love it here",
            "user_id": USER_1_ID,
            "source_id": "doc_1.md",
            "metadata": {"title": "My Move to SF"},
            "source_type": "document",
            "scope": USER_SCOPE,
            "owner_id": USER_1_ID
        },
        # User 1 document 2
        {
            "content": "Just walking down Hayes and seeing my friends is the best",
            "user_id": USER_1_ID,
            "source_id": "doc_2.md",
            "metadata": {"title": "Hayes Valley Notes"},
            "source_type": "document",
            "scope": USER_SCOPE,
            "owner_id": USER_1_ID
        },
        # User 2 conversation 1
        {
            "content": "I've lived in NYC my whole life and I love it here",
            "user_id": USER_2_ID,
            "source_id": "conv_1_msg_2",
            "metadata": {"conversation_title": "City Preferences Conversation"},
            "source_type": "chat",
            "scope": USER_SCOPE,
            "owner_id": USER_2_ID
        },
        # User 2 conversation 2
        {
            "content": "The best pizza is in Brooklyn",
            "user_id": USER_2_ID,
            "source_id": "conv_2_msg_1",
            "metadata": {"conversation_title": "Food Discussion"},
            "source_type": "chat",
            "scope": USER_SCOPE,
            "owner_id": USER_2_ID
        },
        # User 2 document 1
        {
            "content": "I always go to the gym in Williamsburg",
            "user_id": USER_2_ID,
            "source_id": "doc_1.md",
            "metadata": {"title": "NYC Fitness Routine"},
            "source_type": "document",
            "scope": USER_SCOPE,
            "owner_id": USER_2_ID
        },
        # Global document
        {
            "content": "SF has a really good pizza spot in Mission.",
            "user_id": "system",
            "source_id": "global_doc_123.md",
            "metadata": {"title": "Global City Guide", "source": "test_script"},
            "source_type": "document",
            "scope": GLOBAL_SCOPE,
            "owner_id": None
        },
    ]
    
    logger.info(f"Processing {len(test_data)} test data items...")
    
    # Process each test data item
    results = []
    for i, item in enumerate(test_data):
        logger.info(f"\n[Item {i+1}] Processing {item['source_type']} for {item['user_id']} with scope {item['scope']}: {item['content'][:50]}...")
        
        if item["source_type"] == "chat":
            result = await pipeline.process_chat_message(
                message_content=item["content"],
                user_id=item["user_id"],
                message_id=item["source_id"],
                metadata=item["metadata"],
                scope=item["scope"],
                owner_id=item["owner_id"]
            )
        else:  # document
            result = await pipeline.process_document(
                content=item["content"],
                user_id=item["user_id"],
                file_path=item["source_id"],
                metadata=item["metadata"],
                scope=item["scope"],
                owner_id=item["owner_id"]
            )
        
        # Log extracted relationships and facts for debugging
        if "processing" in result and "relationships" in result["processing"]:
            rel_count = len(result["processing"]["relationships"])
            logger.info(f"Created {rel_count} relationships for item {i+1}:")
            for j, rel in enumerate(result["processing"]["relationships"]):
                logger.info(f"  {j+1}. {rel.get('source')} -> {rel.get('type')} -> {rel.get('target')}")
        elif "extraction" in result and "relationships" in result["extraction"]:
            rel_count = len(result["extraction"]["relationships"])
            logger.info(f"Extracted {rel_count} relationships for item {i+1}, but they may not have been stored in Graphiti")
        else:
            logger.warning(f"No relationships found for item {i+1}")
        
        results.append({
            "item": item,
            "result": result
        })
    
    logger.info("Test data processing complete")
    return results

async def run_search_tests():
    """Run search tests against the processed data"""
    logger.info("Running search tests...")
    graph_service = GraphitiService()
    
    try:
        # Define our test queries
        test_queries = [
            # {
            #     "query": "which city should I go to?",
            #     "user_id": USER_1_ID,
            #     "expected": "SF"
            # },
            {
                "query": "which city do I like?",
                "user_id": USER_2_ID,
                "expected": "NYC"
            },
            # Additional queries for user_2 that might match NYC better
            {
                "query": "where have I lived?",
                "user_id": USER_2_ID,
                "expected": "NYC"
            },
            {
                "query": "what city do I love?",
                "user_id": USER_2_ID,
                "expected": "NYC"
            },
            {
                "query": "NYC", 
                "user_id": USER_2_ID,
                "expected": "NYC"
            },
            {
                "query": "where is the best pizza?",
                "user_id": USER_1_ID,
                "expected": "downtown SF" # From global scope
            },
            {
                "query": "where is the best pizza?",
                "user_id": USER_2_ID,
                "expected": "Brooklyn" # User preference overrides global
            }
        ]
        
        # Run each test query with both search methods
        for test in test_queries:
            logger.info(f"\n===== Testing query: '{test['query']}' for user {test['user_id']} =====")
            logger.info(f"Expected to find: {test['expected']}")
            
            # Test general relationship search - should get user and global content
            search_results = await graph_service.search(
                query=test["query"],
                user_id=test["user_id"],
                owner_id=test["user_id"],
                limit=5,
                # explicitly not passing scope=ContentScope.GLOBAL so we get global too
            )
            
            logger.info(f"Regular graph search results for user + global content: ({len(search_results)} items):")
            for i, result in enumerate(search_results):
                # log everything except fact_embedding
                log_result = result.copy()
                log_result.pop("fact_embedding", None)
                logger.info(f"  {i+1}. {log_result}")
                
                # logger.info(f"  {i+1}. {result.get('fact', 'No fact')} (scope: {result.get('scope')}, owner: {result.get('owner_id')})")
            
            # Test node search for user scope
            node_results = await graph_service.node_search(
                query=test["query"],
                limit=5,
                owner_id=test["user_id"]  # This will only search user's own content
                # explicitly not passing scope=ContentScope.GLOBAL so we get global too
            )
            
            logger.info(f"Node search results for user + global content: ({len(node_results)} items):")
            for i, result in enumerate(node_results):
                logger.info(f"  {i+1}. {result.get('name', 'No name')} (scope: {result.get('scope')}, owner: {result.get('owner_id')})")
            
            # Also search explicitly for just global content to check
            global_search_results = await graph_service.search(
                query=test["query"],
                limit=5,
                scope=GLOBAL_SCOPE  # Search global content
            )
            logger.info(f"Global only graph search results: ({len(global_search_results)} items):")
            for i, result in enumerate(global_search_results):
                logger.info(f"  {i+1}. {result.get('fact', 'No fact')} (scope: {result.get('scope')}, owner: {result.get('owner_id')})")
                
            global_node_results = await graph_service.node_search(
                query=test["query"],
                limit=5,
                scope=GLOBAL_SCOPE  # Search global content
            )
            
            logger.info(f"Node search results for global-only content ({len(global_node_results)} items):")
            for i, result in enumerate(global_node_results):
                logger.info(f"  {i+1}. {result.get('name', 'No name')} (scope: {result.get('scope')}, owner: {result.get('owner_id')})")
            
            # Combined results that would be accessible to this user (user's content + global)
            combined_results = node_results + global_node_results
            logger.info(f"Combined node results accessible to user ({len(combined_results)} items)")
            
    finally:
        await graph_service.close()

async def initialize_graph():
    """Initialize the graph database with indices and constraints."""
    graph_service = GraphitiService()
    
    try:
        await graph_service.initialize_graph()
        
        logger.info("Graph initialization complete")
    finally:
        await graph_service.close()

async def list_user_facts(user_id):
    """List all facts/relationships associated with a user."""
    logger.info(f"\n===== Facts known about user {user_id} =====")
    graph_service = GraphitiService()
    
    try:
        # Query all relationships where this user is the owner_id
        query = """
        MATCH ()-[r]->()
        WHERE r.owner_id = $owner_id
        RETURN r.uuid as uuid, type(r) as type, r.fact as fact, r.scope as scope, r.owner_id as owner_id
        """
        
        results = await graph_service.execute_cypher(query, {"owner_id": user_id})
        
        logger.info(f"Found {len(results)} facts/relationships owned by {user_id}:")
        for i, result in enumerate(results):
            fact = result.get("fact", "No fact")
            rel_type = result.get("type", "Unknown type")
            scope = result.get("scope", "Unknown scope")
            logger.info(f"  {i+1}. [{rel_type}] {fact} (scope: {scope})")
        
        # Also query global facts
        global_query = """
        MATCH ()-[r]->()
        WHERE r.scope = 'global'
        RETURN r.uuid as uuid, type(r) as type, r.fact as fact, r.scope as scope, r.owner_id as owner_id
        """
        
        global_results = await graph_service.execute_cypher(global_query, {})
        
        logger.info(f"Found {len(global_results)} global facts:")
        for i, result in enumerate(global_results):
            fact = result.get("fact", "No fact")
            rel_type = result.get("type", "Unknown type")
            logger.info(f"  {i+1}. [{rel_type}] {fact}")
        
        # Query node entities
        entity_query = """
        MATCH (n)
        WHERE n.owner_id = $owner_id
        RETURN n.uuid as uuid, n.name as name, labels(n) as labels, n.scope as scope
        """
        
        entity_results = await graph_service.execute_cypher(entity_query, {"owner_id": user_id})
        
        logger.info(f"Found {len(entity_results)} entities owned by {user_id}:")
        for i, result in enumerate(entity_results):
            name = result.get("name", "No name")
            labels = result.get("labels", [])
            scope = result.get("scope", "Unknown scope")
            logger.info(f"  {i+1}. [{', '.join(labels)}] {name} (scope: {scope})")
        
    finally:
        await graph_service.close()

async def check_fulltext_indices():
    """Check if full-text indices are properly set up and working."""
    logger.info("\n===== Checking full-text indices =====")
    graph_service = GraphitiService()
    
    try:
        # Check if indices exist
        index_query = """
        CALL db.indexes() 
        YIELD name, type, labelsOrTypes, properties, state
        WHERE type = 'FULLTEXT'
        RETURN name, labelsOrTypes, properties, state
        """
        
        indices = await graph_service.execute_cypher(index_query)
        
        if not indices:
            logger.error("No full-text indices found in the database!")
            return
        
        logger.info(f"Found {len(indices)} full-text indices:")
        for i, index in enumerate(indices):
            name = index.get("name", "Unknown")
            state = index.get("state", "Unknown")
            labels = ", ".join(index.get("labelsOrTypes", []))
            properties = ", ".join(index.get("properties", []))
            logger.info(f"  {i+1}. {name} - {state} - Labels/Types: {labels} - Properties: {properties}")
        
        # Try a direct query using the relationship index
        direct_query = """
        CALL db.index.fulltext.queryRelationships('relationship_text_index', 'NYC') 
        YIELD relationship, score
        RETURN relationship.fact as fact, relationship.scope as scope, relationship.owner_id as owner_id, 
               score as search_score
        LIMIT 5
        """
        
        direct_results = await graph_service.execute_cypher(direct_query)
        
        logger.info(f"Direct full-text search for 'NYC' returned {len(direct_results)} results:")
        for i, result in enumerate(direct_results):
            fact = result.get("fact", "No fact")
            scope = result.get("scope", "Unknown")
            owner = result.get("owner_id", "Unknown")
            score = result.get("search_score", 0)
            logger.info(f"  {i+1}. {fact} (scope: {scope}, owner: {owner}, score: {score:.2f})")
        
    finally:
        await graph_service.close()

async def main():
    """Main test execution function"""
    logger.info("Starting Graphiti custom search test")
    
    # Initialize graph and necessary indices
    await initialize_graph()
    
    # Optionally clean previous test data (uncomment to enable)
    await clean_test_data()
    
    # Process test data
    processing_results = await process_test_data()
    
    # Wait a moment for all data to be properly indexed
    logger.info("Waiting for indexing to complete...")
    await asyncio.sleep(2)
    
    # Check that full-text indices are working
    # await check_fulltext_indices()
    
    # Dump all facts for user_1 and user_2 to see what's in the database
    await list_user_facts(USER_1_ID)
    await list_user_facts(USER_2_ID)
    
    # Run search tests
    await run_search_tests()
    
    logger.info("Test complete")

if __name__ == "__main__":
    # Check if ENABLE_GRAPHITI_INGESTION is enabled
    if not ENABLE_GRAPHITI_INGESTION:
        logger.warning("WARNING: ENABLE_GRAPHITI_INGESTION is set to False in extraction_pipeline.py. Test will run but no data will be stored in Graphiti.")
    
    # Run the test
    asyncio.run(main())