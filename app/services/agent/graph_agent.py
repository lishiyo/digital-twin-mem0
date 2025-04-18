"""LangGraph-based agent implementation for the digital twin.

This module implements the LangGraph agent that serves as the digital twin,
using Mem0 for memory and Graphiti for knowledge graph retrieval.
"""

import os
import logging
import asyncio
from typing import Dict, List, Any, Optional, TypedDict, Coroutine
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from app.services.memory import MemoryService
from app.services.graph import GraphitiService
from app.core.config import settings

logger = logging.getLogger(__name__)

# Define the agent state schema as TypedDict for LangGraph compatibility
class AgentStateDict(TypedDict, total=False):
    user_id: str
    messages: List[Any]
    mem0_results: List[Dict[str, Any]]
    graphiti_results: Dict[str, List]
    merged_context: str
    twin_response: str
    error: str

# Keep the original AgentState class for object-oriented usage
class AgentState:
    """State for the agent's thought process."""
    
    def __init__(
        self,
        user_id: str,
        messages: List[Any],
        mem0_results: Optional[List[Dict[str, Any]]] = None,
        graphiti_results: Optional[Dict[str, List]] = None,
        merged_context: Optional[str] = None,
        twin_response: Optional[str] = None,
        error: Optional[str] = None,
    ):
        self.user_id = user_id
        self.messages = messages  # The conversation history
        self.mem0_results = mem0_results or []  # Results from Mem0
        self.graphiti_results = graphiti_results or {}  # Results from Graphiti
        self.merged_context = merged_context  # Combined context
        self.twin_response = twin_response  # Generated response
        self.error = error  # Error if any

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary."""
        return {
            "user_id": self.user_id,
            "messages": self.messages,
            "mem0_results": self.mem0_results,
            "graphiti_results": self.graphiti_results,
            "merged_context": self.merged_context,
            "twin_response": self.twin_response,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, state_dict: Dict[str, Any]) -> "AgentState":
        """Create state from dictionary."""
        return cls(
            user_id=state_dict.get("user_id", ""),
            messages=state_dict.get("messages", []),
            mem0_results=state_dict.get("mem0_results", []),
            graphiti_results=state_dict.get("graphiti_results", {}),
            merged_context=state_dict.get("merged_context"),
            twin_response=state_dict.get("twin_response"),
            error=state_dict.get("error"),
        )


class TwinAgent:
    """LangGraph-based agent implementing the digital twin."""
    
    def __init__(self, user_id: str, model_name: str = "gpt-4.1-2025-04-14"):
        """Initialize the twin agent.
        
        Args:
            user_id: The user ID the agent is representing
            model_name: The OpenAI model to use
        """
        self.user_id = user_id
        self.memory_service = MemoryService()
        self.graphiti_service = GraphitiService()
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=0.7,
            api_key=settings.OPENAI_API_KEY,
        )
        
        # Build the agent workflow
        self.workflow = self._build_workflow()
    
    async def _retrieve_from_mem0(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve relevant context from Mem0."""
        state_obj = AgentState.from_dict(state)
        
        try:
            # Get the last user message
            last_user_message = None
            for message in reversed(state_obj.messages):
                if isinstance(message, HumanMessage):
                    last_user_message = message.content
                    break
            
            if not last_user_message:
                state_obj.error = "No user message found"
                return state_obj.to_dict()
            
            # Directly await the async call - we're already in an event loop
            mem0_results = await self.memory_service.search(
                query=last_user_message,
                user_id=state_obj.user_id,
                limit=5
            )
            
            # Process the Mem0 results to handle potential format issues
            processed_results = []
            for result in mem0_results:
                # Create a processed copy
                processed = dict(result)
                
                # Handle content extraction based on Mem0 API response format
                if "content" not in processed or not processed["content"]:
                    # Check for memory field (primary content field in the API response)
                    if "memory" in processed:
                        processed["content"] = processed["memory"]
                    # Fallback to message field if present
                    elif "message" in processed:
                        if isinstance(processed["message"], dict) and "content" in processed["message"]:
                            processed["content"] = processed["message"]["content"]
                        elif isinstance(processed["message"], str):
                            processed["content"] = processed["message"]
                
                # Get similarity score from the appropriate field
                if "similarity" not in processed or processed["similarity"] is None:
                    if "score" in processed and processed["score"] is not None:
                        processed["similarity"] = processed["score"]
                    else:
                        processed["similarity"] = 0.5  # Default reasonable value
                
                # Ensure metadata is a dict
                if "metadata" not in processed or processed["metadata"] is None:
                    processed["metadata"] = {}
                
                processed_results.append(processed)
            
            # Log detailed results for debugging
            logger.info(f"Retrieved {len(processed_results)} results from Mem0")
            for i, result in enumerate(processed_results):
                content = result.get("content", "")
                similarity = result.get("similarity", 0)
                metadata = result.get("metadata", {})
                source = metadata.get("source_file", metadata.get("source", "unknown"))
                content_preview = content[:100] + "..." if len(content) > 100 else content
                # logger.info(f"Mem0 result {i+1}: {content_preview} (relevance: {similarity:.2f}, source: {source})")
            
            state_obj.mem0_results = processed_results
            
        except Exception as e:
            state_obj.error = f"Mem0 retrieval error: {str(e)}"
            logger.error(state_obj.error)
        
        return state_obj.to_dict()
    
    async def _retrieve_from_graphiti(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve relevant context from Graphiti."""
        state_obj = AgentState.from_dict(state)
        
        try:
            # Get the last user message
            last_user_message = None
            for message in reversed(state_obj.messages):
                if isinstance(message, HumanMessage):
                    last_user_message = message.content
                    break
            
            if not last_user_message:
                state_obj.error = "No user message found"
                return state_obj.to_dict()
            
            # Directly await the async calls
            entity_results = await self.graphiti_service.node_search(
                query=last_user_message,
                limit=5
            )
            
            # Also search general graph results
            graph_results = await self.graphiti_service.search(
                query=last_user_message,
                user_id=state_obj.user_id,
                limit=5
            )
            
            # Log detailed entity results
            logger.info(f"Retrieved {len(entity_results)} entities from Graphiti")
            for i, entity in enumerate(entity_results):
                name = entity.get("name", "")
                labels = entity.get("labels", [])
                summary = entity.get("summary", "")
                labels_str = ", ".join(labels) if labels else ""
                # logger.info(f"Entity {i+1}: {name} ({labels_str}): {summary}")
            
            # Log detailed graph facts
            logger.info(f"Retrieved {len(graph_results)} graph facts from Graphiti")
            for i, fact in enumerate(graph_results):
                fact_text = fact.get("fact", "")
                score = fact.get("score", 0)
                safe_score = 0.0 if score is None else score
                # logger.info(f"Fact {i+1}: {fact_text} (confidence: {safe_score:.2f})")
            
            # Combine the results
            state_obj.graphiti_results = {
                "entities": entity_results,
                "graph": graph_results
            }
            
        except Exception as e:
            state_obj.error = f"Graphiti retrieval error: {str(e)}"
            logger.error(state_obj.error)
        
        return state_obj.to_dict()
    
    def _merge_context(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Merge context from Mem0 and Graphiti."""
        state_obj = AgentState.from_dict(state)
        
        try:
            merged_context = "Relevant context:\n\n"
            
            # Add Mem0 results
            if state_obj.mem0_results:
                merged_context += "From memory:\n"
                for i, result in enumerate(state_obj.mem0_results):
                    content = result.get("content", "")
                    similarity = result.get("similarity", 0)
                    metadata = result.get("metadata", {})
                    
                    # Extract better source information
                    source = "unknown"
                    if "source_file" in metadata:
                        source = metadata["source_file"]
                    elif "source" in metadata:
                        source = metadata["source"]
                    
                    # Include more metadata if available
                    meta_str = f"source: {source}"
                    if "title" in metadata:
                        meta_str += f", title: {metadata['title']}"
                    if "categories" in result and result["categories"]:
                        meta_str += f", categories: {', '.join(result['categories'])}"
                    
                    # Format relevance with two decimal places
                    relevance_str = f"{similarity:.2f}" if similarity is not None else "N/A"
                    
                    # Use a reasonable preview length - longer than before
                    preview_length = 1000
                    content_preview = content
                    if len(content) > preview_length:
                        content_preview = content[:preview_length] + "..."
                    
                    merged_context += f"{i+1}. {content_preview} (relevance: {relevance_str}, {meta_str})\n\n"
            
            # Add Graphiti entity results
            if state_obj.graphiti_results and "entities" in state_obj.graphiti_results:
                entities = state_obj.graphiti_results["entities"]
                if entities:
                    merged_context += "From knowledge graph (entities):\n"
                    for i, entity in enumerate(entities):
                        name = entity.get("name", "")
                        labels = entity.get("labels", [])
                        summary = entity.get("summary", "")
                        
                        # Safely format labels
                        labels_str = ", ".join(labels) if labels else ""
                        
                        merged_context += f"{i+1}. {name} ({labels_str}): {summary}\n\n"
            
            # Add Graphiti graph results
            if state_obj.graphiti_results and "graph" in state_obj.graphiti_results:
                graph = state_obj.graphiti_results["graph"]
                if graph:
                    merged_context += "From knowledge graph (facts):\n"
                    for i, fact in enumerate(graph):
                        fact_text = fact.get("fact", "")
                        score = fact.get("score", 0)
                        
                        # Handle potentially None score with safe default
                        safe_score = 0.0 if score is None else score
                        
                        merged_context += f"{i+1}. {fact_text} (confidence: {safe_score:.2f})\n\n"
            
            state_obj.merged_context = merged_context
            logger.info("Successfully merged context from different sources")
            # logger.info(f"Final merged context:\n{merged_context}") # already logged in _generate_response
            
        except Exception as e:
            state_obj.error = f"Context merging error: {str(e)}"
            logger.error(state_obj.error)
        
        return state_obj.to_dict()
    
    async def _generate_response(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a response using the LLM."""
        state_obj = AgentState.from_dict(state)
        
        try:
            # Create system prompt with merged context
            system_content = f"""You are a helpful assistant with access to the user's personal knowledge base.
            You should answer questions using the context provided when relevant, 
            but you can also use your general knowledge for common questions.
            Always be truthful, helpful, and concise.
            
            {state_obj.merged_context}
            """
            
            # Log the full system prompt for debugging
            logger.info(f"System prompt sent to LLM:\n{system_content}")
            
            # Prepare messages
            messages = [SystemMessage(content=system_content)]
            messages.extend(state_obj.messages)
            
            # Call the LLM
            response = await self.llm.ainvoke(messages)
            
            # Save the response
            state_obj.twin_response = response.content
            logger.info("Successfully generated response from LLM")
            
        except Exception as e:
            state_obj.error = f"Response generation error: {str(e)}"
            logger.error(state_obj.error)
        
        return state_obj.to_dict()
    
    def _should_end(self, state: Dict[str, Any]) -> str:
        """Determine if the workflow should end."""
        state_obj = AgentState.from_dict(state)
        
        # End if there's an error or we have a response
        if state_obj.error or state_obj.twin_response:
            return END
        
        # Continue to retrieve from Graphiti
        return "retrieve_from_graphiti"
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow."""
        # Create a state graph with TypedDict schema
        workflow = StateGraph(AgentStateDict)
        
        # Add nodes - note that we're adding async functions
        workflow.add_node("retrieve_from_mem0", self._retrieve_from_mem0)
        workflow.add_node("retrieve_from_graphiti", self._retrieve_from_graphiti)
        workflow.add_node("merge_context", self._merge_context)
        workflow.add_node("generate_response", self._generate_response)
        
        # Add edges
        workflow.add_edge("retrieve_from_mem0", "retrieve_from_graphiti")
        workflow.add_edge("retrieve_from_graphiti", "merge_context")
        workflow.add_edge("merge_context", "generate_response")
        workflow.add_edge("generate_response", END)
        
        # Set entry point
        workflow.set_entry_point("retrieve_from_mem0")
        
        # Compile the graph
        return workflow.compile()
    
    async def chat(self, user_message: str) -> str:
        """Process a user message and generate a response.
        
        Args:
            user_message: The user's message
            
        Returns:
            The agent's response
        """
        try:
            # Initialize state as a dictionary for LangGraph (not as AgentState instance)
            initial_state = {
                "user_id": self.user_id,
                "messages": [HumanMessage(content=user_message)],
                "mem0_results": [],
                "graphiti_results": {},
                "merged_context": None,
                "twin_response": None,
                "error": None
            }
            
            # Run the workflow with dictionary state
            # Use ainvoke instead of invoke for async workflows
            result = await self.workflow.ainvoke(initial_state)
            final_state = AgentState.from_dict(result)
            
            if final_state.error:
                logger.error(f"Error in agent workflow: {final_state.error}")
                return f"I encountered an error: {final_state.error}"
            
            if not final_state.twin_response:
                logger.error("No response generated")
                return "I'm unable to generate a response right now. Please try again later."
            
            return final_state.twin_response
            
        except Exception as e:
            logger.error(f"Error running agent workflow: {e}")
            return f"I encountered an error: {e}" 