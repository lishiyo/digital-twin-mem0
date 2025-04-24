// DOM Elements
const tabButtons = document.querySelectorAll('.tab-button');
const tabContents = document.querySelectorAll('.tab-content');
const clearProfileButton = document.getElementById('clear-profile');

// Stats elements
const skillsCountEl = document.getElementById('skills-count').querySelector('.count');
const interestsCountEl = document.getElementById('interests-count').querySelector('.count');
const preferencesCountEl = document.getElementById('preferences-count').querySelector('.count');
const dislikesCountEl = document.getElementById('dislikes-count').querySelector('.count');
const attributesCountEl = document.getElementById('attributes-count').querySelector('.count');

// Content containers
const skillsContainer = document.getElementById('skills-container');
const interestsContainer = document.getElementById('interests-container');
const preferencesContainer = document.getElementById('preferences-container');
const dislikesContainer = document.getElementById('dislikes-container');
const attributesContainer = document.getElementById('attributes-container');

// API Endpoints
const API_PROFILE = '/api/v1/profile';
const API_CLEAR_PROFILE = '/api/v1/profile/clear';
const API_DELETE_TRAIT = '/api/v1/profile/trait';

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupTabs();
    loadProfileData();
    setupClearButton();
});

/**
 * Set up tab switching functionality
 */
function setupTabs() {
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            // Remove active class from all buttons and contents
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));
            
            // Add active class to clicked button and corresponding content
            button.classList.add('active');
            const tabName = button.getAttribute('data-tab');
            document.getElementById(`${tabName}-tab`).classList.add('active');
        });
    });
}

/**
 * Load profile data from API
 */
async function loadProfileData() {
    try {
        // Show loading state
        document.querySelectorAll('.items-container').forEach(container => {
            container.innerHTML = '<div class="loading-state">Loading...</div>';
        });
        
        const response = await fetch(API_PROFILE);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Profile API error:', response.status, errorText);
            throw new Error(`Failed to load profile data: ${response.status} ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (data.status === 'success' && data.profile) {
            renderProfileData(data.profile);
        } else {
            showError(`Failed to load profile data: ${data.message || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error loading profile data:', error);
        document.querySelectorAll('.items-container').forEach(container => {
            container.innerHTML = '<div class="error-state">Error loading profile data. Please try refreshing the page.</div>';
        });
        showError('Error loading profile data: ' + error.message);
    }
}

/**
 * Render profile data to the page
 */
function renderProfileData(profile) {
    // Ensure all profile data structures exist
    profile = profile || {};
    profile.stats = profile.stats || {};
    profile.skills = profile.skills || [];
    profile.interests = profile.interests || [];
    profile.preferences = profile.preferences || {};
    profile.dislikes = profile.dislikes || [];
    profile.attributes = profile.attributes || [];
    
    // Update stats
    skillsCountEl.textContent = profile.stats.skills_count || 0;
    interestsCountEl.textContent = profile.stats.interests_count || 0;
    preferencesCountEl.textContent = profile.stats.preferences_count || 0;
    dislikesCountEl.textContent = profile.stats.dislikes_count || 0;
    attributesCountEl.textContent = profile.stats.attributes_count || 0;
    
    // Render skills
    renderTraitList(skillsContainer, profile.skills, 'skill');
    
    // Render interests
    renderTraitList(interestsContainer, profile.interests, 'interest');
    
    // Render preferences
    renderPreferences(preferencesContainer, profile.preferences);
    
    // Render dislikes
    renderTraitList(dislikesContainer, profile.dislikes, 'dislike');
    
    // Render attributes
    renderTraitList(attributesContainer, profile.attributes, 'attribute');
}

/**
 * Render a list of traits to a container
 */
function renderTraitList(container, items, type) {
    container.innerHTML = '';
    
    if (!items || items.length === 0) {
        container.innerHTML = `<div class="empty-state">No ${type}s found</div>`;
        return;
    }
    
    items.forEach(item => {
        if (!item || typeof item !== 'object') return;
        
        const confidence = parseFloat(item.confidence) || 0;
        const evidence = item.evidence || '';
        const name = item.name || 'Unnamed';
        
        const itemEl = document.createElement('div');
        itemEl.className = 'item-card';
        
        itemEl.innerHTML = `
            <button class="delete-trait-btn" data-type="${type}s" data-name="${escapeHtml(name)}" title="Delete ${escapeHtml(name)}">×</button>
            <div class="item-name">${escapeHtml(name)}</div>
            <div class="item-meta">
                ${type === 'skill' ? `Proficiency: ${Math.round((parseFloat(item.proficiency) || 0) * 100)}%` : ''}
                ${type === 'skill' ? '<br>' : ''}
                Confidence: ${Math.round(confidence * 100)}%
            </div>
            <div class="confidence">
                <div class="confidence-bar" style="width: ${confidence * 100}%"></div>
            </div>
            ${evidence ? `<div class="evidence">"${escapeHtml(evidence)}"</div>` : ''}
        `;
        
        // Add event listener to delete button
        const deleteBtn = itemEl.querySelector('.delete-trait-btn');
        deleteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            deleteTrait(type + 's', name);
        });
        
        container.appendChild(itemEl);
    });
}

/**
 * Render preferences to a container
 */
function renderPreferences(container, preferences) {
    container.innerHTML = '';
    
    if (!preferences || Object.keys(preferences).length === 0) {
        container.innerHTML = '<div class="empty-state">No preferences found</div>';
        return;
    }
    
    for (const category in preferences) {
        const categoryPrefs = preferences[category];
        
        // Skip empty categories
        if (!categoryPrefs || Object.keys(categoryPrefs).length === 0) {
            continue;
        }
        
        const categoryHeader = document.createElement('h3');
        categoryHeader.textContent = formatCategory(category);
        categoryHeader.style.marginBottom = '1rem';
        categoryHeader.style.marginTop = '1rem';
        container.appendChild(categoryHeader);
        
        const categoryContainer = document.createElement('div');
        categoryContainer.className = 'items-container';
        
        for (const prefName in categoryPrefs) {
            const pref = categoryPrefs[prefName];
            
            if (typeof pref !== 'object') continue;
            
            const confidence = parseFloat(pref.confidence) || 0;
            const evidence = pref.evidence || '';
            
            const itemEl = document.createElement('div');
            itemEl.className = 'item-card';
            
            itemEl.innerHTML = `
                <button class="delete-trait-btn" data-type="preferences" data-name="${escapeHtml(category)}.${escapeHtml(prefName)}" title="Delete ${escapeHtml(prefName)}">×</button>
                <div class="item-name">${escapeHtml(prefName)}</div>
                <div class="item-meta">
                    Confidence: ${Math.round(confidence * 100)}%
                </div>
                <div class="confidence">
                    <div class="confidence-bar" style="width: ${confidence * 100}%"></div>
                </div>
                ${evidence ? `<div class="evidence">"${escapeHtml(evidence)}"</div>` : ''}
            `;
            
            // Add event listener to delete button
            const deleteBtn = itemEl.querySelector('.delete-trait-btn');
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                deleteTrait('preferences', `${category}.${prefName}`);
            });
            
            categoryContainer.appendChild(itemEl);
        }
        
        container.appendChild(categoryContainer);
    }
}

/**
 * Format category name for display
 */
function formatCategory(category) {
    if (!category) return 'General';
    return category.charAt(0).toUpperCase() + category.slice(1).replace(/_/g, ' ');
}

/**
 * Set up clear profile button
 */
function setupClearButton() {
    clearProfileButton.addEventListener('click', async () => {
        if (!confirm('Are you sure you want to clear your profile? This action cannot be undone.')) {
            return;
        }
        
        try {
            clearProfileButton.disabled = true;
            clearProfileButton.textContent = 'Clearing...';
            
            const response = await fetch(API_CLEAR_PROFILE, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Failed to clear profile: ${response.status} ${response.statusText} - ${errorText}`);
            }
            
            const data = await response.json();
            
            if (data.status === 'success') {
                alert('Profile cleared successfully');
                loadProfileData(); // Reload profile data
            } else {
                showError(data.message || 'Failed to clear profile');
            }
        } catch (error) {
            console.error('Error clearing profile:', error);
            showError('Error clearing profile: ' + error.message);
        } finally {
            clearProfileButton.disabled = false;
            clearProfileButton.textContent = 'Clear Profile';
        }
    });
}

/**
 * Show error message
 */
function showError(message) {
    console.error(message);
    alert(`Error: ${message}`);
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(unsafe) {
    if (typeof unsafe !== 'string') return '';
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

/**
 * Delete a trait
 */
async function deleteTrait(traitType, traitName) {
    if (!confirm(`Are you sure you want to delete '${traitName}'?`)) {
        return;
    }
    
    try {
        // Encode the trait name to handle special characters in the URL
        const encodedTraitName = encodeURIComponent(traitName);
        
        const response = await fetch(`${API_DELETE_TRAIT}/${traitType}/${encodedTraitName}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Failed to delete trait: ${response.status} ${response.statusText} - ${errorText}`);
        }
        
        const data = await response.json();
        
        if (data.status === 'success') {
            // Reload profile data to reflect changes
            loadProfileData();
        } else {
            showError(data.message || 'Failed to delete trait');
        }
    } catch (error) {
        console.error('Error deleting trait:', error);
        showError('Error deleting trait: ' + error.message);
    }
} 