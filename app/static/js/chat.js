document.addEventListener('DOMContentLoaded', function() {
    // DOM elements
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    const messagesContainer = document.getElementById('messages-container');
    const conversationsList = document.getElementById('conversations-list');
    const newConversationButton = document.getElementById('new-conversation');
    const currentConversationTitle = document.getElementById('current-conversation-title');
    
    // Application state
    let currentConversationId = null;
    let conversations = [];
    
    // Initialize the chat interface
    init();
    
    // Event listeners
    messageInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    sendButton.addEventListener('click', sendMessage);
    
    newConversationButton.addEventListener('click', function() {
        currentConversationId = null;
        currentConversationTitle.textContent = 'New Conversation';
        messagesContainer.innerHTML = '';
        messageInput.focus();
    });
    
    // Functions
    async function init() {
        // Fetch existing conversations
        try {
            const response = await fetch('/api/v1/chat/conversations');
            if (response.ok) {
                const data = await response.json();
                conversations = data.conversations || [];
                renderConversationsList();
            } else {
                console.error('Failed to fetch conversations:', response.statusText);
            }
        } catch (error) {
            console.error('Error fetching conversations:', error);
        }
    }
    
    function renderConversationsList() {
        conversationsList.innerHTML = '';
        
        if (conversations.length === 0) {
            const emptyState = document.createElement('div');
            emptyState.className = 'empty-state';
            emptyState.textContent = 'No conversations yet';
            conversationsList.appendChild(emptyState);
            return;
        }
        
        conversations.forEach(conversation => {
            const conversationItem = document.createElement('div');
            conversationItem.className = 'conversation-item';
            if (conversation.id === currentConversationId) {
                conversationItem.classList.add('active');
            }
            
            const title = document.createElement('div');
            title.className = 'conversation-title';
            title.textContent = conversation.title || 'Untitled Conversation';
            
            const date = document.createElement('div');
            date.className = 'conversation-date';
            date.textContent = formatDate(conversation.updated_at);
            
            conversationItem.appendChild(title);
            conversationItem.appendChild(date);
            
            conversationItem.addEventListener('click', function() {
                loadConversation(conversation.id);
            });
            
            conversationsList.appendChild(conversationItem);
        });
    }
    
    async function loadConversation(conversationId) {
        try {
            const response = await fetch(`/api/v1/chat/conversations/${conversationId}`);
            if (response.ok) {
                const conversation = await response.json();
                currentConversationId = conversation.id;
                currentConversationTitle.textContent = conversation.title || 'Untitled Conversation';
                
                // Mark as active in the sidebar
                document.querySelectorAll('.conversation-item').forEach(item => {
                    item.classList.remove('active');
                });
                document.querySelector(`.conversation-item:nth-child(${conversations.findIndex(c => c.id === conversationId) + 1})`).classList.add('active');
                
                // Render messages
                renderMessages(conversation.messages);
            } else {
                console.error('Failed to load conversation:', response.statusText);
            }
        } catch (error) {
            console.error('Error loading conversation:', error);
        }
    }
    
    function renderMessages(messages) {
        messagesContainer.innerHTML = '';
        
        messages.forEach(message => {
            appendMessage(message.role, message.content, message.created_at);
        });
        
        // Scroll to bottom
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
    
    async function sendMessage() {
        const messageText = messageInput.value.trim();
        if (!messageText) return;
        
        // Disable input during processing
        messageInput.disabled = true;
        sendButton.disabled = true;
        
        // Add user message to UI immediately
        appendMessage('user', messageText);
        
        // Clear input
        messageInput.value = '';
        
        try {
            // Prepare API request
            const requestData = {
                message: messageText,
                conversation_id: currentConversationId,
                metadata: {} // Optional metadata
            };
            
            // Send to API
            const response = await fetch('/api/v1/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            });
            
            if (response.ok) {
                const data = await response.json();
                
                // Update conversation ID if this was a new conversation
                if (!currentConversationId) {
                    currentConversationId = data.conversation_id;
                    
                    // Refresh conversations list
                    init();
                }
                
                // Add assistant response to UI
                appendMessage('assistant', data.twin_response);
                
                // Update conversation title if this was a new conversation
                if (currentConversationTitle.textContent === 'New Conversation') {
                    // Generate title from first user message
                    currentConversationTitle.textContent = messageText.length > 30 
                        ? messageText.substring(0, 30) + '...' 
                        : messageText;
                }
            } else {
                const errorData = await response.json();
                console.error('Error from API:', errorData);
                appendMessage('system', 'Error: Failed to send message. Please try again.');
            }
        } catch (error) {
            console.error('Error sending message:', error);
            appendMessage('system', 'Error: Could not connect to the server. Please check your connection.');
        } finally {
            // Re-enable input
            messageInput.disabled = false;
            sendButton.disabled = false;
            messageInput.focus();
        }
    }
    
    function appendMessage(role, content, timestamp = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message message-${role}`;
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        messageContent.textContent = content;
        
        const messageTime = document.createElement('div');
        messageTime.className = 'message-time';
        messageTime.textContent = timestamp ? formatDate(timestamp) : formatDate(new Date().toISOString());
        
        messageDiv.appendChild(messageContent);
        messageDiv.appendChild(messageTime);
        
        messagesContainer.appendChild(messageDiv);
        
        // Scroll to bottom
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
    
    function formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleString('en-US', { 
            month: 'short', 
            day: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        });
    }
}); 