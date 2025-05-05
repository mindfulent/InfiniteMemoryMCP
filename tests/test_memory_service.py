"""
Tests for the memory service.
"""

import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.infinite_memory_mcp.core.memory_service import MemoryService
from src.infinite_memory_mcp.core.memory_repository import memory_repository
from src.infinite_memory_mcp.core.models import ConversationMemory, MemoryScope


class TestMemoryService(unittest.TestCase):
    """Test cases for the memory service."""
    
    def setUp(self):
        """Set up the test case."""
        # Create a patch for the memory_repository in memory_service module
        self.repo_patcher = patch('src.infinite_memory_mcp.core.memory_service.memory_repository')
        # Start the patcher and get the mock object
        self.mock_repo = self.repo_patcher.start()
        
        # Create a patch for config_manager
        self.config_patcher = patch('src.infinite_memory_mcp.core.memory_service.config_manager')
        # Start the patcher and get the mock object
        self.mock_config = self.config_patcher.start()
        
        # Set up mock config behavior
        self.mock_config.get.side_effect = self._mock_config_get
        
        # Create the service with our mocks
        self.service = MemoryService()
    
    def tearDown(self):
        """Clean up after the test."""
        # Stop all patchers
        self.repo_patcher.stop()
        self.config_patcher.stop()
    
    def _mock_config_get(self, key, default=None):
        """Mock config_manager.get."""
        config = {
            "memory.default_scope": "Global",
            "memory.auto_create_scope": True
        }
        return config.get(key, default)
    
    def test_store_memory(self):
        """Test storing a memory."""
        # Setup mock repository
        mock_memory_id = "mock_memory_id"
        self.mock_repo.store_conversation_memory.return_value = mock_memory_id
        
        # Call the service
        result = self.service.store_memory(
            content="Test memory content",
            scope="TestScope",
            tags=["test", "memory"],
            source="test",
            conversation_id="test_conversation",
            speaker="user"
        )
        
        # Verify the repository was called correctly
        self.mock_repo.store_conversation_memory.assert_called_once()
        args, kwargs = self.mock_repo.store_conversation_memory.call_args
        memory = args[0]
        self.assertEqual(memory.text, "Test memory content")
        self.assertEqual(memory.scope, "TestScope")
        self.assertEqual(memory.tags, ["test", "memory"])
        self.assertEqual(memory.conversation_id, "test_conversation")
        self.assertEqual(memory.speaker, "user")
        
        # Verify the result
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["memory_id"], mock_memory_id)
        self.assertEqual(result["scope"], "TestScope")
    
    def test_store_memory_auto_create_scope(self):
        """Test storing a memory with auto-creating scope."""
        # Setup mock repository
        mock_memory_id = "mock_memory_id"
        mock_scope_id = "mock_scope_id"
        self.mock_repo.store_conversation_memory.return_value = mock_memory_id
        self.mock_repo.get_scope.return_value = None
        self.mock_repo.create_scope.return_value = mock_scope_id
        
        # Call the service
        result = self.service.store_memory(
            content="Test memory content",
            scope="NewScope",
            tags=["test"],
            source="test"
        )
        
        # Verify the scope was checked and created
        self.mock_repo.get_scope.assert_called_once_with("NewScope")
        self.mock_repo.create_scope.assert_called_once()
        self.assertEqual(self.mock_repo.create_scope.call_args[0][0].scope_name, "NewScope")
        
        # Verify the memory was stored
        self.mock_repo.store_conversation_memory.assert_called_once()
        
        # Verify the result
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["memory_id"], mock_memory_id)
        self.assertEqual(result["scope"], "NewScope")
    
    def test_retrieve_memory(self):
        """Test retrieving memories by query."""
        # Setup mock repository
        mock_memories = [
            ConversationMemory(
                id="memory1",
                text="This is a test memory",
                scope="TestScope",
                tags=["test"],
                timestamp=datetime.now(),
                conversation_id="test_convo",
                speaker="user"
            ),
            ConversationMemory(
                id="memory2",
                text="Another test memory",
                scope="TestScope",
                tags=["test", "another"],
                timestamp=datetime.now(),
                conversation_id="test_convo",
                speaker="assistant"
            )
        ]
        self.mock_repo.get_conversations_by_text_search.return_value = mock_memories
        
        # Call the service
        result = self.service.retrieve_memory(
            query="test memory",
            scope="TestScope",
            tags=["test"],
            top_k=2
        )
        
        # Verify the repository was called correctly
        self.mock_repo.get_conversations_by_text_search.assert_called_once_with("test memory", "TestScope")
        
        # Verify the result
        self.assertEqual(result["status"], "OK")
        self.assertEqual(len(result["results"]), 2)
        self.assertEqual(result["results"][0]["text"], "This is a test memory")
        self.assertEqual(result["results"][0]["memory_id"], "memory1")
        self.assertEqual(result["results"][1]["text"], "Another test memory")
        self.assertEqual(result["results"][1]["memory_id"], "memory2")
    
    def test_retrieve_memory_with_time_range(self):
        """Test retrieving memories with time range filter."""
        # Setup mock repository
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        
        mock_memories = [
            ConversationMemory(
                id="memory1",
                text="This is a test memory",
                scope="TestScope",
                tags=["test"],
                timestamp=now,
                conversation_id="test_convo",
                speaker="user"
            ),
            ConversationMemory(
                id="memory2",
                text="Another test memory",
                scope="TestScope",
                tags=["test", "another"],
                timestamp=yesterday,
                conversation_id="test_convo",
                speaker="assistant"
            )
        ]
        self.mock_repo.get_conversations_by_text_search.return_value = mock_memories
        
        # Create time range filter that should only include today's memory
        time_range = {
            "from": (now - timedelta(hours=1)).isoformat(),
            "to": (now + timedelta(hours=1)).isoformat()
        }
        
        # Call the service
        result = self.service.retrieve_memory(
            query="test memory",
            scope="TestScope",
            time_range=time_range
        )
        
        # Verify the repository was called correctly
        self.mock_repo.get_conversations_by_text_search.assert_called_once_with("test memory", "TestScope")
        
        # Verify the result
        self.assertEqual(result["status"], "OK")
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["text"], "This is a test memory")
        self.assertEqual(result["results"][0]["memory_id"], "memory1")
    
    def test_search_by_tag(self):
        """Test searching memories by tag."""
        # Setup mock repository
        mock_memories = [
            ConversationMemory(
                id="memory1",
                text="This is a tagged memory",
                scope="TestScope",
                tags=["important"],
                timestamp=datetime.now(),
                conversation_id="test_convo",
                speaker="user"
            )
        ]
        self.mock_repo.get_conversations_by_tag.return_value = mock_memories
        
        # Call the service
        result = self.service.search_by_tag(tag="important")
        
        # Verify the repository was called correctly
        self.mock_repo.get_conversations_by_tag.assert_called_once_with("important")
        
        # Verify the result
        self.assertEqual(result["status"], "OK")
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["text"], "This is a tagged memory")
        self.assertEqual(result["results"][0]["tags"], ["important"])
    
    def test_delete_memory(self):
        """Test deleting a memory by ID."""
        # Setup mock repository
        self.mock_repo.delete_memory.return_value = True
        
        # Call the service
        result = self.service.delete_memory(memory_id="memory1")
        
        # Verify the repository was called correctly
        self.mock_repo.delete_memory.assert_called_once_with("memory1")
        
        # Verify the result
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["deleted_count"], 1)
    
    def test_get_memory_stats(self):
        """Test getting memory statistics."""
        # Setup mock repository
        mock_stats = {
            "total_memories": 10,
            "conversation_count": 2,
            "scopes": {"Global": 5, "TestScope": 5},
            "last_backup": None,
            "db_size_mb": 1.5
        }
        self.mock_repo.get_memory_stats.return_value = mock_stats
        
        # Call the service
        result = self.service.get_memory_stats()
        
        # Verify the repository was called correctly
        self.mock_repo.get_memory_stats.assert_called_once()
        
        # Verify the result
        self.assertEqual(result, mock_stats)


if __name__ == "__main__":
    unittest.main() 