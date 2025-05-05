"""
Embedding service for InfiniteMemoryMCP.

This module handles the generation of text embeddings for semantic search.
It encapsulates the embedding model and provides methods for generating
and working with embeddings.
"""

import os
import queue
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple, Union

import numpy as np

from ..utils.config import config_manager
from ..utils.logging import logger

# Try to import sentence-transformers, but have a fallback if not available
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    logger.warning("sentence-transformers not available. Using dummy embedding model.")
    SENTENCE_TRANSFORMERS_AVAILABLE = False


class EmbeddingService:
    """
    Service for generating and working with embeddings.
    
    This class encapsulates the embedding model and provides methods for
    generating embeddings from text and computing similarity.
    """
    
    def __init__(self):
        """Initialize the embedding service."""
        self.model = None
        self.embedding_size = 384  # Default size for all-MiniLM-L6-v2
        self.model_name = config_manager.get(
            "embedding.model_name",
            "all-MiniLM-L6-v2"
        )
        self.use_gpu = config_manager.get("embedding.use_gpu", False)
        self.initialized = False
        
        # Async processing
        self.async_enabled = config_manager.get("embedding.async_enabled", True)
        self.embedding_queue = queue.Queue()
        self.cache_size = config_manager.get("embedding.cache_size", 1000)
        self.embedding_cache: Dict[str, List[float]] = {}  # Simple LRU cache
        self.worker_thread = None
        self.running = False
        self.embedding_callbacks: Dict[str, List[Tuple[Callable, List, Dict]]] = {}
        self.lock = threading.RLock()
        self._is_test_environment = False  # Flag to detect test environment
    
    def initialize(self) -> bool:
        """
        Initialize the embedding model.
        
        Returns:
            True if initialization succeeded, False otherwise
        """
        if self.initialized:
            return True
        
        # Skip real model initialization if in test environment
        if self._is_test_environment:
            logger.info("Test environment detected, using dummy embedding model")
            self.initialized = True
            return True
        
        try:
            if not SENTENCE_TRANSFORMERS_AVAILABLE:
                logger.warning("Using dummy embedding model - semantic search will be limited")
                self.initialized = True
                return True
            
            # Determine the device
            device = "cpu"  # Default to CPU
            if self.use_gpu:
                try:
                    import torch
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                except ImportError:
                    logger.warning("PyTorch not available, using CPU for embeddings")
            
            # Get the model_path from config or use the model_name
            model_path = config_manager.get("embedding.model_path", None)
            model_source = model_path if model_path else self.model_name
            
            # Initialize the model
            logger.info(f"Loading embedding model: {model_source} on {device}")
            self.model = SentenceTransformer(model_source, device=device)
            
            # Only update embedding size if it hasn't been manually set (e.g., in tests)
            if self.embedding_size == 384:  # Only update if it's the default value
                self.embedding_size = self.model.get_sentence_embedding_dimension()
            
            logger.info(f"Embedding model loaded successfully. "
                      f"Embedding size: {self.embedding_size}")
            
            # Start the worker thread if async is enabled
            if self.async_enabled:
                self.start_worker()
            
            self.initialized = True
            return True
        
        except Exception as e:
            logger.error(f"Failed to initialize embedding model: {e}")
            # Fall back to dummy model
            self.initialized = True
            return False
    
    def start_worker(self) -> None:
        """Start the background worker thread for async embedding generation."""
        if self.worker_thread and self.worker_thread.is_alive():
            logger.warning("Worker thread already running")
            return
        
        self.running = True
        self.worker_thread = threading.Thread(target=self._embedding_worker)
        self.worker_thread.daemon = True
        self.worker_thread.start()
        logger.info("Started background embedding worker thread")
    
    def stop_worker(self) -> None:
        """Stop the background worker thread."""
        if not self.worker_thread or not self.worker_thread.is_alive():
            logger.warning("Worker thread not running")
            return
        
        logger.info("Stopping background embedding worker thread")
        self.running = False
        
        # Wait for the worker to finish, but with timeout
        self.worker_thread.join(timeout=2.0)
        if self.worker_thread.is_alive():
            logger.warning("Worker thread did not stop cleanly - work may be lost")
        
        self.worker_thread = None
    
    def _embedding_worker(self) -> None:
        """
        Background worker that processes queued embedding requests.
        
        This runs in a separate thread and processes embedding requests
        from the queue.
        """
        logger.info("Embedding worker thread started")
        
        while self.running:
            try:
                # Get an item from the queue, wait for up to 0.1 seconds
                try:
                    item = self.embedding_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                text, request_id = item
                
                # Generate the embedding
                try:
                    embedding = self._generate_embedding_internal(text)
                    
                    # Add to cache
                    with self.lock:
                        # If cache is full, remove the oldest item
                        if len(self.embedding_cache) >= self.cache_size:
                            # Remove the first item (oldest in the ordered dict)
                            oldest_key = next(iter(self.embedding_cache))
                            self.embedding_cache.pop(oldest_key)
                        self.embedding_cache[text] = embedding
                    
                    # Call any registered callbacks for this request
                    with self.lock:
                        callbacks = self.embedding_callbacks.pop(request_id, [])
                    
                    for callback, args, kwargs in callbacks:
                        try:
                            callback(embedding, *args, **kwargs)
                        except Exception as e:
                            logger.error(f"Error in embedding callback: {e}")
                
                except Exception as e:
                    logger.error(f"Error generating embedding: {e}")
                    # Get any callbacks and call with zero vector
                    with self.lock:
                        callbacks = self.embedding_callbacks.pop(request_id, [])
                    
                    for callback, args, kwargs in callbacks:
                        try:
                            callback([0.0] * self.embedding_size, *args, **kwargs)
                        except Exception as cb_err:
                            logger.error(f"Error in embedding error callback: {cb_err}")
                
                # Mark the task as done
                self.embedding_queue.task_done()
            
            except Exception as e:
                logger.exception(f"Error in embedding worker: {e}")
        
        logger.info("Embedding worker thread stopped")
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate an embedding for the given text.
        
        This is a synchronous version that blocks until the embedding is generated.
        
        Args:
            text: The text to generate an embedding for
            
        Returns:
            A list of floats representing the embedding
        """
        if not self.initialized:
            self.initialize()
        
        if not text:
            logger.warning("Empty text provided for embedding")
            return [0.0] * self.embedding_size
        
        # Check cache first (with lock to avoid race conditions)
        with self.lock:
            if text in self.embedding_cache:
                # Move to most recently used position (simple LRU)
                embedding = self.embedding_cache.pop(text)
                self.embedding_cache[text] = embedding
                return embedding
        
        try:
            # Generate the embedding
            embedding = self._generate_embedding_internal(text)
            
            # Add to cache
            with self.lock:
                # If cache is full, remove the oldest item
                if len(self.embedding_cache) >= self.cache_size:
                    # Remove the first item (oldest in the ordered dict)
                    oldest_key = next(iter(self.embedding_cache))
                    self.embedding_cache.pop(oldest_key)
                self.embedding_cache[text] = embedding
            
            return embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return [0.0] * self.embedding_size
    
    def generate_embedding_async(self, text: str, callback: Callable, *args, **kwargs) -> None:
        """
        Generate an embedding asynchronously.
        
        This method queues the embedding generation and returns immediately.
        When the embedding is ready, the callback will be called with the
        embedding as the first argument, followed by any additional args and kwargs.
        
        Args:
            text: The text to generate an embedding for
            callback: Function to call when embedding is ready
            *args: Additional positional arguments to pass to callback
            **kwargs: Additional keyword arguments to pass to callback
        """
        if not self.initialized:
            self.initialize()
        
        if not text:
            logger.warning("Empty text provided for async embedding")
            # Call the callback immediately with a zero vector
            callback([0.0] * self.embedding_size, *args, **kwargs)
            return
        
        # Check cache first
        with self.lock:
            if text in self.embedding_cache:
                # Move to most recently used position (simple LRU)
                embedding = self.embedding_cache.pop(text)
                self.embedding_cache[text] = embedding
                # Call the callback immediately
                callback(embedding, *args, **kwargs)
                return
        
        # If async is disabled or worker not running, do it synchronously
        if not self.async_enabled or not self.running:
            try:
                embedding = self._generate_embedding_internal(text)
                
                # Add to cache
                with self.lock:
                    # If cache is full, remove the oldest item
                    if len(self.embedding_cache) >= self.cache_size:
                        # Remove the first item (oldest in the ordered dict)
                        oldest_key = next(iter(self.embedding_cache))
                        self.embedding_cache.pop(oldest_key)
                    self.embedding_cache[text] = embedding
                
                callback(embedding, *args, **kwargs)
            except Exception as e:
                logger.error(f"Error in sync embedding generation: {e}")
                callback([0.0] * self.embedding_size, *args, **kwargs)
            return
        
        # Queue the embedding request
        request_id = f"{text}_{time.time()}"
        
        with self.lock:
            # Register the callback
            if request_id not in self.embedding_callbacks:
                self.embedding_callbacks[request_id] = []
            self.embedding_callbacks[request_id].append((callback, args, kwargs))
        
        # Queue the text for embedding
        self.embedding_queue.put((text, request_id))
    
    def _generate_embedding_internal(self, text: str) -> List[float]:
        """
        Internal method that does the actual embedding generation.
        
        Args:
            text: The text to generate an embedding for
            
        Returns:
            A list of floats representing the embedding
        """
        try:
            if self.model:
                # Use the real embedding model
                embedding = self.model.encode(text)
                result = embedding.tolist()
            else:
                # Use a dummy embedding (random but deterministic based on text hash)
                text_hash = hash(text) % 10000
                np.random.seed(text_hash)
                dummy_embedding = np.random.randn(self.embedding_size).astype(np.float32)
                # Normalize to unit length
                dummy_embedding = dummy_embedding / np.linalg.norm(dummy_embedding)
                result = dummy_embedding.tolist()
            
            # Cache handling is done in the calling method to ensure consistency
            return result
        
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            # Propagate the exception to allow proper error handling in tests
            raise
    
    def compute_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Compute the cosine similarity between two embeddings.
        
        Args:
            embedding1: The first embedding
            embedding2: The second embedding
            
        Returns:
            A float between -1 and 1 representing the cosine similarity
        """
        # Convert to numpy arrays
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        # Compute cosine similarity
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return np.dot(vec1, vec2) / (norm1 * norm2)
    
    def compute_similarities(self, query_embedding: List[float], 
                           candidate_embeddings: List[List[float]]) -> List[float]:
        """
        Compute cosine similarities between one query embedding and multiple candidate embeddings.
        
        Args:
            query_embedding: The query embedding
            candidate_embeddings: A list of candidate embeddings
            
        Returns:
            A list of similarity scores (same length as candidate_embeddings)
        """
        similarities = []
        for candidate in candidate_embeddings:
            similarity = self.compute_similarity(query_embedding, candidate)
            similarities.append(similarity)
        
        return similarities
    
    def find_most_similar(self, query_embedding: List[float],
                        candidate_embeddings: List[List[float]],
                        top_k: int = 5,
                        threshold: float = 0.0) -> List[int]:
        """
        Find the indices of the most similar embeddings.
        
        Args:
            query_embedding: The query embedding
            candidate_embeddings: A list of candidate embeddings
            top_k: Maximum number of results to return
            threshold: Minimum similarity score to include
            
        Returns:
            A list of indices of the most similar embeddings
        """
        if not candidate_embeddings:
            return []
        
        # Compute similarities
        similarities = self.compute_similarities(query_embedding, candidate_embeddings)
        
        # Create (index, similarity) pairs
        indexed_similarities = list(enumerate(similarities))
        
        # Filter by threshold
        filtered_similarities = [(idx, sim) for idx, sim in indexed_similarities if sim >= threshold]
        
        # Sort by similarity (descending)
        sorted_similarities = sorted(filtered_similarities, key=lambda x: x[1], reverse=True)
        
        # Get top_k indices
        top_indices = [idx for idx, _ in sorted_similarities[:top_k]]
        
        return top_indices


# Create a singleton instance
embedding_service = EmbeddingService() 