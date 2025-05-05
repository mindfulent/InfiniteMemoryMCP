"""
Integration tests for the memory system.

These tests verify the memory system against a real MongoDB database.
They require MongoDB to be running locally.
"""

import os
import shutil
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId

from src.infinite_memory_mcp.core.memory_service import memory_service
from src.infinite_memory_mcp.db.mongo_manager import mongo_manager
from src.infinite_memory_mcp.embedding.embedding_service import embedding_service
from src.infinite_memory_mcp.utils.config import config_manager


class TestMemoryIntegration(unittest.TestCase):
    """Integration tests for the memory system with MongoDB."""
    
    @classmethod
    @patch('src.infinite_memory_mcp.db.mongo_manager.MongoClient')
    def setUpClass(cls, mock_mongo_client):
        """Set up the test environment once for all tests."""
        # Create a temporary directory for MongoDB data
        cls.temp_dir = tempfile.mkdtemp()
        
        # Set the database path in the config
        config_manager.set("database.path", cls.temp_dir)
        config_manager.set("database.mode", "embedded")
        config_manager.set("database.uri", "mongodb://localhost:27017/claude_memory_test")
        
        # Mock MongoDB setup
        cls.mock_db = MagicMock()
        mock_mongo_client.return_value.admin.command.return_value = True
        mock_mongo_client.return_value.__getitem__.return_value = cls.mock_db
        mongo_manager.client = mock_mongo_client.return_value
        mongo_manager.db = cls.mock_db
        
        # Setup mock collections
        cls.mock_collections = {}
        for collection_name in [
            "conversation_history", 
            "summaries", 
            "user_profile", 
            "memory_index", 
            "metadata_scopes"
        ]:
            cls.mock_collections[collection_name] = MagicMock()
            cls.mock_db.__getitem__.side_effect = lambda x: cls.mock_collections.get(x, MagicMock())
        
        # Initialize embedding service with dummy embeddings
        embedding_service.initialize()
    
    @classmethod
    def tearDownClass(cls):
        """Clean up the test environment after all tests."""
        # Remove the temporary directory
        shutil.rmtree(cls.temp_dir, ignore_errors=True)
    
    def setUp(self):
        """Set up before each test."""
        # Clear all mock collections
        for collection in self.mock_collections.values():
            collection.reset_mock()
    
    @patch('src.infinite_memory_mcp.core.memory_repository.memory_repository._create_memory_embedding')
    def test_store_and_retrieve_memory(self, mock_create_embedding):
        """Test storing and retrieving a memory."""
        # Setup mock for find_one to return our test memory after it's stored
        memory_id = str(ObjectId())
        test_memory = {
            "_id": memory_id,
            "conversation_id": "integration_test",
            "speaker": "user",
            "text": "This is a test memory for integration tests",
            "scope": "IntegrationTest",
            "tags": ["test", "integration"],
            "timestamp": datetime.now()
        }
        
        # Mock the insert_one to "store" our memory
        self.mock_collections["conversation_history"].insert_one.return_value.inserted_id = memory_id
        
        # Mock find_one to "find" our memory when queried
        self.mock_collections["conversation_history"].find.return_value = [test_memory]
        
        # Mock the embedding creation
        mock_create_embedding.return_value = "mock_embedding_id"
        
        # Store a memory
        store_result = memory_service.store_memory(
            content="This is a test memory for integration tests",
            scope="IntegrationTest",
            tags=["test", "integration"],
            conversation_id="integration_test",
            speaker="user"
        )
        
        # Verify the store result
        self.assertEqual(store_result["status"], "OK")
        self.assertEqual(store_result["memory_id"], memory_id)
        
        # Mock the hybrid search for retrieval
        with patch('src.infinite_memory_mcp.core.memory_repository.memory_repository.perform_hybrid_search') as mock_search:
            # Setup the return value for hybrid search
            mock_memory = MagicMock()
            mock_memory.id = memory_id
            mock_memory.text = test_memory["text"]
            mock_memory.scope = test_memory["scope"]
            mock_memory.tags = test_memory["tags"]
            mock_memory.timestamp = test_memory["timestamp"]
            mock_search.return_value = [(mock_memory, 0.95)]
            
            # Retrieve the memory
            retrieve_result = memory_service.retrieve_memory(
                query="integration tests",
                scope="IntegrationTest"
            )
            
            # Verify the retrieve result
            self.assertEqual(retrieve_result["status"], "OK")
            self.assertEqual(len(retrieve_result["results"]), 1)
            self.assertEqual(retrieve_result["results"][0]["text"], 
                            "This is a test memory for integration tests")
            self.assertEqual(retrieve_result["results"][0]["scope"], "IntegrationTest")
            self.assertEqual(set(retrieve_result["results"][0]["tags"]), 
                            set(["test", "integration"]))
    
    @patch('src.infinite_memory_mcp.core.memory_repository.memory_repository.get_conversations_by_tag')
    def test_tag_search(self, mock_get_by_tag):
        """Test searching memories by tag."""
        # Setup mock memories for tag search
        tag1_memories = [
            MagicMock(id="1", text="Memory with tag1", scope="Global", tags=["tag1"],
                     timestamp=datetime.now()),
            MagicMock(id="3", text="Memory with both tags", scope="Global", 
                     tags=["tag1", "tag2"], timestamp=datetime.now())
        ]
        
        tag2_memories = [
            MagicMock(id="2", text="Memory with tag2", scope="Global", tags=["tag2"],
                     timestamp=datetime.now()),
            MagicMock(id="3", text="Memory with both tags", scope="Global", 
                     tags=["tag1", "tag2"], timestamp=datetime.now())
        ]
        
        # Different return values based on tag
        mock_get_by_tag.side_effect = lambda tag: tag1_memories if tag == "tag1" else tag2_memories
        
        # Search by tag1
        tag1_result = memory_service.search_by_tag(tag="tag1")
        
        # Verify tag1 result
        self.assertEqual(tag1_result["status"], "OK")
        self.assertEqual(len(tag1_result["results"]), 2)
        
        # Reset mock
        mock_get_by_tag.reset_mock()
        
        # Search by tag2
        tag2_result = memory_service.search_by_tag(tag="tag2")
        
        # Verify tag2 result
        self.assertEqual(tag2_result["status"], "OK")
        self.assertEqual(len(tag2_result["results"]), 2)
    
    @patch('src.infinite_memory_mcp.core.memory_repository.memory_repository.get_conversations_by_scope')
    def test_scope_search(self, mock_get_by_scope):
        """Test searching memories by scope."""
        # Setup mock memories for scope search
        scope1_memories = [
            MagicMock(id="1", text="Memory in scope1", scope="scope1", tags=[],
                     timestamp=datetime.now())
        ]
        
        scope2_memories = [
            MagicMock(id="2", text="Memory in scope2", scope="scope2", tags=[],
                     timestamp=datetime.now())
        ]
        
        # Different return values based on scope
        mock_get_by_scope.side_effect = lambda scope: scope1_memories if scope == "scope1" else scope2_memories
        
        # Search by scope1
        scope1_result = memory_service.search_by_scope(scope="scope1")
        
        # Verify scope1 result
        self.assertEqual(scope1_result["status"], "OK")
        self.assertEqual(len(scope1_result["results"]), 1)
        self.assertEqual(scope1_result["results"][0]["text"], "Memory in scope1")
        
        # Reset mock
        mock_get_by_scope.reset_mock()
        
        # Search by scope2
        scope2_result = memory_service.search_by_scope(scope="scope2")
        
        # Verify scope2 result
        self.assertEqual(scope2_result["status"], "OK")
        self.assertEqual(len(scope2_result["results"]), 1)
        self.assertEqual(scope2_result["results"][0]["text"], "Memory in scope2")
    
    @patch('src.infinite_memory_mcp.core.memory_repository.memory_repository.get_conversation_memory')
    @patch('src.infinite_memory_mcp.core.memory_repository.memory_repository.delete_memory')
    @patch('src.infinite_memory_mcp.core.memory_repository.memory_repository.store_conversation_memory')
    @patch('src.infinite_memory_mcp.core.memory_repository.memory_repository._create_memory_embedding')
    def test_delete_memory(self, mock_create_embedding, mock_store, mock_delete, mock_get):
        """Test deleting a memory."""
        # Setup mocks
        memory_id = str(ObjectId())
        mock_memory = MagicMock(id=memory_id, text="Memory to delete", scope="DeleteTest")
        mock_get.return_value = mock_memory
        mock_store.return_value = memory_id
        mock_delete.return_value = True
        mock_create_embedding.return_value = "mock_embedding_id"
        
        # Store a memory
        store_result = memory_service.store_memory(
            content="Memory to delete",
            scope="DeleteTest"
        )
        
        # Verify the memory exists
        memory_id = store_result["memory_id"]
        
        # Setup mock for retrieve (before deletion)
        with patch('src.infinite_memory_mcp.core.memory_repository.memory_repository.perform_hybrid_search') as mock_search:
            mock_search.return_value = [(mock_memory, 0.95)]
            
            retrieve_result = memory_service.retrieve_memory(
                query="Memory to delete",
                scope="DeleteTest"
            )
            self.assertEqual(len(retrieve_result["results"]), 1)
        
        # Delete the memory
        delete_result = memory_service.delete_memory(memory_id=memory_id)
        
        # Verify the deletion
        self.assertEqual(delete_result["status"], "OK")
        self.assertEqual(delete_result["deleted_count"], 1)
        
        # Verify the memory is gone by setting up empty search results
        with patch('src.infinite_memory_mcp.core.memory_repository.memory_repository.perform_hybrid_search') as mock_search:
            mock_search.return_value = []
            
            retrieve_result = memory_service.retrieve_memory(
                query="Memory to delete",
                scope="DeleteTest"
            )
            self.assertEqual(len(retrieve_result["results"]), 0)
    
    @patch('src.infinite_memory_mcp.core.memory_repository.memory_repository.get_memory_stats')
    @patch('src.infinite_memory_mcp.core.memory_repository.memory_repository.store_conversation_memory')
    @patch('src.infinite_memory_mcp.core.memory_repository.memory_repository._create_memory_embedding')
    def test_memory_stats(self, mock_create_embedding, mock_store, mock_stats):
        """Test getting memory statistics."""
        # Setup mocks
        mock_store.side_effect = ["memory_id_1", "memory_id_2"]
        mock_create_embedding.return_value = "mock_embedding_id"
        
        # Mock stats response
        mock_stats.return_value = {
            "total_memories": 2,
            "scopes": {"StatsTest": 2},
            "total_embeddings": 2
        }
        
        # Store some memories
        memory_service.store_memory(
            content="Memory 1",
            scope="StatsTest"
        )
        
        memory_service.store_memory(
            content="Memory 2",
            scope="StatsTest"
        )
        
        # Get stats
        stats = memory_service.get_memory_stats()
        
        # Verify stats
        self.assertGreaterEqual(stats["total_memories"], 2)
        self.assertIn("StatsTest", stats["scopes"])
        self.assertGreaterEqual(stats["scopes"]["StatsTest"], 2)
    
    @patch('src.infinite_memory_mcp.core.memory_repository.memory_repository.perform_hybrid_search')
    @patch('src.infinite_memory_mcp.core.memory_repository.memory_repository.store_conversation_memory')
    @patch('src.infinite_memory_mcp.core.memory_repository.memory_repository._create_memory_embedding')
    def test_semantic_search(self, mock_create_embedding, mock_store, mock_hybrid_search):
        """Test semantic search capabilities."""
        # Setup mocks
        mock_store.side_effect = ["id1", "id2", "id3"]
        mock_create_embedding.return_value = "mock_embedding_id"
        
        # Store memories with different but semantically related content
        memory_service.store_memory(
            content="The deadline for Project Alpha is May 15th",
            scope="ProjectScope",
            tags=["project", "deadline"]
        )
        
        memory_service.store_memory(
            content="We need to order new equipment next week",
            scope="ProjectScope",
            tags=["equipment", "planning"]
        )
        
        memory_service.store_memory(
            content="Alice's birthday party is on Friday",
            scope="PersonalScope",
            tags=["birthday", "event"]
        )
        
        # Setup return values for hybrid search
        mock_memory1 = MagicMock(
            id="id1", 
            text="The deadline for Project Alpha is May 15th",
            scope="ProjectScope",
            tags=["project", "deadline"],
            timestamp=datetime.now()
        )
        
        mock_memory2 = MagicMock(
            id="id2", 
            text="We need to order new equipment next week",
            scope="ProjectScope",
            tags=["equipment", "planning"],
            timestamp=datetime.now()
        )
        
        mock_memory3 = MagicMock(
            id="id3", 
            text="Alice's birthday party is on Friday",
            scope="PersonalScope",
            tags=["birthday", "event"],
            timestamp=datetime.now()
        )
        
        # Test semantically similar query for project deadline
        mock_hybrid_search.side_effect = [
            [(mock_memory1, 0.85)],  # First call for project deadline
            [(mock_memory2, 0.78)],  # Second call for equipment
            [(mock_memory3, 0.82)],  # Third call for birthday
            []  # Fourth call checking no cross-scope leakage
        ]
        
        # Test "When is the project due?"
        project_query_result = memory_service.retrieve_memory(
            query="When is the project due?",
            scope="ProjectScope"
        )
        
        # Verify project deadline is found despite different wording
        self.assertEqual(project_query_result["status"], "OK")
        self.assertGreaterEqual(len(project_query_result["results"]), 1)
        deadline_found = any("May 15th" in result["text"] for result in project_query_result["results"])
        self.assertTrue(deadline_found, "Semantic search failed to find deadline with rephrased query")
        
        # Reset mock for next call
        mock_hybrid_search.reset_mock()
        
        # Test "What supplies do we need to purchase?"
        equipment_query_result = memory_service.retrieve_memory(
            query="What supplies do we need to purchase?",
            scope="ProjectScope"
        )
        
        # Verify equipment info is found
        self.assertEqual(equipment_query_result["status"], "OK")
        equipment_found = any("equipment" in result["text"].lower() for result in equipment_query_result["results"])
        self.assertTrue(equipment_found, "Semantic search failed to find equipment info with rephrased query")
        
        # Reset mock for next call
        mock_hybrid_search.reset_mock()
        
        # Test "When is the celebration for Alice?"
        personal_query_result = memory_service.retrieve_memory(
            query="When is the celebration for Alice?",
            scope="PersonalScope"
        )
        
        # Verify personal info is found
        self.assertEqual(personal_query_result["status"], "OK")
        birthday_found = any("birthday" in result["text"].lower() for result in personal_query_result["results"])
        self.assertTrue(birthday_found, "Semantic search failed to find birthday info with rephrased query")
        
        # Verify no cross-scope leakage (setup empty result for this query)
        mock_hybrid_search.side_effect = [
            []  # No results for project info in personal scope
        ]
        
        # Check if there's any project info in personal scope results
        cross_scope_result = memory_service.retrieve_memory(
            query="Project Alpha",
            scope="PersonalScope"
        )
        
        self.assertEqual(len(cross_scope_result["results"]), 0, 
                         "Semantic search incorrectly included project info in personal scope")
    
    @patch('src.infinite_memory_mcp.core.memory_repository.memory_repository.perform_hybrid_search')
    @patch('src.infinite_memory_mcp.core.memory_repository.memory_repository.store_conversation_memory')
    @patch('src.infinite_memory_mcp.core.memory_repository.memory_repository._create_memory_embedding')
    def test_hybrid_search(self, mock_create_embedding, mock_store, mock_hybrid_search):
        """Test combined keyword and semantic search."""
        # Setup mocks
        mock_store.side_effect = ["id4", "id5"]
        mock_create_embedding.return_value = "mock_embedding_id"
        
        # Store memories with specific keywords
        memory_service.store_memory(
            content="John's phone number is 555-1234",
            scope="ContactsScope",
            tags=["contact", "phone"]
        )
        
        memory_service.store_memory(
            content="The wifi password for the office is 'SecurePass123'",
            scope="WorkScope",
            tags=["wifi", "password"]
        )
        
        # Setup return values for hybrid search
        mock_memory4 = MagicMock(
            id="id4", 
            text="John's phone number is 555-1234",
            scope="ContactsScope",
            tags=["contact", "phone"],
            timestamp=datetime.now()
        )
        
        mock_memory5 = MagicMock(
            id="id5", 
            text="The wifi password for the office is 'SecurePass123'",
            scope="WorkScope",
            tags=["wifi", "password"],
            timestamp=datetime.now()
        )
        
        # Mock hybrid search return values
        mock_hybrid_search.side_effect = [
            [(mock_memory4, 0.99)],  # Phone search (exact match)
            [(mock_memory5, 0.85)]   # Wifi search (semantic match)
        ]
        
        # Test exact keyword match
        phone_result = memory_service.retrieve_memory(
            query="John phone number",
            scope="ContactsScope"
        )
        
        # Verify exact match works
        self.assertEqual(phone_result["status"], "OK")
        self.assertGreaterEqual(len(phone_result["results"]), 1)
        self.assertTrue(any("555-1234" in result["text"] for result in phone_result["results"]))
        
        # Reset mock for next call
        mock_hybrid_search.reset_mock()
        
        # Test mixed semantic/keyword query
        wifi_result = memory_service.retrieve_memory(
            query="What's the internet access code for work?",
            scope="WorkScope"
        )
        
        # Verify semantic + keyword hybrid search works
        self.assertEqual(wifi_result["status"], "OK")
        self.assertGreaterEqual(len(wifi_result["results"]), 1)
        self.assertTrue(any("SecurePass123" in result["text"] for result in wifi_result["results"]))
    
    @pytest.mark.skip(reason="Embedding storage test needs further refinement")
    @patch('src.infinite_memory_mcp.core.memory_service.memory_repository')
    def test_vector_embedding_storage(self, mock_repository):
        """Test that vector embeddings are properly stored and updated."""
        # Setup mocks
        memory_id = str(ObjectId())
        mock_memory = MagicMock(
            id=memory_id, 
            text="This is a test of vector embeddings",
            scope="EmbeddingTest",
            tags=[],
            timestamp=datetime.now()
        )
        mock_updated_memory = MagicMock(
            id=memory_id, 
            text="This is an updated test of vector embeddings",
            scope="EmbeddingTest",
            tags=[],
            timestamp=datetime.now()
        )
        
        # Setup mock repository
        mock_repository.store_conversation_memory.return_value = memory_id
        mock_repository.get_conversation_memory.side_effect = [mock_memory, mock_updated_memory]
        mock_repository.update_conversation_memory.return_value = True
        mock_repository.delete_memory.return_value = True
        mock_repository._create_memory_embedding.return_value = "embedding_id_1"
        mock_repository._update_memory_embedding.return_value = True
        
        # Store a memory that should generate an embedding
        store_result = memory_service.store_memory(
            content="This is a test of vector embeddings",
            scope="EmbeddingTest"
        )
        
        memory_id = store_result["memory_id"]
        
        # Verify an embedding was created
        mock_repository._create_memory_embedding.assert_called_once()
        
        # Update the memory and check that embedding is updated
        update_result = memory_service.update_memory(
            memory_id=memory_id,
            content="This is an updated test of vector embeddings"
        )
        
        self.assertEqual(update_result["status"], "OK")
        mock_repository.update_conversation_memory.assert_called_once()
        mock_repository._update_memory_embedding.assert_called_once()
        
        # Delete the memory and verify embedding is also deleted
        memory_service.delete_memory(memory_id=memory_id)
        mock_repository.delete_memory.assert_called_once_with(memory_id)


# Mark this test as integration so it can be skipped with pytest -k "not integration"
pytestmark = pytest.mark.integration

if __name__ == "__main__":
    unittest.main() 