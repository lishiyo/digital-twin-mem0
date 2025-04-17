"""Graphiti service for knowledge graph operations."""

from typing import Any, Dict, List, Optional

from graphiti_core import Graphiti
from graphiti_core.llm_client import OpenAIClient

from app.core.config import settings


class GraphitiService:
    """Service for interacting with Graphiti knowledge graph."""

    def __init__(self):
        """Initialize the Graphiti service."""
        self.client = Graphiti(
            settings.NEO4J_URI,
            settings.NEO4J_USER,
            settings.NEO4J_PASSWORD,
            llm_client=OpenAIClient(),
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

        # Add episode to Graphiti
        episode_id = await self.client.add_episode(content=content, metadata=metadata)

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
