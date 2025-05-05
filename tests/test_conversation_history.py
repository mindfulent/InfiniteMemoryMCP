"""
Tests for conversation history and summarization functionality.

This module tests the conversation history storage, retrieval, and summarization
features of InfiniteMemoryMCP.
"""

import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from src.infinite_memory_mcp.core.memory_service import memory_service
from src.infinite_memory_mcp.core.models import ConversationMemory, SummaryMemory
from src.infinite_memory_mcp.mcp.commands import (
    handle_create_conversation_summary, handle_get_conversation_history,
    handle_get_conversation_summaries, handle_get_conversations_list,
    handle_store_conversation_history
)


class TestConversationHistory(unittest.TestCase):
    """Tests for conversation history functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a patch for the memory repository
        self.memory_repository_patch = patch('src.infinite_memory_mcp.core.memory_service.memory_repository')
        self.mock_memory_repository = self.memory_repository_patch.start()
        
        # Mock the store_conversation_batch method
        self.mock_memory_repository.store_conversation_batch.return_value = {
            "conversation_id": "test-conversation-id",
            "memory_ids": ["memory-id-1", "memory-id-2"]
        }
        
        # Mock the get_conversation_history method
        test_memories = [
            ConversationMemory(
                id="memory-id-1",
                conversation_id="test-conversation-id",
                speaker="user",
                text="Hello, Claude!",
                timestamp=datetime.now() - timedelta(minutes=10),
                scope="TestScope"
            ),
            ConversationMemory(
                id="memory-id-2",
                conversation_id="test-conversation-id",
                speaker="assistant",
                text="Hello! How can I help you today?",
                timestamp=datetime.now() - timedelta(minutes=9),
                scope="TestScope"
            )
        ]
        self.mock_memory_repository.get_conversation_history.return_value = test_memories
        
        # Mock the get_conversations_list method
        test_conversations = [
            {
                "_id": "test-conversation-id",
                "conversation_id": "test-conversation-id",
                "first_timestamp": datetime.now() - timedelta(minutes=10),
                "last_timestamp": datetime.now() - timedelta(minutes=1),
                "message_count": 5,
                "scope": "TestScope",
                "first_message": {"text": "Hello, Claude!", "speaker": "user"}
            }
        ]
        self.mock_memory_repository.get_conversations_list.return_value = test_conversations
    
    def tearDown(self):
        """Tear down test fixtures."""
        self.memory_repository_patch.stop()
    
    def test_store_conversation_history(self):
        """Test storing a conversation history batch."""
        # Create test request
        request = {
            "messages": [
                {"speaker": "user", "text": "Hello, Claude!"},
                {"speaker": "assistant", "text": "Hello! How can I help you today?"}
            ],
            "metadata": {
                "scope": "TestScope"
            }
        }
        
        # Call the handler
        response = handle_store_conversation_history(request)
        
        # Check the response
        self.assertEqual(response["status"], "OK")
        self.assertEqual(response["conversation_id"], "test-conversation-id")
        self.assertEqual(len(response["memory_ids"]), 2)
        
        # Verify the repository was called correctly
        self.mock_memory_repository.store_conversation_batch.assert_called_once()
        call_args = self.mock_memory_repository.store_conversation_batch.call_args[1]
        self.assertEqual(len(call_args["messages"]), 2)
        self.assertEqual(call_args["scope"], "TestScope")
    
    def test_get_conversation_history(self):
        """Test retrieving conversation history."""
        # Create test request
        request = {
            "conversation_id": "test-conversation-id",
            "limit": 10
        }
        
        # Call the handler
        response = handle_get_conversation_history(request)
        
        # Check the response
        self.assertEqual(response["status"], "OK")
        self.assertEqual(response["conversation_id"], "test-conversation-id")
        self.assertEqual(len(response["messages"]), 2)
        self.assertEqual(response["messages"][0]["speaker"], "user")
        self.assertEqual(response["messages"][0]["text"], "Hello, Claude!")
        self.assertEqual(response["messages"][1]["speaker"], "assistant")
        
        # Verify the repository was called correctly
        self.mock_memory_repository.get_conversation_history.assert_called_once_with(
            conversation_id="test-conversation-id",
            limit=10,
            offset=0
        )
    
    def test_get_conversations_list(self):
        """Test retrieving the list of conversations."""
        # Create test request
        request = {
            "limit": 5,
            "scope": "TestScope",
            "include_messages": True
        }
        
        # Mock additional data for include_messages
        mock_preview = [
            {"text": "Hello, Claude!", "speaker": "user", "timestamp": datetime.now() - timedelta(minutes=10)},
            {"text": "Hello! How can I help you today?", "speaker": "assistant", "timestamp": datetime.now() - timedelta(minutes=9)}
        ]
        self.mock_memory_repository.get_conversations_list.return_value[0]["preview_messages"] = mock_preview
        
        # Call the handler
        response = handle_get_conversations_list(request)
        
        # Check the response
        self.assertEqual(response["status"], "OK")
        self.assertEqual(len(response["conversations"]), 1)
        self.assertEqual(response["conversations"][0]["conversation_id"], "test-conversation-id")
        self.assertEqual(response["conversations"][0]["message_count"], 5)
        self.assertTrue("preview_messages" in response["conversations"][0])
        
        # Verify the repository was called correctly
        self.mock_memory_repository.get_conversations_list.assert_called_once_with(
            limit=5,
            scope="TestScope",
            include_messages=True
        )


class TestConversationSummary(unittest.TestCase):
    """Tests for conversation summarization functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a patch for the memory repository
        self.memory_repository_patch = patch('src.infinite_memory_mcp.core.memory_service.memory_repository')
        self.mock_memory_repository = self.memory_repository_patch.start()
        
        # Mock the get_conversation_history method for summarization
        test_memories = [
            ConversationMemory(
                id="memory-id-1",
                conversation_id="test-conversation-id",
                speaker="user",
                text="Hello, Claude!",
                timestamp=datetime.now() - timedelta(minutes=10),
                scope="TestScope"
            ),
            ConversationMemory(
                id="memory-id-2",
                conversation_id="test-conversation-id",
                speaker="assistant",
                text="Hello! How can I help you today?",
                timestamp=datetime.now() - timedelta(minutes=9),
                scope="TestScope"
            )
        ]
        self.mock_memory_repository.get_conversation_history.return_value = test_memories
        
        # Mock the store_summary method
        self.mock_memory_repository.store_summary.return_value = "summary-id-1"
        
        # Mock get_summaries_by_conversation
        test_summaries = [
            SummaryMemory(
                id="summary-id-1",
                conversation_id="test-conversation-id",
                summary_text="Conversation about greeting and assistance.",
                scope="TestScope",
                timestamp=datetime.now(),
                time_range={
                    "from": datetime.now() - timedelta(minutes=10),
                    "to": datetime.now() - timedelta(minutes=1)
                },
                message_refs=["memory-id-1", "memory-id-2"]
            )
        ]
        self.mock_memory_repository.get_summaries_by_conversation.return_value = test_summaries
        self.mock_memory_repository.get_latest_conversation_summaries.return_value = test_summaries
    
    def tearDown(self):
        """Tear down test fixtures."""
        self.memory_repository_patch.stop()
    
    def test_create_conversation_summary_auto_generate(self):
        """Test creating a conversation summary with auto-generation."""
        # Create test request
        request = {
            "conversation_id": "test-conversation-id",
            "generate_summary": True
        }
        
        # Call the handler
        response = handle_create_conversation_summary(request)
        
        # Check the response
        self.assertEqual(response["status"], "OK")
        self.assertEqual(response["conversation_id"], "test-conversation-id")
        self.assertEqual(response["summary_id"], "summary-id-1")
        self.assertTrue("summary_text" in response)
        self.assertTrue(response["generated"])
        
        # Verify the repository was called correctly
        self.mock_memory_repository.get_conversation_history.assert_called_once_with(
            "test-conversation-id"
        )
        self.mock_memory_repository.store_summary.assert_called_once()
    
    def test_create_conversation_summary_with_provided_text(self):
        """Test creating a conversation summary with provided text."""
        # Create test request
        request = {
            "conversation_id": "test-conversation-id",
            "summary_text": "This is a custom summary.",
            "generate_summary": False
        }
        
        # Call the handler
        response = handle_create_conversation_summary(request)
        
        # Check the response
        self.assertEqual(response["status"], "OK")
        self.assertEqual(response["conversation_id"], "test-conversation-id")
        self.assertEqual(response["summary_id"], "summary-id-1")
        self.assertEqual(response["summary_text"], "This is a custom summary.")
        self.assertFalse(response["generated"])
        
        # Verify the repository calls
        self.mock_memory_repository.get_conversation_history.assert_called_once()
        self.mock_memory_repository.store_summary.assert_called_once()
    
    def test_get_conversation_summaries_by_conversation(self):
        """Test getting summaries for a specific conversation."""
        # Create test request
        request = {
            "conversation_id": "test-conversation-id"
        }
        
        # Call the handler
        response = handle_get_conversation_summaries(request)
        
        # Check the response
        self.assertEqual(response["status"], "OK")
        self.assertEqual(len(response["summaries"]), 1)
        self.assertEqual(response["summaries"][0]["conversation_id"], "test-conversation-id")
        self.assertEqual(response["summaries"][0]["summary_id"], "summary-id-1")
        self.assertEqual(response["summaries"][0]["scope"], "TestScope")
        
        # Verify the repository was called correctly
        self.mock_memory_repository.get_summaries_by_conversation.assert_called_once_with(
            "test-conversation-id"
        )
    
    def test_get_latest_conversation_summaries(self):
        """Test getting the latest conversation summaries."""
        # Create test request
        request = {
            "limit": 10,
            "scope": "TestScope"
        }
        
        # Call the handler
        response = handle_get_conversation_summaries(request)
        
        # Check the response
        self.assertEqual(response["status"], "OK")
        self.assertEqual(len(response["summaries"]), 1)
        self.assertEqual(response["summaries"][0]["summary_id"], "summary-id-1")
        
        # Verify the repository was called correctly
        self.mock_memory_repository.get_latest_conversation_summaries.assert_called_once_with(
            limit=10,
            scope="TestScope"
        )


if __name__ == "__main__":
    unittest.main() 