import logging
import numpy as np
import threading
import faiss
import time
import hashlib
from collections import defaultdict

logger = logging.getLogger(__name__)

class VectorStore:
    def __init__(self, vector_dim=16):  # Low dim for example, real embeddings would be larger
        self.vector_dim = vector_dim
        self.index = faiss.IndexFlatL2(vector_dim)  # Simple L2 distance index
        self.document_store = {}  # Maps IDs to document text
        self.id_map = {}  # Maps FAISS internal IDs to document IDs
        self.document_metadata = defaultdict(dict)  # Additional document metadata
        self.next_id = 0
        self.lock = threading.Lock()
        self.last_update_time = time.time()
        
        logger.info(f"Initialized VectorStore with dimension {vector_dim}")
        
    def add_document(self, document_id, text, embedding=None):
        """Add a document to the vector store."""
        with self.lock:
            # If embedding is not provided, create an embedding based on text hash
            if embedding is None:
                embedding = self._create_hash_embedding(text)
            else:
                # Ensure embedding has the right size and type
                if len(embedding) != self.vector_dim:
                    logger.warning(f"Resizing embedding from {len(embedding)} to {self.vector_dim} dimensions")
                    # Resize embedding to match index dimension
                    resized_embedding = np.zeros(self.vector_dim, dtype=np.float32)
                    min_dim = min(len(embedding), self.vector_dim)
                    resized_embedding[:min_dim] = embedding[:min_dim]
                    embedding = resized_embedding
                embedding = np.array(embedding).astype(np.float32)
            
            # Reshape to 2D array for FAISS
            embedding = embedding.reshape(1, -1)
            
            # Add to FAISS index
            faiss_id = self.next_id
            self.index.add(embedding)
            
            # Update mappings
            doc_key = f"{document_id}_{faiss_id}"
            self.id_map[faiss_id] = doc_key
            self.document_store[doc_key] = text
            
            # Store metadata
            source_doc = document_id.split('_chunk_')[0] if '_chunk_' in document_id else document_id
            self.document_metadata[doc_key] = {
                "source": source_doc,
                "added_at": time.time(),
                "content_hash": hashlib.md5(text.encode()).hexdigest()[:8]
            }
            
            self.next_id += 1
            self.last_update_time = time.time()
            
            # Log document addition with current count
            doc_count = self.index.ntotal
            logger.info(f"Added document {doc_key} to vector store. Total documents: {doc_count}")
            
            return doc_key
    
    def _create_hash_embedding(self, text):
        """Create a deterministic embedding based on text hash."""
        hash_bytes = hashlib.md5(text.encode()).digest()
        embedding = np.array([float(byte) / 255.0 for byte in hash_bytes]).astype(np.float32)
        
        # Pad or truncate to vector_dim
        if len(embedding) != self.vector_dim:
            result = np.zeros(self.vector_dim, dtype=np.float32)
            min_dim = min(len(embedding), self.vector_dim)
            result[:min_dim] = embedding[:min_dim]
            embedding = result
            
        # Normalize embedding
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
            
        return embedding
    
    def search(self, query_embedding, top_k=5):
        """Search for similar documents by embedding."""
        with self.lock:
            doc_count = self.index.ntotal
            
            if doc_count == 0:
                logger.warning("Search attempted on empty vector store")
                return [], []
            
            logger.info(f"Searching among {doc_count} documents for top {top_k} matches")
                
            # Ensure query embedding has the right format
            if isinstance(query_embedding, list):
                query_embedding = np.array(query_embedding).astype(np.float32)
                
            # Resize if needed
            if len(query_embedding) != self.vector_dim:
                logger.warning(f"Resizing query embedding from {len(query_embedding)} to {self.vector_dim}")
                resized_query = np.zeros(self.vector_dim, dtype=np.float32)
                min_dim = min(len(query_embedding), self.vector_dim)
                resized_query[:min_dim] = query_embedding[:min_dim]
                query_embedding = resized_query
                
            # Reshape to 2D array for FAISS
            query_embedding = query_embedding.reshape(1, -1)
            
            # Perform search
            distances, indices = self.index.search(query_embedding, min(top_k, doc_count))
            
            # Get document texts
            results = []
            for i, idx in enumerate(indices[0]):
                if idx >= 0 and idx in self.id_map:  # -1 indicates not enough results
                    doc_key = self.id_map[idx]
                    text = self.document_store.get(doc_key, "")
                    metadata = self.document_metadata.get(doc_key, {})
                    
                    # Calculate similarity score (convert L2 distance to similarity)
                    similarity = 1.0 / (1.0 + distances[0][i])
                    
                    result = {
                        "id": doc_key,
                        "text": text,
                        "score": similarity,
                        "source": metadata.get("source", "unknown"),
                        "timestamp": metadata.get("added_at", 0)
                    }
                    results.append(result)
                    
                    logger.debug(f"Found match: {doc_key} with score {similarity:.4f}")
            
            return results, distances[0].tolist()
    
    def get_metrics(self):
        """Get metrics about the vector store."""
        with self.lock:
            doc_count = self.index.ntotal
            
            # Count unique sources
            sources = set()
            for doc_key in self.document_store:
                metadata = self.document_metadata.get(doc_key, {})
                source = metadata.get("source", "unknown")
                sources.add(source)
            
            logger.info(f"Vector store metrics: {doc_count} docs, {len(sources)} sources")
                
            return {
                "document_count": doc_count,
                "last_update": self.last_update_time,
                "vector_dimension": self.vector_dim,
                "unique_sources": len(sources),
                "sources": list(sources)
            }
