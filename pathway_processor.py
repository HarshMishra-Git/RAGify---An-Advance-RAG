import logging
import threading
import time
import numpy as np
import hashlib
from vector_store import VectorStore

logger = logging.getLogger(__name__)

class PathwayProcessor:
    def __init__(self, vector_store):
        self.vector_store = vector_store
        self.documents_queue = []
        self.processed_count = 0
        self.processing_lock = threading.Lock()
        self.is_running = False
        self.recently_processed_docs = []
        self.processor_thread = None
        
    def get_processed_count(self):
        """Returns the count of processed documents."""
        return self.processed_count
    
    def get_recent_documents(self):
        """Returns a list of recently processed documents."""
        with self.processing_lock:
            return self.recently_processed_docs.copy()
        
    def add_document(self, content, doc_id):
        """Add a document to the processing queue."""
        with self.processing_lock:
            # Generate a unique document ID if one isn't provided
            if not doc_id:
                doc_id = f"doc_{int(time.time())}_{len(self.documents_queue)}"
                
            self.documents_queue.append({"content": content, "id": doc_id})
            logger.info(f"Document {doc_id} added to queue")
            
            # Start processing thread if not running
            if not self.is_running or self.processor_thread is None or not self.processor_thread.is_alive():
                self.start_processing()
            
            return doc_id
            
    def start_processing(self):
        """Start the Pathway data processing pipeline."""
        if self.is_running and self.processor_thread and self.processor_thread.is_alive():
            logger.debug("Processing thread already running")
            return
            
        self.is_running = True
        self.processor_thread = threading.Thread(target=self._processing_worker)
        self.processor_thread.daemon = True
        self.processor_thread.start()
        logger.info("Started document processing thread")
        
    def _processing_worker(self):
        """Worker thread for document processing."""
        logger.info("Document processing worker started")
        
        while self.is_running:
            documents_to_process = []
            
            # Get documents from queue
            with self.processing_lock:
                if self.documents_queue:
                    # Process up to 5 documents at a time
                    documents_to_process = self.documents_queue[:5]
                    self.documents_queue = self.documents_queue[5:]
            
            if documents_to_process:
                logger.info(f"Processing batch of {len(documents_to_process)} documents")
                batch_successful = 0
                
                for doc in documents_to_process:
                    try:
                        # Process the document
                        processed = self._process_document(doc["content"], doc["id"])
                        if processed:
                            batch_successful += 1
                            
                            # Add to recent documents
                            with self.processing_lock:
                                # Keep only the 10 most recent documents
                                self.recently_processed_docs = ([
                                    {
                                        "id": doc["id"],
                                        "title": doc["id"],
                                        "timestamp": time.time()
                                    }
                                ] + self.recently_processed_docs)[:10]
                    except Exception as e:
                        logger.error(f"Error processing document {doc['id']}: {str(e)}")
                
                # Update processed count
                with self.processing_lock:
                    self.processed_count += batch_successful
                    
                logger.info(f"Successfully processed {batch_successful}/{len(documents_to_process)} documents, total: {self.processed_count}")
            
            # Sleep before checking for more documents
            time.sleep(0.5)
        
        logger.info("Document processing worker stopped")
    
    def _process_document(self, content, doc_id):
        """Process a single document."""
        # Skip empty documents
        if not content or not content.strip():
            logger.warning(f"Skipping empty document {doc_id}")
            return False
            
        # Split document into chunks
        chunks = self._chunk_document(content)
        if not chunks:
            logger.warning(f"No chunks generated for document {doc_id}")
            return False
        
        logger.info(f"Processing document {doc_id} into {len(chunks)} chunks")
            
        # Process each chunk
        chunk_ids = []
        successful_chunks = 0
        for i, chunk in enumerate(chunks):
            try:
                # Create embedding for chunk
                embedding = self._create_embedding(chunk)
                
                # Add to vector store with a unique ID
                chunk_id = f"{doc_id}_chunk_{i}"
                doc_key = self.vector_store.add_document(chunk_id, chunk, embedding)
                chunk_ids.append(doc_key)
                successful_chunks += 1
            except Exception as e:
                logger.error(f"Error processing chunk {i} of document {doc_id}: {str(e)}")
                
        # Only count as successful if we processed at least one chunk
        if successful_chunks > 0:
            logger.info(f"Successfully added {successful_chunks}/{len(chunks)} chunks for document {doc_id}")
            return True
        else:
            logger.warning(f"Failed to process any chunks for document {doc_id}")
            return False
    
    def _chunk_document(self, text, chunk_size=1000, overlap=200):
        """Split document into chunks."""
        # Skip empty documents
        if not text or not text.strip():
            return []
            
        # Handle short documents without chunking
        if len(text) < chunk_size:
            return [text]
            
        chunks = []
        for i in range(0, len(text), chunk_size - overlap):
            chunk = text[i:i + chunk_size]
            # Skip empty chunks
            if chunk and chunk.strip():
                chunks.append(chunk)
                
        return chunks
    
    def _create_embedding(self, text):
        """Create an embedding for a text chunk."""
        # This would use a real embedding model in production
        # For demonstration purposes, we create a deterministic hash-based embedding
        
        # Create a deterministic embedding based on content hash
        hash_bytes = hashlib.md5(text.encode()).digest()
        # Create a vector of 16 dimensions from the hash
        embedding = np.array([float(byte) / 255.0 for byte in hash_bytes])
        # Normalize the embedding vector (important for meaningful cosine similarity)
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
            
        return embedding.tolist()  # Convert to list
    
    def stop_processing(self):
        """Stop the Pathway data processing pipeline."""
        logger.info("Stopping document processing")
        self.is_running = False
        # Wait for the thread to terminate
        if self.processor_thread and self.processor_thread.is_alive():
            self.processor_thread.join(timeout=2.0)
        logger.info("Document processing stopped")
