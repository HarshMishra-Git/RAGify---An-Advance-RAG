/**
 * D3.js visualizations for the RAG application
 */

// Global visualization objects
let retrievalViz;

/**
 * Initialize all visualizations
 */
function initializeVisualizations() {
    initRetrievalVisualization();
}

/**
 * Initialize the retrieval visualization
 */
function initRetrievalVisualization() {
    const container = d3.select('#retrievalVisualization');
    const width = container.node().getBoundingClientRect().width;
    const height = container.node().getBoundingClientRect().height;
    
    // Create SVG
    const svg = container.append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `0 0 ${width} ${height}`)
        .attr('class', 'retrieval-viz-svg');
    
    // Add title
    svg.append('text')
        .attr('x', width / 2)
        .attr('y', 20)
        .attr('text-anchor', 'middle')
        .attr('class', 'viz-title')
        .style('font-size', '14px')
        .style('font-weight', '500')
        .text('Semantic Similarity');
    
    // Create a group for the visualization elements
    const vizGroup = svg.append('g')
        .attr('transform', `translate(${width/2}, ${height/2})`);
    
    // Store the visualization objects for later updates
    retrievalViz = {
        svg: svg,
        vizGroup: vizGroup,
        width: width,
        height: height
    };
}

/**
 * Update the retrieval visualization with new data
 */
function updateRetrievalVisualization(context, metrics) {
    if (!retrievalViz || !context) return;
    
    const { svg, vizGroup, width, height } = retrievalViz;
    
    // Clear previous visualization
    vizGroup.selectAll('*').remove();
    
    // Get distances from metrics if available
    let distances = [];
    if (metrics && metrics.distances) {
        distances = metrics.distances;
    } else {
        // Generate mock distances if real ones aren't available
        distances = context.map((_, i) => 1 - (i * 0.15));
    }
    
    // Center node (query)
    vizGroup.append('circle')
        .attr('cx', 0)
        .attr('cy', 0)
        .attr('r', 25)
        .attr('fill', '#0066CC')
        .attr('stroke', '#FFFFFF')
        .attr('stroke-width', 2);
    
    vizGroup.append('text')
        .attr('x', 0)
        .attr('y', 5)
        .attr('text-anchor', 'middle')
        .attr('fill', '#FFFFFF')
        .attr('font-size', '12px')
        .text('Query');
    
    // Determine positions for context nodes in a circle around the query
    const nodeRadius = 20;
    const orbitRadius = Math.min(width, height) / 2 - nodeRadius - 30;
    
    // Create context nodes
    context.forEach((doc, i) => {
        const angle = (i / context.length) * 2 * Math.PI;
        const x = Math.cos(angle) * orbitRadius;
        const y = Math.sin(angle) * orbitRadius;
        
        // Calculate color based on distance (similarity)
        // Convert distance to a value between 0 and 1 (assuming distances are normalized)
        const distance = distances[i] || 0;
        const normalizedDistance = Math.max(0, Math.min(1, distance));
        
        // Interpolate color from red (low similarity) to green (high similarity)
        const colorScale = d3.scaleLinear()
            .domain([0, 1])
            .range(['#FF9500', '#34C759']);
        
        const color = colorScale(1 - normalizedDistance);
        
        // Draw line from query to context
        vizGroup.append('line')
            .attr('x1', 0)
            .attr('y1', 0)
            .attr('x2', x)
            .attr('y2', y)
            .attr('stroke', color)
            .attr('stroke-width', 2 + (1 - normalizedDistance) * 3)
            .attr('opacity', 0.6);
        
        // Draw context node
        vizGroup.append('circle')
            .attr('cx', x)
            .attr('cy', y)
            .attr('r', nodeRadius)
            .attr('fill', color)
            .attr('stroke', '#FFFFFF')
            .attr('stroke-width', 2);
        
        // Add context number
        vizGroup.append('text')
            .attr('x', x)
            .attr('y', y + 5)
            .attr('text-anchor', 'middle')
            .attr('fill', '#FFFFFF')
            .attr('font-size', '12px')
            .text(i + 1);
        
        // Add distance label
        vizGroup.append('text')
            .attr('x', (x + 0) / 2)
            .attr('y', (y + 0) / 2)
            .attr('text-anchor', 'middle')
            .attr('fill', '#333333')
            .attr('font-size', '10px')
            .attr('font-weight', 'bold')
            .attr('background', '#FFFFFF')
            .text(normalizedDistance.toFixed(2));
    });
}

/**
 * Handle window resize events
 */
window.addEventListener('resize', () => {
    // Reinitialize visualizations on resize
    const container = d3.select('#retrievalVisualization');
    retrievalViz.width = container.node().getBoundingClientRect().width;
    retrievalViz.height = container.node().getBoundingClientRect().height;
    
    // Update SVG dimensions
    retrievalViz.svg
        .attr('width', retrievalViz.width)
        .attr('height', retrievalViz.height)
        .attr('viewBox', `0 0 ${retrievalViz.width} ${retrievalViz.height}`);
    
    // Reposition visualization group
    retrievalViz.vizGroup
        .attr('transform', `translate(${retrievalViz.width/2}, ${retrievalViz.height/2})`);
});
