"""Graphiti service for knowledge graph operations."""

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import json

from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from graphiti_core.llm_client import OpenAIClient
import openai

from app.core.config import settings


class GraphitiService:
    """Service for interacting with Graphiti knowledge graph."""

    def __init__(self):
        """Initialize the Graphiti service."""
        # Configure OpenAI with API key
        openai.api_key = settings.OPENAI_API_KEY
        
        # Initialize Graphiti client
        self.client = Graphiti(
            settings.NEO4J_URI,
            settings.NEO4J_USER,
            settings.NEO4J_PASSWORD,
            llm_client=OpenAIClient()  # Graphiti will use the global OpenAI client
        )

    async def add_episode(
        self, content: str, user_id: str, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Add an episode to the knowledge graph.

        Args:
            content: The content of the episode
            user_id: The user ID associated with the episode
            metadata: Optional metadata for the episode

        Returns:
            Dictionary with episode information
        """
        # Create metadata if not provided
        if metadata is None:
            metadata = {}

        # Add user_id to metadata
        metadata["user_id"] = user_id
        
        # Prepare name for the episode (include metadata info in the name)
        meta_info = "-".join(f"{k}_{v}" for k, v in metadata.items() if k != "user_id")
        episode_name = f"Episode-{user_id}-{meta_info}-{datetime.now(timezone.utc).isoformat()}"
        
        # Add episode to Graphiti using the correct method signature
        # See api docs: https://help.getzep.com/graphiti/graphiti/adding-episodes
        episode_results = await self.client.add_episode(
            name=episode_name,
            episode_body=content,
            source=EpisodeType.text,
            source_description=f"User content from {user_id}",
            reference_time=datetime.now(timezone.utc)
        )

        # From the test output, we can see the AddEpisodeResults contains an EpisodicNode with a uuid
        # The format is: "episode=EpisodicNode(uuid='6fe7a92c-ee6b-4d0d-bdb5-ff42f4ba34c9',"
        result_str = str(episode_results)
        
        # Extract UUID using string operations
        if "uuid='" in result_str:
            # Find the UUID between uuid=' and the next quote
            start_idx = result_str.find("uuid='") + 6
            end_idx = result_str.find("'", start_idx)
            if end_idx > start_idx:
                episode_id = result_str[start_idx:end_idx]
            else:
                episode_id = f"unknown-{datetime.now(timezone.utc).isoformat()}"
        else:
            # Fallback to the previous method
            if hasattr(episode_results, "episode_uuid"):
                episode_id = episode_results.episode_uuid
            elif hasattr(episode_results, "uuid"):
                episode_id = episode_results.uuid
            else:
                episode_id = str(episode_results)

        return {"episode_id": episode_id, "user_id": user_id}

    async def search(self, query: str, user_id: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search the knowledge graph.

        Args:
            query: The search query
            user_id: The user ID to filter results by
            limit: Maximum number of results to return

        Returns:
            List of search results
        """
        # Use the user_id as a filter for the search
        filters = {"metadata.user_id": user_id}

        # Search episodes in Graphiti
        search_results = await self.client.search_episodes(
            query=query, limit=limit, filters=filters
        )

        return search_results
