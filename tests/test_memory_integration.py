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

import pytest

from src.infinite_memory_mcp.core.memory_service import memory_service
from src.infinite_memory_mcp.db.mongo_manager import mongo_manager
from src.infinite_memory_mcp.utils.config import config_manager


class TestMemoryIntegration(unittest.TestCase):
    """Integration tests for the memory system with MongoDB."""
    
    @classmethod
    def setUpClass(cls):
        """Set up the test environment once for all tests."""
        # Create a temporary directory for MongoDB data
        cls.temp_dir = tempfile.mkdtemp()
        
        # Set the database path in the config
        config_manager.set("database.path", cls.temp_dir)
        config_manager.set("database.mode", "embedded")
        config_manager.set("database.uri", "mongodb://localhost:27017/claude_memory_test")
        
        # Start MongoDB
        if not mongo_manager.start():
            raise RuntimeError("Failed to start MongoDB for integration tests")
        
        # Wait for MongoDB to start
        time.sleep(1)
    
    @classmethod
    def tearDownClass(cls):
        """Clean up the test environment after all tests."""
        # Stop MongoDB
        mongo_manager.stop()
        
        # Remove the temporary directory
        shutil.rmtree(cls.temp_dir, ignore_errors=True)
    
    def setUp(self):
        """Set up before each test."""
        # Clear all collections before each test
        db = mongo_manager.db
        if db:
            for collection_name in db.list_collection_names():
                if collection_name != "system.indexes":
                    db[collection_name].delete_many({})
    
    def test_store_and_retrieve_memory(self):
        """Test storing and retrieving a memory."""
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
        self.assertIsNotNone(store_result["memory_id"])
        
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
    
    def test_tag_search(self):
        """Test searching memories by tag."""
        # Store memories with different tags
        memory_service.store_memory(
            content="Memory with tag1",
            tags=["tag1"]
        )
        
        memory_service.store_memory(
            content="Memory with tag2",
            tags=["tag2"]
        )
        
        memory_service.store_memory(
            content="Memory with both tags",
            tags=["tag1", "tag2"]
        )
        
        # Search by tag1
        tag1_result = memory_service.search_by_tag(tag="tag1")
        
        # Verify tag1 result
        self.assertEqual(tag1_result["status"], "OK")
        self.assertEqual(len(tag1_result["results"]), 2)
        
        # Search by tag2
        tag2_result = memory_service.search_by_tag(tag="tag2")
        
        # Verify tag2 result
        self.assertEqual(tag2_result["status"], "OK")
        self.assertEqual(len(tag2_result["results"]), 2)
    
    def test_scope_search(self):
        """Test searching memories by scope."""
        # Store memories in different scopes
        memory_service.store_memory(
            content="Memory in scope1",
            scope="scope1"
        )
        
        memory_service.store_memory(
            content="Memory in scope2",
            scope="scope2"
        )
        
        # Search by scope1
        scope1_result = memory_service.search_by_scope(scope="scope1")
        
        # Verify scope1 result
        self.assertEqual(scope1_result["status"], "OK")
        self.assertEqual(len(scope1_result["results"]), 1)
        self.assertEqual(scope1_result["results"][0]["text"], "Memory in scope1")
        
        # Search by scope2
        scope2_result = memory_service.search_by_scope(scope="scope2")
        
        # Verify scope2 result
        self.assertEqual(scope2_result["status"], "OK")
        self.assertEqual(len(scope2_result["results"]), 1)
        self.assertEqual(scope2_result["results"][0]["text"], "Memory in scope2")
    
    def test_delete_memory(self):
        """Test deleting a memory."""
        # Store a memory
        store_result = memory_service.store_memory(
            content="Memory to delete",
            scope="DeleteTest"
        )
        
        # Verify the memory exists
        memory_id = store_result["memory_id"]
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
        
        # Verify the memory is gone
        retrieve_result = memory_service.retrieve_memory(
            query="Memory to delete",
            scope="DeleteTest"
        )
        self.assertEqual(len(retrieve_result["results"]), 0)
    
    def test_memory_stats(self):
        """Test getting memory statistics."""
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


# Mark this test as integration so it can be skipped with pytest -k "not integration"
pytestmark = pytest.mark.integration

if __name__ == "__main__":
    unittest.main() 