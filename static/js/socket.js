/**
 * Socket.IO connection management and event handling
 */

let socket;

/**
 * Initialize Socket.IO connection
 */
function initializeSocketConnection() {
    // Connect to Socket.IO server
    socket = io();
    
    // Connection event handlers
    socket.on('connect', () => {
        console.log('Socket.IO connected');
        updateStatus('Connected to real-time updates', 'success');
    });
    
    socket.on('disconnect', () => {
        console.log('Socket.IO disconnected');
        updateStatus('Disconnected from real-time updates', 'error');
    });
    
    socket.on('connect_error', (error) => {
        console.error('Socket.IO connection error:', error);
        updateStatus('Connection error', 'error');
    });
    
    // Data event handlers
    socket.on('metrics_update', handleMetricsUpdate);
    socket.on('retrieval_metrics', handleRetrievalUpdate);
}

/**
 * Handle metrics updates from the server
 */
function handleMetricsUpdate(data) {
    console.log('Received metrics update:', data);
    
    // Update the metrics display in the system info panel
    const docsProcessed = document.getElementById('docsProcessed');
    const chunksCount = document.getElementById('chunksCount');
    const processRate = document.getElementById('processRate');
    const vectorDims = document.getElementById('vectorDims');
    const llmRequests = document.getElementById('llmRequests');
    const lastUpdate = document.getElementById('lastUpdate');
    
    // Get modal elements
    const modalDocsProcessed = document.getElementById('modalDocsProcessed');
    const modalProcessingRate = document.getElementById('modalProcessingRate');
    
    // Update document counts
    if (docsProcessed) {
        docsProcessed.textContent = data.documents_processed || 0;
    }
    
    if (chunksCount) {
        chunksCount.textContent = data.document_count || 0;
    }
    
    // Update processing metrics
    if (processRate) {
        const rate = data.processing_rate || 0;
        processRate.textContent = `${rate.toFixed(2)} docs/sec`;
    }
    
    // Update vector store info
    if (vectorDims) {
        vectorDims.textContent = data.vector_dimensions || 0;
    }
    
    // Update LLM info if we have it
    if (llmRequests && data.llm_stats) {
        llmRequests.textContent = data.llm_stats.total_requests || 0;
    }
    
    // Update last update time
    if (lastUpdate) {
        const date = new Date();
        lastUpdate.textContent = date.toLocaleTimeString();
    }
    
    // Update recent documents list if present
    updateRecentDocuments(data.recent_documents);
    
    // Update modal metrics if they exist
    if (modalDocsProcessed) {
        modalDocsProcessed.textContent = data.documents_processed || 0;
    }
    
    if (modalProcessingRate) {
        const rate = data.processing_rate || 0;
        modalProcessingRate.textContent = `${rate.toFixed(2)} docs/sec`;
    }
}

/**
 * Handle retrieval metrics updates
 */
function handleRetrievalUpdate(data) {
    // This data is used to update visualizations in real-time
    // when streaming mode is enabled
    if (document.getElementById('streamingToggle').checked) {
        updateRetrievalVisualization(data.context, data);
    }
}

/**
 * Update the list of recently processed documents if present
 */
function updateRecentDocuments(documents) {
    const recentDocsList = document.getElementById('recentDocsList');
    if (!recentDocsList || !documents || !Array.isArray(documents)) {
        return;
    }
    
    // Clear the current list
    recentDocsList.innerHTML = '';
    
    if (documents.length === 0) {
        recentDocsList.innerHTML = '<li class="list-group-item text-muted">No documents processed yet</li>';
        return;
    }
    
    // Add each document to the list
    documents.forEach(doc => {
        const docItem = document.createElement('li');
        docItem.className = 'list-group-item d-flex justify-content-between align-items-center';
        
        // Format timestamp
        const docTime = new Date(doc.timestamp * 1000).toLocaleTimeString();
        
        docItem.innerHTML = `
            <span>${escapeHtml(doc.title)}</span>
            <span class="badge bg-secondary rounded-pill">${docTime}</span>
        `;
        
        recentDocsList.appendChild(docItem);
    });
}

/**
 * Disconnect Socket.IO when the page is unloaded
 */
window.addEventListener('beforeunload', () => {
    if (socket) {
        socket.disconnect();
    }
});
