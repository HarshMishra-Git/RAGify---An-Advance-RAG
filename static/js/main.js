/**
 * Main application JavaScript
 */

// Global state
const appState = {
    isProcessing: false,
    lastQuery: null,
    uploadedDocuments: []
};

/**
 * Set up all event listeners for the application
 */
function setupEventListeners() {
    // Query form submission
    const queryForm = document.getElementById('queryForm');
    queryForm.addEventListener('submit', handleQuerySubmit);
    
    // Document upload form
    const uploadForm = document.getElementById('documentUploadForm');
    uploadForm.addEventListener('submit', handleDocumentUpload);
    
    // Initialize tooltips
    const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltips.forEach(tooltip => {
        new bootstrap.Tooltip(tooltip);
    });
}

/**
 * Handle query form submission
 */
async function handleQuerySubmit(event) {
    event.preventDefault();
    
    const queryInput = document.getElementById('queryInput');
    const query = queryInput.value.trim();
    
    if (!query) {
        showAlert('Please enter a query', 'warning');
        return;
    }
    
    // Update UI to show processing state
    setProcessingState(true);
    updateStatus('Processing query...', 'working');
    
    try {
        // Send query to backend
        const response = await fetch('/api/query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ query })
        });
        
        if (!response.ok) {
            throw new Error(`Error: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        // Update appState
        appState.lastQuery = query;
        
        // Display retrieved context
        displayRetrievedContext(data.context);
        
        // Display generated response
        displayGeneratedResponse(data.response);
        
        // Display metrics
        displayMetrics(data.metrics);
        
        // Update visualizations
        updateRetrievalVisualization(data.context, data.metrics);
        
        // Update status
        updateStatus('Query processed successfully', 'success');
    } catch (error) {
        console.error('Error processing query:', error);
        updateStatus(`Error: ${error.message}`, 'error');
        displayGeneratedResponse('An error occurred while processing your query. Please try again.');
    } finally {
        // Reset processing state
        setProcessingState(false);
    }
}

/**
 * Handle document upload
 */
async function handleDocumentUpload(event) {
    event.preventDefault();
    
    const fileInput = document.getElementById('documentFile');
    const file = fileInput.files[0];
    
    if (!file) {
        showAlert('Please select a file to upload', 'warning');
        return;
    }
    
    // Create FormData
    const formData = new FormData();
    formData.append('file', file);
    
    // Update UI
    const uploadStatus = document.getElementById('uploadStatus');
    uploadStatus.innerHTML = `<div class="alert alert-info">Uploading ${file.name}...</div>`;
    
    try {
        // Send file to backend
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`Error: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        // Update UI with success message
        uploadStatus.innerHTML = `<div class="alert alert-success">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="feather feather-check-circle me-1">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                <polyline points="22 4 12 14.01 9 11.01"></polyline>
            </svg>
            ${file.name} uploaded successfully and is being processed.
        </div>`;
        
        // Add to uploaded documents list
        appState.uploadedDocuments.push({
            name: file.name,
            timestamp: new Date()
        });
        
        // Reset file input
        fileInput.value = '';
    } catch (error) {
        console.error('Error uploading document:', error);
        uploadStatus.innerHTML = `<div class="alert alert-danger">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="feather feather-alert-circle me-1">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
            Error uploading ${file.name}: ${error.message}
        </div>`;
    }
}

/**
 * Display retrieved context in the UI
 */
function displayRetrievedContext(context) {
    const contextContainer = document.getElementById('retrievedContext');
    
    if (!context || context.length === 0) {
        contextContainer.innerHTML = `
            <div class="empty-state text-center py-5">
                <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#CCCCCC" stroke-width="1" stroke-linecap="round" stroke-linejoin="round" class="feather feather-search">
                    <circle cx="11" cy="11" r="8"></circle>
                    <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                </svg>
                <p class="mt-3 text-muted">No relevant context found</p>
            </div>
        `;
        return;
    }
    
    let html = '';
    
    context.forEach((doc, index) => {
        // Truncate text if it's too long
        let displayText = doc.text;
        if (displayText.length > 300) {
            displayText = displayText.substring(0, 300) + '...';
        }
        
        html += `
            <div class="context-item">
                <div class="context-item-header">
                    <span>Document ${index + 1}</span>
                    <span class="context-score">Score: ${(1 - (index * 0.15)).toFixed(2)}</span>
                </div>
                <div class="context-item-content">${escapeHtml(displayText)}</div>
            </div>
        `;
    });
    
    contextContainer.innerHTML = html;
}

/**
 * Display generated response in the UI
 */
function displayGeneratedResponse(response) {
    const responseContainer = document.getElementById('generatedResponse');
    
    if (!response) {
        responseContainer.innerHTML = `
            <div class="empty-state text-center py-5">
                <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#CCCCCC" stroke-width="1" stroke-linecap="round" stroke-linejoin="round" class="feather feather-message-square">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                </svg>
                <p class="mt-3 text-muted">No response generated</p>
            </div>
        `;
        return;
    }
    
    responseContainer.innerHTML = `<div>${escapeHtml(response).replace(/\n/g, '<br>')}</div>`;
}

/**
 * Display metrics in the UI
 */
function displayMetrics(metrics) {
    if (!metrics) return;
    
    const retrievalMetricsEl = document.getElementById('retrievalMetrics');
    const responseMetricsEl = document.getElementById('responseMetrics');
    
    // Format retrieval metrics
    retrievalMetricsEl.innerHTML = `
        <div class="metrics-container">
            <div class="metric-item">
                <span>Retrieval time:</span> 
                <span class="value">${metrics.retrieval_time.toFixed(2)}s</span>
            </div>
            <div class="metric-item">
                <span>Chunks:</span> 
                <span class="value">${metrics.context_chunks}</span>
            </div>
        </div>
    `;
    
    // Format response metrics
    let llmMetricsHtml = '';
    let isMockResponse = false;
    
    if (metrics.llm_metrics) {
        const llmMetrics = metrics.llm_metrics;
        isMockResponse = llmMetrics.is_mock;
        
        llmMetricsHtml = `
            <div class="metrics-container mt-2">
                <div class="metric-item">
                    <span>Generation time:</span> 
                    <span class="value">${llmMetrics.latency ? llmMetrics.latency.toFixed(2) : '0.00'}s</span>
                </div>
                ${llmMetrics.tokens_generated ? 
                  `<div class="metric-item">
                      <span>Tokens:</span> 
                      <span class="value">${llmMetrics.tokens_generated}</span>
                  </div>` : 
                  (llmMetrics.tokens ? 
                  `<div class="metric-item">
                      <span>Tokens (est.):</span> 
                      <span class="value">${llmMetrics.tokens}</span>
                  </div>` : '')}
                ${isMockResponse ? 
                  `<div class="metric-item">
                      <span>Mode:</span> 
                      <span class="value text-warning">Mock response (no API key)</span>
                  </div>` : 
                  `<div class="metric-item">
                      <span>Model:</span> 
                      <span class="value">${llmMetrics.model || 'Mixtral-8x7B'}</span>
                  </div>`}
            </div>
        `;
    }
    
    responseMetricsEl.innerHTML = `
        <div class="metrics-container">
            <div class="metric-item">
                <span>Total time:</span> 
                <span class="value">${metrics.total_time.toFixed(2)}s</span>
            </div>
        </div>
        ${llmMetricsHtml}
    `;
    
    // Add retrieved document IDs if available
    if (metrics.retrieved_documents && metrics.retrieved_documents.length > 0) {
        retrievalMetricsEl.innerHTML += `
            <div class="mt-2 small">
                <div><strong>Source documents:</strong></div>
                <div class="text-muted">${metrics.retrieved_documents.join(', ')}</div>
            </div>
        `;
    }
}

/**
 * Update status indicator
 */
function updateStatus(message, status = 'default') {
    const statusDot = document.querySelector('.status-dot');
    const statusText = document.getElementById('statusText');
    
    // Remove all status classes
    statusDot.classList.remove('inactive', 'error', 'working');
    
    // Add appropriate class
    switch (status) {
        case 'error':
            statusDot.classList.add('error');
            break;
        case 'working':
            statusDot.classList.add('working');
            break;
        case 'success':
            // Success has default color
            break;
        default:
            statusDot.classList.add('inactive');
    }
    
    // Update text
    statusText.textContent = message;
}

/**
 * Set the processing state of the application
 */
function setProcessingState(isProcessing) {
    appState.isProcessing = isProcessing;
    
    const submitButton = document.getElementById('submitQuery');
    const loadingOverlay = document.getElementById('loadingOverlay');
    
    if (isProcessing) {
        submitButton.disabled = true;
        submitButton.innerHTML = `
            <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
            Processing...
        `;
        loadingOverlay.classList.remove('d-none');
    } else {
        submitButton.disabled = false;
        submitButton.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="feather feather-search me-1">
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
            Submit Query
        `;
        loadingOverlay.classList.add('d-none');
    }
}

/**
 * Show an alert message
 */
function showAlert(message, type = 'info') {
    const alertHtml = `
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;
    
    // Add alert to the top of the query form
    const queryForm = document.getElementById('queryForm');
    queryForm.insertAdjacentHTML('beforebegin', alertHtml);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(alert => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
