# Digital Twin Chat Implementation with WebSockets

This document outlines the implementation approach for real-time chat between users and their digital twins, where the chat UI lives in the main application while the digital twin logic and data reside in our service.

## Architecture Overview

```
┌─────────────────┐                ┌───────────────────────┐
│                 │                │                       │
│   Main App      │                │   Digital Twin        │
│   (Frontend)    │                │   Service             │
│                 │                │                       │
│  ┌───────────┐  │    WebSocket   │   ┌───────────────┐   │
│  │           │  │    Connection  │   │               │   │
│  │  User UI  │◄─┼───────────────┼──►│  Twin Agent   │   │
│  │ (Chat Box)│  │                │   │               │   │
│  │           │  │                │   │               │   │
│  └───────────┘  │                │   └───────┬───────┘   │
│                 │                │           │           │
└─────────────────┘                │           ▼           │
                                   │   ┌───────────────┐   │
                                   │   │               │   │
                                   │   │ Profile/Memory│   │
                                   │   │  (Persistence)│   │
                                   │   │               │   │
                                   │   └───────────────┘   │
                                   │                       │
                                   └───────────────────────┘
```

## WebSocket Implementation

### 1. WebSocket Connection Flow

1. **User Authentication in Main App:**
   - User logs into the main application
   - Main app generates a JWT with user identity and permissions

2. **Establishing WebSocket Connection:**
   - Main app initiates WebSocket connection to Digital Twin Service
   - Connection URL: `wss://digital-twin-service.example.com/ws/chat/{user_id}`
   - Required headers:
     - `Authorization: Bearer {jwt_token}`
     - `X-Session-ID: {unique_session_id}` (allows multiple concurrent sessions)

3. **Connection Validation:**
   - Digital Twin Service validates JWT
   - Confirms `user_id` in URL matches JWT subject claim
   - Creates a WebSocket session mapped to this user's digital twin

### 2. Message Protocol

All messages use JSON format with a consistent structure:

```json
{
  "type": "message_type",
  "payload": { /* message-specific data */ },
  "metadata": {
    "timestamp": "ISO-8601 timestamp",
    "session_id": "unique_session_id",
    "message_id": "unique_message_id"
  }
}
```

#### Message Types:

1. **From Main App to Digital Twin Service:**
   - `user_message`: User's chat message
   - `context_update`: Project/environment context changes
   - `feedback`: User feedback on twin's responses
   - `typing_indicator`: User is typing (optional)
   - `read_receipt`: User has read message (optional)
   - `heartbeat`: Connection keep-alive

2. **From Digital Twin Service to Main App:**
   - `twin_message`: Complete message from twin
   - `twin_message_chunk`: Partial/streaming response chunk
   - `twin_thinking`: Indicates twin is processing (optional)
   - `profile_update`: Notification that user profile was updated
   - `error`: Error information
   - `heartbeat_ack`: Heartbeat acknowledgment

#### Example Messages:

**User Message:**
```json
{
  "type": "user_message",
  "payload": {
    "text": "How should we approach the authentication feature?",
    "context": {
      "project_id": "proj-123",
      "current_page": "sprint-planning",
      "task_id": "task-456"
    }
  },
  "metadata": {
    "timestamp": "2023-06-12T14:22:31Z",
    "session_id": "sess-789",
    "message_id": "msg-abc123"
  }
}
```

**Twin Response (Streaming):**
```json
{
  "type": "twin_message_chunk",
  "payload": {
    "text": "Based on your preference for",
    "chunk_index": 3,
    "is_last_chunk": false
  },
  "metadata": {
    "timestamp": "2023-06-12T14:22:33Z",
    "session_id": "sess-789",
    "message_id": "msg-def456",
    "in_response_to": "msg-abc123"
  }
}
```

## Implementation Details

### 1. Digital Twin Service WebSocket Server

**Technology Options:**
- FastAPI with WebSockets (built on Starlette)
- Django Channels
- Standalone WebSocket server using libraries like websockets, Socket.IO, or Tornado

**Recommended Stack:**
- FastAPI + WebSockets (integrates well with existing FastAPI REST endpoints)
- Redis PubSub for coordinating multiple server instances
- Celery for background processing

**Connection Management:**
```python
# Example using FastAPI (simplified)
@app.websocket("/ws/chat/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    # Get token from header
    token = websocket.headers.get("authorization", "").replace("Bearer ", "")
    session_id = websocket.headers.get("x-session-id")
    
    # Authenticate
    try:
        jwt_payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        if jwt_payload["sub"] != user_id:
            await websocket.close(code=4003, reason="Unauthorized")
            return
    except Exception as e:
        await websocket.close(code=4003, reason="Invalid token")
        return
    
    # Accept connection
    await websocket.accept()
    
    # Register connection in connection manager
    await connection_manager.connect(user_id, session_id, websocket)
    
    try:
        # Main message loop
        while True:
            data = await websocket.receive_json()
            await process_message(user_id, session_id, data, websocket)
    except WebSocketDisconnect:
        # Handle disconnection
        connection_manager.disconnect(user_id, session_id)
```

### 2. Handling Multiple Users & Sessions

The Digital Twin Service needs to maintain a registry of active WebSocket connections:

```python
class ConnectionManager:
    def __init__(self):
        # user_id -> {session_id -> websocket}
        self.active_connections = {}
        self.lock = asyncio.Lock()
    
    async def connect(self, user_id: str, session_id: str, websocket: WebSocket):
        async with self.lock:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = {}
            self.active_connections[user_id][session_id] = websocket
    
    async def disconnect(self, user_id: str, session_id: str):
        async with self.lock:
            if user_id in self.active_connections:
                if session_id in self.active_connections[user_id]:
                    del self.active_connections[user_id][session_id]
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
    
    async def send_message(self, user_id: str, message: dict, exclude_session=None):
        if user_id in self.active_connections:
            for session_id, websocket in self.active_connections[user_id].items():
                if session_id != exclude_session:
                    await websocket.send_json(message)
```

For horizontal scaling with multiple server instances, use Redis PubSub to coordinate messages across instances.

### 3. Processing Messages with LangGraph

When a user message is received, launch the LangGraph agent to process it but stream the response:

```python
async def process_message(user_id: str, session_id: str, message: dict, websocket: WebSocket):
    if message["type"] == "user_message":
        # Acknowledge receipt
        ack = {
            "type": "message_received",
            "payload": {"message_id": message["metadata"]["message_id"]},
            "metadata": {"timestamp": datetime.utcnow().isoformat()}
        }
        await websocket.send_json(ack)
        
        # Start LangGraph agent in background
        asyncio.create_task(
            process_with_langgraph(user_id, session_id, message, websocket)
        )
    
    # Handle other message types...

async def process_with_langgraph(user_id: str, session_id: str, message: dict, websocket: WebSocket):
    # Get or create a LangGraph agent for this user
    agent = await get_user_agent(user_id)
    
    # Store message in database
    msg_id = await store_user_message(user_id, message["payload"]["text"], 
                                     message["payload"].get("context", {}))
    
    # Set up streaming callback
    async def stream_callback(chunk: str, is_last: bool = False):
        chunk_msg = {
            "type": "twin_message_chunk",
            "payload": {
                "text": chunk,
                "is_last_chunk": is_last
            },
            "metadata": {
                "timestamp": datetime.utcnow().isoformat(),
                "session_id": session_id,
                "message_id": f"chunk-{uuid.uuid4()}",
                "in_response_to": message["metadata"]["message_id"]
            }
        }
        await websocket.send_json(chunk_msg)
    
    # Run agent with streaming
    try:
        full_response = await agent.astream_chat(
            message["payload"]["text"],
            context=message["payload"].get("context", {}),
            streaming_callback=stream_callback
        )
        
        # Store the complete response
        await store_twin_response(user_id, msg_id, full_response)
        
        # Trigger profile update in background
        asyncio.create_task(
            update_user_profile_from_chat(user_id, message["payload"]["text"], full_response)
        )
        
    except Exception as e:
        error_msg = {
            "type": "error",
            "payload": {"error": str(e)},
            "metadata": {
                "timestamp": datetime.utcnow().isoformat(),
                "session_id": session_id,
                "in_response_to": message["metadata"]["message_id"]
            }
        }
        await websocket.send_json(error_msg)
```

### 4. Persistence & Background Processing

1. **Message Storage:**
   - Store all user messages and twin responses in the database
   - Include metadata like timestamp, context, session ID

2. **Profile Updates:**
   - Process chat messages asynchronously to extract profile information
   - Update UserProfile model and Graphiti nodes based on new information
   - Run confidence scoring to determine which updates to apply

3. **Background Tasks:**
   - Use Celery for heavier processing tasks like:
     - Trait extraction from chat history
     - Updating knowledge graphs
     - Generating profile statistics

## Main App Integration

### 1. WebSocket Client in Main App

The main application needs to implement a WebSocket client that:

1. **Connects to Digital Twin Service:**
   ```javascript
   // Example using JavaScript
   const connectToTwin = (userId, jwt) => {
     const socket = new WebSocket(`wss://digital-twin-service.example.com/ws/chat/${userId}`);
     
     // Add headers to WebSocket connection
     socket.setRequestHeader('Authorization', `Bearer ${jwt}`);
     socket.setRequestHeader('X-Session-ID', generateSessionId());
     
     socket.onopen = () => {
       console.log('Connected to digital twin');
     };
     
     socket.onmessage = (event) => {
       const data = JSON.parse(event.data);
       handleTwinMessage(data);
     };
     
     socket.onclose = (event) => {
       console.log(`Connection closed: ${event.code}, ${event.reason}`);
       // Implement reconnection logic
     };
     
     return socket;
   };
   ```

2. **Handles Message Updates:**
   ```javascript
   const handleTwinMessage = (data) => {
     switch(data.type) {
       case 'twin_message_chunk':
         // Append to UI or update streaming message
         updateChatUI(data.payload.text, data.payload.is_last_chunk);
         break;
       
       case 'twin_thinking':
         // Show thinking indicator
         showThinkingIndicator();
         break;
       
       case 'error':
         // Show error in UI
         showErrorMessage(data.payload.error);
         break;
       
       // Handle other message types
     }
   };
   ```

3. **Sends Messages & Context:**
   ```javascript
   const sendMessage = (text, contextData = {}) => {
     const message = {
       type: 'user_message',
       payload: {
         text: text,
         context: contextData
       },
       metadata: {
         timestamp: new Date().toISOString(),
         session_id: currentSessionId,
         message_id: generateMessageId()
       }
     };
     
     socket.send(JSON.stringify(message));
   };
   ```

### 2. Context Transmission

The main app is responsible for sending relevant context to the digital twin:

1. **Initial Context:** Send project/environment information when connecting
2. **Context Updates:** Send updates when the user navigates to different parts of the app
3. **Regular Context Refresh:** Periodically send updated context (e.g., team member status)

## Security Considerations

1. **Authentication:**
   - Use JWT with appropriate expiration
   - Validate token on every WebSocket connection
   - Consider token refresh mechanism for long-lived connections

2. **Authorization:**
   - Ensure users can only access their own digital twin
   - Implement proper scopes/permissions in JWT claims

3. **Data Privacy:**
   - Encrypt sensitive data in transit (HTTPS/WSS)
   - Store conversation history securely
   - Implement proper data retention policies

4. **Rate Limiting:**
   - Protect against abuse with connection and message rate limits
   - Implement exponential backoff for reconnection attempts

## Scaling Considerations

1. **Stateful Connections:**
   - WebSockets maintain state, requiring sticky sessions or connection sharing
   - Use Redis or similar for connection registry across multiple server instances

2. **Load Balancing:**
   - Ensure load balancers support WebSocket protocol (long-lived connections)
   - Consider connection draining during deployments

3. **Performance:**
   - Batch database operations where possible
   - Use caching for frequently accessed user profiles and agent state
   - Monitor connection counts and resource usage

4. **Connection Management:**
   - Handle reconnections gracefully with message queuing
   - Implement heartbeats to detect stale connections
   - Have a strategy for graceful degradation under high load

## Implementation Phases

1. **Phase 1: Basic WebSocket Infrastructure**
   - Set up WebSocket server endpoints
   - Implement authentication and connection management
   - Create basic message passing without LangGraph integration

2. **Phase 2: LangGraph Integration**
   - Implement streaming response from LangGraph agents
   - Set up message persistence
   - Add basic error handling

3. **Phase 3: Profile Integration**
   - Implement background profile updates from chat
   - Add confidence scoring for extracted traits
   - Develop feedback processing

4. **Phase 4: Advanced Features**
   - Add typing indicators and read receipts
   - Implement multi-device synchronization
   - Enhance context processing 