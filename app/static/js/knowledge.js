document.addEventListener('DOMContentLoaded', function() {
    // Add modal HTML to the body
    const modalHtml = `
        <div id="memory-modal" class="modal">
            <div class="modal-content">
                <span class="close-modal">&times;</span>
                <h2 id="modal-title">Memory Details</h2>
                <div id="modal-content"></div>
            </div>
        </div>
    `;
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // Modal handling logic
    const modal = document.getElementById('memory-modal');
    const closeModal = document.querySelector('.close-modal');
    
    closeModal.onclick = function() {
        modal.style.display = "none";
    }
    
    window.onclick = function(event) {
        if (event.target == modal) {
            modal.style.display = "none";
        }
    }
    
    // Tab switching
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            // Remove active class from all buttons and contents
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));
            
            // Add active class to clicked button and corresponding content
            button.classList.add('active');
            const tabId = `${button.dataset.tab}-tab`;
            document.getElementById(tabId).classList.add('active');
            
            // Load content for the active tab
            loadTabContent(button.dataset.tab);
        });
    });
    
    // Load memories content by default
    loadTabContent('memories');
    
    // Set up search button event listeners
    document.getElementById('memory-search-btn').addEventListener('click', () => {
        const query = document.getElementById('memory-search').value.trim();
        loadMemories(1, query);
    });
    
    document.getElementById('entity-search-btn').addEventListener('click', () => {
        const query = document.getElementById('entity-search').value.trim();
        loadEntities(1, query);
    });
    
    document.getElementById('relationship-search-btn').addEventListener('click', () => {
        const query = document.getElementById('relationship-search').value.trim();
        loadRelationships(1, query);
    });
    
    // Set up pagination event listeners
    document.getElementById('prev-memories-page').addEventListener('click', () => {
        const currentPage = parseInt(document.getElementById('memories-page-info').textContent.split(' ')[1]);
        if (currentPage > 1) {
            const query = document.getElementById('memory-search').value.trim();
            loadMemories(currentPage - 1, query);
        }
    });
    
    document.getElementById('next-memories-page').addEventListener('click', () => {
        const currentPage = parseInt(document.getElementById('memories-page-info').textContent.split(' ')[1]);
        const query = document.getElementById('memory-search').value.trim();
        loadMemories(currentPage + 1, query);
    });
    
    document.getElementById('prev-entities-page').addEventListener('click', () => {
        const currentPage = parseInt(document.getElementById('entities-page-info').textContent.split(' ')[1]);
        if (currentPage > 1) {
            const query = document.getElementById('entity-search').value.trim();
            loadEntities(currentPage - 1, query);
        }
    });
    
    document.getElementById('next-entities-page').addEventListener('click', () => {
        const currentPage = parseInt(document.getElementById('entities-page-info').textContent.split(' ')[1]);
        const query = document.getElementById('entity-search').value.trim();
        loadEntities(currentPage + 1, query);
    });
    
    document.getElementById('prev-relationships-page').addEventListener('click', () => {
        const currentPage = parseInt(document.getElementById('relationships-page-info').textContent.split(' ')[1]);
        if (currentPage > 1) {
            const query = document.getElementById('relationship-search').value.trim();
            loadRelationships(currentPage - 1, query);
        }
    });
    
    document.getElementById('next-relationships-page').addEventListener('click', () => {
        const currentPage = parseInt(document.getElementById('relationships-page-info').textContent.split(' ')[1]);
        const query = document.getElementById('relationship-search').value.trim();
        loadRelationships(currentPage + 1, query);
    });
    
    // Add Enter key event listeners for search inputs
    document.getElementById('memory-search').addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            document.getElementById('memory-search-btn').click();
        }
    });
    
    document.getElementById('entity-search').addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            document.getElementById('entity-search-btn').click();
        }
    });
    
    document.getElementById('relationship-search').addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            document.getElementById('relationship-search-btn').click();
        }
    });
    
    // Tab content loading function
    function loadTabContent(tab) {
        switch (tab) {
            case 'memories':
                loadMemories(1);
                break;
            case 'entities':
                loadEntities(1);
                break;
            case 'relationships':
                loadRelationships(1);
                break;
        }
    }
    
    // Load memories function
    async function loadMemories(page = 1, query = '') {
        const container = document.getElementById('memories-container');
        const pageSize = 10;
        
        try {
            container.innerHTML = '<div class="loading">Loading memories...</div>';
            
            // Construct the API URL
            let url = `/api/v1/memory/list?limit=${pageSize}&offset=${(page - 1) * pageSize}`;
            if (query) {
                url += `&query=${encodeURIComponent(query)}`;
            }
            
            const response = await fetch(url);
            
            if (!response.ok) {
                throw new Error(`Failed to load memories: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // Update pagination
            document.getElementById('memories-page-info').textContent = `Page ${page}`;
            document.getElementById('prev-memories-page').disabled = page <= 1;
            document.getElementById('next-memories-page').disabled = data.memories.length < pageSize;
            
            // Clear container
            container.innerHTML = '';
            
            if (data.memories.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <p>No memories found${query ? ' matching "' + query + '"' : ''}.</p>
                    </div>
                `;
                return;
            }
            
            // Render memories
            data.memories.forEach(memory => {
                const memoryCard = document.createElement('div');
                memoryCard.className = 'item-card memory-card';
                
                // Extract memory ID
                const memoryId = memory.memory_id || memory.id || 'unknown';
                
                // Extract memory type
                const memoryType = memory.memory_type || 'unknown';
                
                // Extract content - the actual memory content
                // In Mem0 v2 API, the content is stored in the 'memory' field
                let content = memory.memory || memory.content || (memory.message?.content) || '';
                
                // Extract title from content or ID
                let title = memory.name || '';
                if (!title && content) {
                    // Create a shorter title from content
                    title = content.length > 50 ? content.substring(0, 50) + '...' : content;
                } else if (!title) {
                    title = `Memory ${memoryId.substring(0, 8)}`;
                }
                
                // Format date
                const date = memory.created_at 
                    ? new Date(memory.created_at).toLocaleString() 
                    : memory.timestamp 
                        ? new Date(memory.timestamp).toLocaleString()
                        : 'Unknown date';
                
                // If content is still empty or matches title exactly, try alternative fields
                if (!content || (content === title && title !== `Memory ${memoryId.substring(0, 8)}`)) {
                    content = memory.summary || memory.description || 'No additional content available';
                }
                
                // Extract tags from metadata
                const tags = [];
                let messageId = null;
                let conversationId = null;
                
                // Add memory ID and type as tags
                tags.push({text: `ID: ${memoryId.substring(0, 8)}`, isInteractive: true, type: 'memory', id: memoryId});
                tags.push({text: `${memoryType}`, isInteractive: false});
                
                if (memory.metadata) {
                    // Store IDs for potential modal use
                    messageId = memory.metadata.message_id;
                    conversationId = memory.metadata.conversation_id;
                    
                    // Add chat tag if message_id exists
                    if (messageId) {
                        tags.push({
                            html: `<span class="tag interactive chat" data-type="chat" data-id="${messageId}">chat</span>`,
                            isInteractive: true
                        });
                    }
                    
                    // Add conversation tag
                    if (conversationId) {
                        tags.push({
                            html: `<span class="tag interactive conversation" data-type="conversation" data-id="${conversationId}">Conversation</span>`,
                            isInteractive: true
                        });
                    }
                    
                    if (memory.metadata.source) tags.push({text: memory.metadata.source, isInteractive: false});
                    if (memory.metadata.source_file) tags.push({text: memory.metadata.source_file, isInteractive: false});
                    if (memory.metadata.category) tags.push({text: memory.metadata.category, isInteractive: false});
                    // Add any additional tags
                    if (memory.metadata.tags && Array.isArray(memory.metadata.tags)) {
                        memory.metadata.tags.forEach(tag => tags.push({text: tag, isInteractive: false}));
                    }
                }
                
                // Add any categories as tags
                if (memory.categories && Array.isArray(memory.categories)) {
                    memory.categories.forEach(category => tags.push({text: category, isInteractive: false}));
                }
                
                // If similarity score exists, show it
                if (memory.similarity !== undefined) {
                    const score = Math.round(memory.similarity * 100);
                    tags.push({text: `Match: ${score}%`, isInteractive: false});
                }
                
                // Process tags to HTML
                const tagsHtml = tags.map(tag => {
                    if (tag.isInteractive) {
                        if (tag.html) {
                            return tag.html;
                        } else if (tag.type === 'memory') {
                            return `<span class="tag interactive memory" data-type="memory" data-id="${tag.id}">${tag.text}</span>`;
                        } else {
                            return `<span class="tag interactive" data-type="${tag.type}" data-id="${tag.id}">${tag.text}</span>`;
                        }
                    } else {
                        return `<span class="tag">${tag.text}</span>`;
                    }
                }).join(' ');
                
                // Create the memory card HTML
                memoryCard.innerHTML = `
                    <div class="item-header">
                        <div class="item-title">${title}</div>
                        <div class="item-meta">${date}</div>
                    </div>
                    <div class="item-content">${content || 'No content available'}</div>
                    <div class="item-tags">
                        ${tagsHtml}
                    </div>
                `;
                
                container.appendChild(memoryCard);
            });
            
            // Add event listeners to interactive tags
            document.querySelectorAll('.tag.interactive').forEach(tag => {
                tag.addEventListener('click', async function() {
                    const type = this.dataset.type;
                    const id = this.dataset.id;
                    
                    try {
                        // Show loading state
                        document.getElementById('modal-title').textContent = `Loading ${type} details...`;
                        document.getElementById('modal-content').innerHTML = '<div class="loading">Loading...</div>';
                        modal.style.display = "block";
                        
                        if (type === 'chat') {
                            // Fetch message details
                            const response = await fetch(`/api/v1/chat/messages/${id}`);
                            if (!response.ok) {
                                throw new Error(`Failed to load message: ${response.statusText}`);
                            }
                            
                            const messageData = await response.json();
                            
                            // Display message details
                            document.getElementById('modal-title').textContent = 'Chat Message';
                            document.getElementById('modal-content').innerHTML = `
                                <div class="message-details">
                                    <p><strong>From:</strong> ${messageData.role || 'Unknown'}</p>
                                    <p><strong>Timestamp:</strong> ${new Date(messageData.timestamp).toLocaleString()}</p>
                                    <div class="message-content">
                                        <p>${messageData.content || 'No content available'}</p>
                                    </div>
                                </div>
                            `;
                        } else if (type === 'conversation') {
                            // Fetch conversation
                            const response = await fetch(`/api/v1/chat/conversations/${id}`);
                            if (!response.ok) {
                                throw new Error(`Failed to load conversation: ${response.statusText}`);
                            }
                            
                            const conversationData = await response.json();
                            
                            // Display conversation details
                            document.getElementById('modal-title').textContent = conversationData.title || 'Conversation';
                            
                            let messagesHtml = '';
                            if (conversationData.messages && conversationData.messages.length > 0) {
                                messagesHtml = conversationData.messages.map(msg => `
                                    <div class="conversation-message ${msg.role}">
                                        <div class="message-header">
                                            <span class="message-role">${msg.role}</span>
                                            <span class="message-time">${new Date(msg.timestamp || msg.created_at).toLocaleString()}</span>
                                        </div>
                                        <div class="message-body">${msg.content}</div>
                                    </div>
                                `).join('');
                            } else {
                                messagesHtml = '<p>No messages in this conversation</p>';
                            }
                            
                            document.getElementById('modal-content').innerHTML = `
                                <div class="conversation-details">
                                    <p><strong>Created:</strong> ${new Date(conversationData.created_at).toLocaleString()}</p>
                                    <div class="conversation-messages">
                                        ${messagesHtml}
                                    </div>
                                </div>
                            `;
                        } else if (type === 'memory') {
                            // Fetch memory details using the correct endpoint path
                            const response = await fetch(`/api/v1/memory/memory/${id}`);
                            if (!response.ok) {
                                throw new Error(`Failed to load memory: ${response.statusText}`);
                            }
                            
                            const memoryData = await response.json();
                            
                            // Format date
                            const date = memoryData.created_at 
                                ? new Date(memoryData.created_at).toLocaleString() 
                                : memoryData.timestamp 
                                    ? new Date(memoryData.timestamp).toLocaleString()
                                    : 'Unknown date';
                            
                            // Extract content
                            const content = memoryData.memory || memoryData.content || '';
                            
                            // Process metadata
                            const metadataHtml = memoryData.metadata 
                                ? Object.entries(memoryData.metadata)
                                    .map(([key, value]) => `<tr><td><strong>${key}:</strong></td><td>${JSON.stringify(value)}</td></tr>`)
                                    .join('')
                                : '<tr><td colspan="2">No metadata available</td></tr>';
                            
                            // Display memory details
                            document.getElementById('modal-title').textContent = 'Memory Details';
                            document.getElementById('modal-content').innerHTML = `
                                <div class="memory-details">
                                    <p><strong>ID:</strong> ${memoryData.memory_id || memoryData.id}</p>
                                    <p><strong>Type:</strong> ${memoryData.memory_type || 'Unknown'}</p>
                                    <p><strong>Created:</strong> ${date}</p>
                                    <div class="memory-content">
                                        <h3>Content</h3>
                                        <p>${content || 'No content available'}</p>
                                    </div>
                                    <div class="memory-metadata">
                                        <h3>Metadata</h3>
                                        <table class="metadata-table">
                                            ${metadataHtml}
                                        </table>
                                    </div>
                                </div>
                            `;
                        }
                    } catch (error) {
                        console.error(`Error loading ${type} details:`, error);
                        document.getElementById('modal-title').textContent = 'Error';
                        document.getElementById('modal-content').innerHTML = `
                            <div class="error-state">
                                <p>Error loading ${type} details: ${error.message}</p>
                            </div>
                        `;
                    }
                });
            });
            
        } catch (error) {
            console.error('Error loading memories:', error);
            container.innerHTML = `
                <div class="error-state">
                    Error loading memories: ${error.message}
                </div>
            `;
        }
    }
    
    // Load entities function
    async function loadEntities(page = 1, query = '') {
        const container = document.getElementById('entities-container');
        const pageSize = 10;
        
        try {
            container.innerHTML = '<div class="loading">Loading entities...</div>';
            
            // Construct the API URL
            let url = `/api/v1/graph/nodes?limit=${pageSize}&offset=${(page - 1) * pageSize}`;
            if (query) {
                url += `&query=${encodeURIComponent(query)}`;
            }
            
            const response = await fetch(url);
            
            if (!response.ok) {
                throw new Error(`Failed to load entities: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // Update pagination
            document.getElementById('entities-page-info').textContent = `Page ${page}`;
            document.getElementById('prev-entities-page').disabled = page <= 1;
            document.getElementById('next-entities-page').disabled = data.nodes.length < pageSize;
            
            // Clear container
            container.innerHTML = '';
            
            if (data.nodes.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <p>No entities found${query ? ' matching "' + query + '"' : ''}.</p>
                    </div>
                `;
                return;
            }
            
            // Render entities
            data.nodes.forEach(entity => {
                const entityCard = document.createElement('div');
                entityCard.className = 'item-card entity-card';
                
                // Create the entity card HTML
                entityCard.innerHTML = `
                    <div class="item-header">
                        <div class="item-title">${entity.name || 'Unnamed entity'}</div>
                        <div class="item-meta">${entity.labels ? entity.labels.join(', ') : 'No labels'}</div>
                    </div>
                    <div class="item-content">${entity.summary || 'No summary available'}</div>
                    <div class="item-tags">
                        ${entity.properties ? Object.entries(entity.properties)
                            .filter(([key, value]) => key !== 'name' && key !== 'summary')
                            .map(([key, value]) => `<span class="tag">${key}: ${value}</span>`)
                            .join('') : ''}
                    </div>
                `;
                
                container.appendChild(entityCard);
            });
            
        } catch (error) {
            console.error('Error loading entities:', error);
            container.innerHTML = `
                <div class="error-state">
                    Error loading entities: ${error.message}
                </div>
            `;
        }
    }
    
    // Load relationships function
    async function loadRelationships(page = 1, query = '') {
        const container = document.getElementById('relationships-container');
        const pageSize = 10;
        
        try {
            container.innerHTML = '<div class="loading">Loading relationships...</div>';
            
            // Construct the API URL
            let url = `/api/v1/graph/relationships?limit=${pageSize}&offset=${(page - 1) * pageSize}`;
            if (query) {
                url += `&query=${encodeURIComponent(query)}`;
            }
            
            const response = await fetch(url);
            
            if (!response.ok) {
                throw new Error(`Failed to load relationships: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // Update pagination
            document.getElementById('relationships-page-info').textContent = `Page ${page}`;
            document.getElementById('prev-relationships-page').disabled = page <= 1;
            document.getElementById('next-relationships-page').disabled = data.relationships.length < pageSize;
            
            // Clear container
            container.innerHTML = '';
            
            if (data.relationships.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <p>No relationships found${query ? ' matching "' + query + '"' : ''}.</p>
                    </div>
                `;
                return;
            }
            
            // Render relationships
            data.relationships.forEach(rel => {
                const relCard = document.createElement('div');
                relCard.className = 'item-card relationship-card';
                
                // Create the relationship card HTML
                relCard.innerHTML = `
                    <div class="item-header">
                        <div class="item-title">${rel.type || 'Unknown relationship'}</div>
                        <div class="item-meta">ID: ${rel.id ? rel.id.substring(0, 8) : 'N/A'}</div>
                    </div>
                    <div class="item-content">
                        <strong>From:</strong> ${rel.source_node?.name || 'Unknown'} 
                        <strong>To:</strong> ${rel.target_node?.name || 'Unknown'}
                    </div>
                    <div class="item-tags">
                        ${rel.properties ? Object.entries(rel.properties)
                            .map(([key, value]) => `<span class="tag">${key}: ${value}</span>`)
                            .join('') : ''}
                    </div>
                `;
                
                container.appendChild(relCard);
            });
            
        } catch (error) {
            console.error('Error loading relationships:', error);
            container.innerHTML = `
                <div class="error-state">
                    Error loading relationships: ${error.message}
                </div>
            `;
        }
    }
}); 