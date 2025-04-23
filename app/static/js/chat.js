document.addEventListener('DOMContentLoaded', function() {
    // DOM elements
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    const messagesContainer = document.getElementById('messages-container');
    const conversationsList = document.getElementById('conversations-list');
    const newConversationButton = document.getElementById('new-conversation');
    const currentConversationTitle = document.getElementById('current-conversation-title');
    const summarizeButton = document.getElementById('summarize-button');
    
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
    
    // Add event listener for summarize button if it exists
    if (summarizeButton) {
        summarizeButton.addEventListener('click', function() {
            summarizeConversation();
        });
    }
    
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
                appendMessage('assistant', data.message);
                
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
    
    async function summarizeConversation() {
        if (!currentConversationId) {
            appendMessage('system', 'Please start or select a conversation first.');
            return;
        }
        
        try {
            // Show loading indicator
            const loadingMessage = document.createElement('div');
            loadingMessage.className = 'message message-system';
            loadingMessage.innerHTML = '<div class="message-content">Summarizing conversation...</div>';
            messagesContainer.appendChild(loadingMessage);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
            
            // Call API to summarize
            const response = await fetch(`/api/v1/chat/conversations/${currentConversationId}/summarize`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) {
                // Remove loading indicator
                messagesContainer.removeChild(loadingMessage);
                
                const errorData = await response.json();
                console.error('Error summarizing conversation:', errorData);
                appendMessage('system', 'Error: Failed to summarize conversation. Please try again.');
                return;
            }
            
            const data = await response.json();
            
            if (data.status !== 'pending' || !data.task_id) {
                // Remove loading indicator
                messagesContainer.removeChild(loadingMessage);
                
                appendMessage('system', `Failed to summarize: ${data.detail || 'Unknown error'}`);
                return;
            }
            
            // Update loading message to show it's processing
            loadingMessage.innerHTML = '<div class="message-content">Processing summary... This may take a moment.</div>';
            
            // Poll for completion (every 2 seconds for 30 seconds max)
            const maxAttempts = 15;
            let attempts = 0;
            
            const pollForCompletion = async () => {
                if (attempts >= maxAttempts) {
                    // Remove loading indicator after timeout
                    messagesContainer.removeChild(loadingMessage);
                    appendMessage('system', 'Summarization is taking longer than expected. Check back later for results.');
                    return;
                }
                
                attempts++;
                
                try {
                    // Check if conversation has been updated with summary
                    const statusResponse = await fetch(`/api/v1/chat/conversations/${currentConversationId}`);
                    
                    if (statusResponse.ok) {
                        const conversationData = await statusResponse.json();
                        
                        if (conversationData.summary) {
                            // Success! Remove loading indicator
                            messagesContainer.removeChild(loadingMessage);
                            
                            // Display summary
                            appendMessage('system', `Conversation has been summarized: ${conversationData.summary}`);
                            
                            // Update title if it was changed
                            if (conversationData.title !== currentConversationTitle.textContent) {
                                currentConversationTitle.textContent = conversationData.title;
                                // Refresh conversations list
                                init();
                            }
                            return;
                        }
                    }
                    
                    // Not ready yet, continue polling
                    setTimeout(pollForCompletion, 2000);
                    
                } catch (error) {
                    console.error('Error checking summarization status:', error);
                    // Continue polling despite error
                    setTimeout(pollForCompletion, 2000);
                }
            };
            
            // Start polling
            setTimeout(pollForCompletion, 2000);
            
        } catch (error) {
            console.error('Error summarizing conversation:', error);
            appendMessage('system', 'Error: Could not connect to the server. Please check your connection.');
        }
    }
}); 