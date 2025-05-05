"""
Tests for asynchronous embedding functionality.
"""

import time
import unittest
from typing import List
from unittest.mock import MagicMock, patch

from src.infinite_memory_mcp.embedding.embedding_service import EmbeddingService


class TestAsyncEmbedding(unittest.TestCase):
    """Test cases for asynchronous embedding functionality."""
    
    def setUp(self):
        """Set up test cases."""
        self.service = EmbeddingService()
        self.service._is_test_environment = True  # Flag as test environment
        self.service.embedding_size = 4  # Small size for testing
    
    def test_sync_embedding_generation(self):
        """Test synchronous embedding generation."""
        # Mock the internal method to return a known vector
        self.service._generate_embedding_internal = MagicMock(
            return_value=[0.1, 0.2, 0.3, 0.4]
        )
        
        # Generate an embedding
        embedding = self.service.generate_embedding("test text")
        
        # Verify the result
        self.assertEqual(embedding, [0.1, 0.2, 0.3, 0.4])
        self.service._generate_embedding_internal.assert_called_once_with("test text")
    
    def test_async_embedding_generation(self):
        """Test asynchronous embedding generation."""
        # Mock the internal method to return a known vector
        self.service._generate_embedding_internal = MagicMock(
            return_value=[0.1, 0.2, 0.3, 0.4]
        )
        
        # Mock callback
        callback = MagicMock()
        
        # Enable async mode
        self.service.async_enabled = True
        
        # Generate an embedding asynchronously (in non-worker mode for testing)
        self.service.running = False  # Disable worker for direct testing
        self.service.generate_embedding_async("test text", callback, "arg1", arg2="value2")
        
        # Verify the callback was called with correct arguments
        callback.assert_called_once_with([0.1, 0.2, 0.3, 0.4], "arg1", arg2="value2")
    
    def test_embedding_caching(self):
        """Test embedding caching."""
        # Mock the internal method to return a known vector
        self.service._generate_embedding_internal = MagicMock(
            return_value=[0.1, 0.2, 0.3, 0.4]
        )
        
        # Initial call should generate the embedding
        embedding1 = self.service.generate_embedding("cached text")
        self.assertEqual(embedding1, [0.1, 0.2, 0.3, 0.4])
        self.service._generate_embedding_internal.assert_called_once_with("cached text")
        
        # Reset the mock to verify it's not called again
        self.service._generate_embedding_internal.reset_mock()
        
        # Second call should use the cache
        embedding2 = self.service.generate_embedding("cached text")
        self.assertEqual(embedding2, [0.1, 0.2, 0.3, 0.4])
        self.service._generate_embedding_internal.assert_not_called()
    
    def test_async_worker_queue(self):
        """Test the async worker queue processing."""
        # Mock the internal method to return a known vector
        self.service._generate_embedding_internal = MagicMock(
            return_value=[0.1, 0.2, 0.3, 0.4]
        )
        
        # Enable async mode and start worker
        self.service.async_enabled = True
        
        # Mock callback function
        callback_results = []
        def callback(embedding: List[float], *args, **kwargs):
            callback_results.append((embedding, args, kwargs))
        
        # Start the worker thread
        self.service.start_worker()
        
        try:
            # Queue multiple embedding requests
            for i in range(3):
                self.service.generate_embedding_async(
                    f"text{i}", callback, f"arg{i}", kwarg=f"value{i}"
                )
            
            # Wait for all embeddings to be processed
            self.service.embedding_queue.join()
            
            # Give the callbacks time to execute
            time.sleep(0.1)
            
            # Verify all callbacks were executed
            self.assertEqual(len(callback_results), 3)
            
            # Check results
            for i, result in enumerate(callback_results):
                embedding, args, kwargs = result
                self.assertEqual(embedding, [0.1, 0.2, 0.3, 0.4])
                self.assertEqual(args[0], f"arg{i}")
                self.assertEqual(kwargs["kwarg"], f"value{i}")
        
        finally:
            # Always stop the worker
            self.service.stop_worker()
    
    def test_empty_text_handling(self):
        """Test handling of empty text."""
        # Empty text should return a zero vector without calling the internal method
        self.service._generate_embedding_internal = MagicMock()
        
        # Generate embedding for empty text
        embedding = self.service.generate_embedding("")
        
        # Should be a zero vector of the correct size
        self.assertEqual(embedding, [0.0, 0.0, 0.0, 0.0])
        self.service._generate_embedding_internal.assert_not_called()
    
    def test_error_handling(self):
        """Test error handling during embedding generation."""
        # Mock the internal method to raise an exception
        self.service._generate_embedding_internal = MagicMock(
            side_effect=Exception("Test error")
        )
        
        # Should return a zero vector on error and not raise the exception
        embedding = self.service.generate_embedding("error text")
        
        # Should be a zero vector of the correct size
        self.assertEqual(embedding, [0.0, 0.0, 0.0, 0.0])
    
    def test_cache_size_limit(self):
        """Test that the cache size is limited."""
        # Set a small cache size
        self.service.cache_size = 3
        
        # Mock the internal method to generate unique vectors
        def mock_generate(text):
            # Generate a vector based on the text
            return [float(ord(c)) for c in text[:4].ljust(4)]
        
        self.service._generate_embedding_internal = MagicMock(side_effect=mock_generate)
        
        # Fill the cache
        for i in range(5):
            text = f"text{i}"
            self.service.generate_embedding(text)
        
        # Cache should only contain the last 3 items
        self.assertEqual(len(self.service.embedding_cache), 3)
        self.assertIn("text2", self.service.embedding_cache)
        self.assertIn("text3", self.service.embedding_cache)
        self.assertIn("text4", self.service.embedding_cache)
        self.assertNotIn("text0", self.service.embedding_cache)
        self.assertNotIn("text1", self.service.embedding_cache)


if __name__ == "__main__":
    unittest.main() 