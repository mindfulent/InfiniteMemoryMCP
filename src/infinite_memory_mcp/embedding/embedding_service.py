"""
Embedding service for InfiniteMemoryMCP.

This module handles the generation of text embeddings for semantic search.
It encapsulates the embedding model and provides methods for generating
and working with embeddings.
"""

import os
from typing import List, Optional, Union

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
    
    def initialize(self) -> bool:
        """
        Initialize the embedding model.
        
        Returns:
            True if initialization succeeded, False otherwise
        """
        if self.initialized:
            return True
        
        try:
            if not SENTENCE_TRANSFORMERS_AVAILABLE:
                logger.warning("Using dummy embedding model - semantic search will be limited")
                self.initialized = True
                return True
            
            # Determine the device
            device = "cuda" if self.use_gpu else "cpu"
            
            # Get the model_path from config or use the model_name
            model_path = config_manager.get("embedding.model_path", None)
            model_source = model_path if model_path else self.model_name
            
            # Initialize the model
            logger.info(f"Loading embedding model: {model_source} on {device}")
            self.model = SentenceTransformer(model_source, device=device)
            
            # Update embedding size based on the model
            self.embedding_size = self.model.get_sentence_embedding_dimension()
            
            logger.info(f"Embedding model loaded successfully. "
                      f"Embedding size: {self.embedding_size}")
            
            self.initialized = True
            return True
        
        except Exception as e:
            logger.error(f"Failed to initialize embedding model: {e}")
            # Fall back to dummy model
            self.initialized = True
            return False
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate an embedding for the given text.
        
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
        
        try:
            if self.model:
                # Use the real embedding model
                embedding = self.model.encode(text)
                return embedding.tolist()
            else:
                # Use a dummy embedding (random but deterministic based on text hash)
                text_hash = hash(text) % 10000
                np.random.seed(text_hash)
                dummy_embedding = np.random.randn(self.embedding_size).astype(np.float32)
                # Normalize to unit length
                dummy_embedding = dummy_embedding / np.linalg.norm(dummy_embedding)
                return dummy_embedding.tolist()
        
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            # Return a zero vector as fallback
            return [0.0] * self.embedding_size
    
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