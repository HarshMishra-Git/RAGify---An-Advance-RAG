import os
import logging
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import threading
import time
import json
import re
import mimetypes

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Import RAG components
from pathway_processor import PathwayProcessor
from vector_store import VectorStore
from llm_integration import TogetherAILLM
from rag_orchestrator import RAGOrchestrator

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Check for Together AI API key
together_api_key = os.environ.get("TOGETHER_API_KEY", "")
if not together_api_key:
    logger.warning("TOGETHER_API_KEY environment variable not set. Using mock LLM responses.")

# Initialize RAG components
vector_store = VectorStore(vector_dim=16)  # Using 16-dim for demonstration
llm = TogetherAILLM()
pathway_processor = PathwayProcessor(vector_store)
rag_orchestrator = RAGOrchestrator(vector_store, llm)

# Global variables for streaming stats
processor_metrics = {
    "documents_processed": 0,
    "document_count": 0,
    "chunks_count": 0,
    "last_update": time.time(),
    "processing_rate": 0,
    "vector_dimensions": vector_store.vector_dim,
    "recent_documents": [],
    "llm_stats": {
        "has_api_key": bool(together_api_key),
        "model": llm.model,
        "total_requests": 0
    }
}

# Start the data processor - it auto-starts when needed
logger.info("RAG components initialized")

# Add custom mime types
mimetypes.add_type('text/markdown', '.md')
mimetypes.add_type('text/csv', '.csv')
mimetypes.add_type('text/plain', '.txt')
mimetypes.add_type('application/json', '.json')

# Socket.IO events
@socketio.on('connect')
def handle_connect():
    logger.info("Client connected")
    # Send initial metrics
    update_metrics_data()
    socketio.emit('metrics_update', processor_metrics)

@socketio.on('disconnect')
def handle_disconnect():
    logger.info("Client disconnected")

# Routes
@app.route('/')
def landing():
    # Serve the landing page
    return render_template('landing.html')

@app.route('/app')
def index():
    # API key is handled in backend, no need to pass status to template
    return render_template('index.html')

@app.route('/api/query', methods=['POST'])
def query():
    try:
        data = request.json
        user_query = data.get('query', '').strip()

        if not user_query:
            return jsonify({"error": "Query cannot be empty"}), 400

        logger.info(f"Processing query: {user_query}")

        # Get retrieved context and generated response from RAG
        context, response, metrics = rag_orchestrator.process_query(user_query)

        # Emit retrieval metrics via SocketIO
        socketio.emit('retrieval_metrics', metrics)

        # Force metrics update
        update_metrics_data()
        socketio.emit('metrics_update', processor_metrics)

        logger.info(f"Query processed with {len(context)} context chunks")

        return jsonify({
            "query": user_query,
            "context": context,
            "response": response,
            "metrics": metrics
        })
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload_document():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400

        # Check file extension
        allowed_extensions = ['.txt', '.md', '.csv', '.json']
        file_ext = os.path.splitext(file.filename)[1].lower()

        if file_ext not in allowed_extensions:
            return jsonify({
                "error": f"Unsupported file type. Supported types: {', '.join(allowed_extensions)}"
            }), 400

        try:
            content = file.read().decode('utf-8')
        except UnicodeDecodeError:
            return jsonify({"error": "File encoding not supported. Please upload UTF-8 encoded text files."}), 400

        if not content.strip():
            return jsonify({"error": "File appears to be empty"}), 400

        # Format content based on file type
        if file_ext == '.json':
            try:
                json_data = json.loads(content)
                # Extract text from common JSON formats
                if isinstance(json_data, dict):
                    if 'text' in json_data:
                        content = json_data['text']
                    elif 'content' in json_data:
                        content = json_data['content']
                    else:
                        # Format the JSON nicely for processing
                        content = json.dumps(json_data, indent=2)
                elif isinstance(json_data, list):
                    # Join list items into text
                    content = '\n\n'.join([str(item) for item in json_data])
            except json.JSONDecodeError:
                return jsonify({"error": "Invalid JSON file format"}), 400

        # Log document information
        logger.info(f"Processing document: {file.filename}, size: {len(content)} bytes")

        # Process the document with Pathway
        doc_id = pathway_processor.add_document(content, file.filename)
        logger.info(f"Document {file.filename} uploaded and queued for processing as {doc_id}")

        # Give pathway processor a moment to start processing 
        time.sleep(1)

        # Force metrics update
        update_metrics_data()
        socketio.emit('metrics_update', processor_metrics)

        # Send success response
        return jsonify({
            "message": "Document uploaded and processing started",
            "document_id": doc_id,
            "content_size": len(content),
            "current_metrics": {
                "docs_processed": processor_metrics["documents_processed"],
                "chunks_count": processor_metrics["chunks_count"]
            }
        })
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/metrics', methods=['GET'])
def get_metrics():
    """Get current system metrics."""
    update_metrics_data()
    return jsonify(processor_metrics)

@app.route('/api/setkey', methods=['POST'])
def set_api_key():
    """Set the Together AI API key."""
    try:
        data = request.json
        api_key = data.get('api_key', '').strip()

        if not api_key:
            return jsonify({"error": "API key cannot be empty"}), 400

        # Set environment variable (temporary, for this session)
        os.environ['TOGETHER_API_KEY'] = api_key

        # Reinitialize LLM with new key
        global llm, together_api_key
        together_api_key = api_key
        llm = TogetherAILLM()  # This will pick up the new environment variable

        # Update orchestrator
        global rag_orchestrator
        rag_orchestrator = RAGOrchestrator(vector_store, llm)

        logger.info("Together AI API key updated")

        return jsonify({"message": "API key updated successfully"})
    except Exception as e:
        logger.error(f"Error setting API key: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

def update_metrics_data():
    """Update the metrics data from various sources."""
    global processor_metrics

    try:
        # Get vector store metrics
        vs_metrics = vector_store.get_metrics()

        # Get processor metrics
        docs_processed = pathway_processor.get_processed_count()
        recent_docs = pathway_processor.get_recent_documents()

        # Log the metrics we're getting
        logger.info(f"Update metrics: processed={docs_processed}, vector_docs={vs_metrics.get('document_count', 0)}")

        # Get LLM metrics
        llm_metrics = llm.get_metrics() if hasattr(llm, 'get_metrics') else {}

        # Calculate processing rate
        current_time = time.time()
        time_diff = current_time - processor_metrics["last_update"]

        if time_diff > 0:
            new_docs = docs_processed - processor_metrics["documents_processed"]
            processing_rate = new_docs / time_diff
        else:
            processing_rate = 0

        # Update metrics
        processor_metrics = {
            "documents_processed": docs_processed,
            "document_count": vs_metrics.get("document_count", 0),
            "chunks_count": vs_metrics.get("document_count", 0),  # Each document is a chunk
            "vector_dimensions": vs_metrics.get("vector_dimension", 16),
            "last_update": current_time,
            "processing_rate": processing_rate,
            "recent_documents": recent_docs,
            "sources": vs_metrics.get("sources", []),
            "unique_sources": vs_metrics.get("unique_sources", 0),
            "llm_stats": {
                "has_api_key": bool(together_api_key),
                "model": llm_metrics.get("model", "unknown"),
                "total_requests": llm_metrics.get("total_requests", 0),
                "successful_requests": llm_metrics.get("successful_requests", 0),
                "failed_requests": llm_metrics.get("failed_requests", 0),
                "total_tokens": llm_metrics.get("total_tokens_generated", 0)
            }
        }

        # Log the updated metrics
        logger.info(f"System metrics updated: documents={processor_metrics['documents_processed']}, " +
                   f"chunks={processor_metrics['chunks_count']}, sources={processor_metrics['unique_sources']}")
    except Exception as e:
        logger.error(f"Error updating metrics: {str(e)}", exc_info=True)

# # Metrics update thread
# def update_metrics_loop():
#     while True:
#         try:
#             update_metrics_data()
#             socketio.emit('metrics_update', processor_metrics)
#         except Exception as e:
#             logger.error(f"Error in metrics thread: {str(e)}")
#         # Update every 2 seconds
#         time.sleep(5)

# Start metrics update thread
# metrics_thread = threading.Thread(target=update_metrics_loop)
# metrics_thread.daemon = True
# metrics_thread.start()
# logger.info("Metrics update thread started")

if __name__ == '__main__':
    socketio.run(app, debug=True)