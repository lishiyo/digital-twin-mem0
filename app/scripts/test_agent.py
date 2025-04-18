#!/usr/bin/env python
"""Test script for the LangGraph agent.

This script tests the digital twin agent by sending a few test messages
and printing the responses. Make sure to ingest some data first using
the ingest_one_file.py script.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.agent.graph_agent import TwinAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_agent(user_id: str = "test-user"):
    """Test the twin agent with a few sample questions.
    
    Args:
        user_id: User ID for the agent to represent
    """
    logger.info(f"Initializing twin agent for user {user_id}")
    agent = TwinAgent(user_id)
    
    # Define some test questions that might relate to ingested content
    test_questions = [
        "What can you tell me about digital twins?",
        "What is Frontier Tower",
        "Who do you know?",
        "Where do you live?",
    ]
    
    for i, question in enumerate(test_questions):
        logger.info(f"Question {i+1}: {question}")
        
        # Process the question - properly await the async chat method
        response = await agent.chat(question)
        
        logger.info(f"Response: {response}")
        logger.info("-" * 60)
        
        # Add a small delay between questions
        await asyncio.sleep(1)


if __name__ == "__main__":
    # Get user ID from command line if provided
    if len(sys.argv) > 1:
        user_id = sys.argv[1]
    else:
        # Default to a user ID that likely has ingested content
        user_id = "test-user"
    
    logger.info(f"Testing agent with user ID: {user_id}")
    
    # Run the test
    asyncio.run(test_agent(user_id))
    
    logger.info("Agent test completed") 