document.addEventListener('DOMContentLoaded', function() {
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
                if (memory.metadata) {
                    if (memory.metadata.source) tags.push(memory.metadata.source);
                    if (memory.metadata.conversation_id) tags.push('Conversation');
                    if (memory.metadata.source_file) tags.push(memory.metadata.source_file);
                    if (memory.metadata.category) tags.push(memory.metadata.category);
                    // Add any additional tags
                    if (memory.metadata.tags && Array.isArray(memory.metadata.tags)) {
                        memory.metadata.tags.forEach(tag => tags.push(tag));
                    }
                }
                
                // Add any categories as tags
                if (memory.categories && Array.isArray(memory.categories)) {
                    memory.categories.forEach(category => tags.push(category));
                }
                
                // If similarity score exists, show it
                if (memory.similarity !== undefined) {
                    const score = Math.round(memory.similarity * 100);
                    tags.push(`Match: ${score}%`);
                }
                
                // Create the memory card HTML
                memoryCard.innerHTML = `
                    <div class="item-header">
                        <div class="item-title">${title}</div>
                        <div class="item-meta">${date}</div>
                    </div>
                    <div class="item-content">${content || 'No content available'}</div>
                    <div class="item-tags">
                        ${tags.map(tag => `<span class="tag">${tag}</span>`).join('')}
                    </div>
                `;
                
                container.appendChild(memoryCard);
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