"""
Tests for the memory MCP commands.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from src.infinite_memory_mcp.mcp.commands import (handle_delete_memory,
                                                 handle_get_memory_stats,
                                                 handle_retrieve_memory,
                                                 handle_search_by_scope,
                                                 handle_search_by_tag,
                                                 handle_store_memory)


class TestMemoryCommands(unittest.TestCase):
    """Test cases for the memory MCP commands."""
    
    def setUp(self):
        """Set up the test case."""
        self.mock_memory_service = MagicMock()
        
        # Create patcher for memory_service
        self.memory_service_patcher = patch(
            'src.infinite_memory_mcp.mcp.commands.memory_service',
            self.mock_memory_service
        )
        self.memory_service_patcher.start()
    
    def tearDown(self):
        """Clean up after the test."""
        self.memory_service_patcher.stop()
    
    def test_store_memory_command(self):
        """Test the store_memory command."""
        # Setup mock service
        expected_response = {
            "status": "OK",
            "memory_id": "mock_id",
            "scope": "TestScope"
        }
        self.mock_memory_service.store_memory.return_value = expected_response
        
        # Create request
        request = {
            "action": "store_memory",
            "content": "Test memory content",
            "metadata": {
                "scope": "TestScope",
                "tags": ["test", "memory"],
                "source": "test",
                "conversation_id": "test_convo",
                "speaker": "user"
            }
        }
        
        # Execute command
        response = handle_store_memory(request)
        
        # Verify service was called correctly
        self.mock_memory_service.store_memory.assert_called_once_with(
            content="Test memory content",
            scope="TestScope",
            tags=["test", "memory"],
            source="test",
            conversation_id="test_convo",
            speaker="user"
        )
        
        # Verify response
        self.assertEqual(response, expected_response)
    
    def test_store_memory_missing_content(self):
        """Test the store_memory command with missing content."""
        # Create request without content
        request = {
            "action": "store_memory",
            "metadata": {
                "scope": "TestScope"
            }
        }
        
        # Execute command
        response = handle_store_memory(request)
        
        # Verify service was not called
        self.mock_memory_service.store_memory.assert_not_called()
        
        # Verify error response
        self.assertEqual(response["status"], "error")
        self.assertIn("Missing required 'content' field", response["error"])
    
    def test_retrieve_memory_command(self):
        """Test the retrieve_memory command."""
        # Setup mock service
        expected_response = {
            "status": "OK",
            "results": [
                {
                    "text": "Test memory",
                    "source": "conversation",
                    "timestamp": "2023-01-01T00:00:00",
                    "scope": "TestScope",
                    "tags": ["test"],
                    "confidence": 1.0,
                    "memory_id": "mock_id"
                }
            ]
        }
        self.mock_memory_service.retrieve_memory.return_value = expected_response
        
        # Create request
        request = {
            "action": "retrieve_memory",
            "query": "test memory",
            "filter": {
                "scope": "TestScope",
                "tags": ["test"],
                "time_range": {"from": "2023-01-01", "to": "2023-01-02"}
            },
            "top_k": 3
        }
        
        # Execute command
        response = handle_retrieve_memory(request)
        
        # Verify service was called correctly
        self.mock_memory_service.retrieve_memory.assert_called_once_with(
            query="test memory",
            scope="TestScope",
            tags=["test"],
            time_range={"from": "2023-01-01", "to": "2023-01-02"},
            top_k=3
        )
        
        # Verify response
        self.assertEqual(response, expected_response)
    
    def test_retrieve_memory_missing_query(self):
        """Test the retrieve_memory command with missing query."""
        # Create request without query
        request = {
            "action": "retrieve_memory",
            "filter": {
                "scope": "TestScope"
            }
        }
        
        # Execute command
        response = handle_retrieve_memory(request)
        
        # Verify service was not called
        self.mock_memory_service.retrieve_memory.assert_not_called()
        
        # Verify error response
        self.assertEqual(response["status"], "error")
        self.assertIn("Missing required 'query' field", response["error"])
    
    def test_search_by_tag_command(self):
        """Test the search_by_tag command."""
        # Setup mock service
        expected_response = {
            "status": "OK",
            "results": [
                {
                    "text": "Tagged memory",
                    "source": "conversation",
                    "timestamp": "2023-01-01T00:00:00",
                    "scope": "TestScope",
                    "tags": ["important"],
                    "confidence": 1.0,
                    "memory_id": "mock_id"
                }
            ]
        }
        self.mock_memory_service.search_by_tag.return_value = expected_response
        
        # Create request
        request = {
            "action": "search_by_tag",
            "tag": "important",
            "query": "meeting"
        }
        
        # Execute command
        response = handle_search_by_tag(request)
        
        # Verify service was called correctly
        self.mock_memory_service.search_by_tag.assert_called_once_with(
            tag="important",
            query="meeting"
        )
        
        # Verify response
        self.assertEqual(response, expected_response)
    
    def test_search_by_scope_command(self):
        """Test the search_by_scope command."""
        # Setup mock service
        expected_response = {
            "status": "OK",
            "results": [
                {
                    "text": "Scoped memory",
                    "source": "conversation",
                    "timestamp": "2023-01-01T00:00:00",
                    "scope": "ProjectAlpha",
                    "tags": [],
                    "confidence": 1.0,
                    "memory_id": "mock_id"
                }
            ]
        }
        self.mock_memory_service.search_by_scope.return_value = expected_response
        
        # Create request
        request = {
            "action": "search_by_scope",
            "scope": "ProjectAlpha",
            "query": "meeting"
        }
        
        # Execute command
        response = handle_search_by_scope(request)
        
        # Verify service was called correctly
        self.mock_memory_service.search_by_scope.assert_called_once_with(
            scope="ProjectAlpha",
            query="meeting"
        )
        
        # Verify response
        self.assertEqual(response, expected_response)
    
    def test_delete_memory_command(self):
        """Test the delete_memory command."""
        # Setup mock service
        expected_response = {
            "status": "OK",
            "deleted_count": 1,
            "scope": None,
            "note": "Deleted 1 memories"
        }
        self.mock_memory_service.delete_memory.return_value = expected_response
        
        # Create request
        request = {
            "action": "delete_memory",
            "target": {
                "memory_id": "mock_id"
            },
            "forget_mode": "soft"
        }
        
        # Execute command
        response = handle_delete_memory(request)
        
        # Verify service was called correctly
        self.mock_memory_service.delete_memory.assert_called_once_with(
            memory_id="mock_id",
            scope=None,
            tag=None,
            query=None,
            forget_mode="soft"
        )
        
        # Verify response
        self.assertEqual(response, expected_response)
    
    def test_delete_memory_missing_criteria(self):
        """Test the delete_memory command with missing criteria."""
        # Create request without criteria
        request = {
            "action": "delete_memory",
            "target": {},
            "forget_mode": "soft"
        }
        
        # Execute command
        response = handle_delete_memory(request)
        
        # Verify service was not called
        self.mock_memory_service.delete_memory.assert_not_called()
        
        # Verify error response
        self.assertEqual(response["status"], "error")
        self.assertIn("At least one deletion criterion is required", response["error"])
    
    def test_get_memory_stats_command(self):
        """Test the get_memory_stats command."""
        # Setup mock service
        expected_stats = {
            "total_memories": 10,
            "conversation_count": 2,
            "scopes": {"Global": 5, "TestScope": 5},
            "last_backup": None,
            "db_size_mb": 1.5
        }
        self.mock_memory_service.get_memory_stats.return_value = expected_stats
        
        # Create request
        request = {
            "action": "get_memory_stats"
        }
        
        # Execute command
        response = handle_get_memory_stats(request)
        
        # Verify service was called correctly
        self.mock_memory_service.get_memory_stats.assert_called_once()
        
        # Verify response
        self.assertEqual(response["status"], "OK")
        self.assertEqual(response["stats"], expected_stats)


if __name__ == "__main__":
    unittest.main() 