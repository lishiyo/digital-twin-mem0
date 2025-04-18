# LangGraph Workflow for Digital Twin Agent

This document explains how LangGraph orchestrates the Digital Twin agent in the Frontier Tower project.

## Overview

LangGraph provides a flexible way to build stateful, multi-step reasoning workflows for LLM agents. In our implementation, we use LangGraph to:

1. Retrieve information from multiple sources (Mem0 and Graphiti)
2. Merge context from these sources
3. Generate coherent responses based on the user's personal data

## State Management

### State Structure

Our agent uses a TypedDict-based state schema with the following keys:

```python
class AgentStateDict(TypedDict, total=False):
    user_id: str                       # The user ID the agent represents
    messages: List[Any]                # Conversation history 
    mem0_results: List[Dict[str, Any]] # Results from Mem0 memory
    graphiti_results: Dict[str, List]  # Results from Graphiti knowledge graph
    merged_context: str                # Combined context for LLM
    twin_response: str                 # Generated response
    error: str                         # Error if any occurred
```

This state is passed between nodes and updated at each step.

## Workflow Graph

The workflow is defined as a directed graph with four primary nodes:

1. `retrieve_from_mem0`: Fetches personal memories from Mem0
2. `retrieve_from_graphiti`: Fetches knowledge graph information from Graphiti
3. `merge_context`: Combines results into a coherent context
4. `generate_response`: Uses the LLM to generate the final response

The flow is linear:
```
retrieve_from_mem0 → retrieve_from_graphiti → merge_context → generate_response → END
```

Example run flow:
```
agent = TwinAgent(user_id="connie", model_name="gpt-4o")
response = await agent.chat("What has OpenAI said about GraphRAG?")

1. retrieve_from_mem0       ← search in Mem0
2. retrieve_from_graphiti   ← search entities & facts in Graphiti
3. merge_context            ← combine both into a prompt
4. generate_response        ← call LLM to reply
```

## Implementation Details

### Node Functions

Each node is implemented as a function that:
1. Takes the current state dictionary
2. Performs its specific task
3. Returns an updated state dictionary

For example, the `retrieve_from_mem0` node:
```python
def _retrieve_from_mem0(self, state: Dict[str, Any]) -> Dict[str, Any]:
    # Convert dict to AgentState object for easier handling
    state_obj = AgentState.from_dict(state)
    
    try:
        # Get last user message and query Mem0
        # ...
        mem0_results = asyncio.run(
            self.memory_service.search(
                query=last_user_message,
                user_id=state_obj.user_id,
                limit=5
            )
        )
        
        # Update state with results
        state_obj.mem0_results = mem0_results
    except Exception as e:
        state_obj.error = f"Mem0 retrieval error: {str(e)}"
    
    # Convert back to dictionary
    return state_obj.to_dict()
```

### Building and Running the Workflow

The workflow is built in the `_build_workflow` method, which:
1. Creates a `StateGraph` with our state schema
2. Adds node functions
3. Defines edges between nodes
4. Sets the entry point
5. Compiles the graph

To execute the workflow, we use the `invoke` method with an initial state:

```python
async def chat(self, user_message: str) -> str:
    # Initialize state dictionary
    initial_state = {
        "user_id": self.user_id,
        "messages": [HumanMessage(content=user_message)],
        # ...other default values
    }
    
    # Run the workflow
    result = self.workflow.invoke(initial_state)
    
    # Extract response from final state
    return final_state.twin_response
```

## Context Merging Strategy

The `merge_context` node combines information from multiple sources:

1. Personal memories from Mem0
2. Entity information from Graphiti
3. Graph facts from Graphiti

The merged context is formatted as a structured text block with sections, which is then included in the system prompt for the LLM.

## Error Handling

Each node contains error handling that:
1. Catches exceptions
2. Records errors in the state
3. Allows the workflow to continue to subsequent nodes

The final response generation checks if an error occurred at any step and returns a user-friendly error message if needed.

## Testing and Debugging

To test the agent, use the `test_agent.py` script, which:
1. Initializes the agent for a test user
2. Sends a series of test questions
3. Logs responses and any errors

For debugging, check the logs to see:
- Which data was retrieved from each source
- How much context was merged
- Any errors that occurred in the workflow

## Performance Considerations

- Asynchronous queries to Mem0 and Graphiti are run in event loops
- Results are limited to prevent context overflows (5 results per source)
- Error handling prevents cascading failures

## Extension Points

The modular design allows for easy extensions:
- Add new data sources as additional nodes
- Implement branching logic in the workflow
- Add feedback loops or reinforcement learning
- Implement streaming responses instead of blocking calls 