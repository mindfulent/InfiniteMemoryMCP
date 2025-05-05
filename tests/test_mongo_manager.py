"""
Test the MongoDB manager functionality.
"""

import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import sys

# Add the src directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.infinite_memory_mcp.db.mongo_manager import MongoDBManager


class TestMongoDBManager(unittest.TestCase):
    """Test the MongoDBManager class."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for the test database
        self.test_db_path = tempfile.mkdtemp()
        
        # Patch the config manager
        self.config_patcher = patch('src.infinite_memory_mcp.db.mongo_manager.config_manager')
        self.mock_config = self.config_patcher.start()
        
        # Configure the mock config
        self.mock_config.get.side_effect = self._mock_config_get
        self.mock_config.get_database_path.return_value = self.test_db_path
    
    def tearDown(self):
        """Clean up after tests."""
        # Stop the patchers
        self.config_patcher.stop()
        
        # Remove the temporary directory
        if os.path.exists(self.test_db_path):
            shutil.rmtree(self.test_db_path)
    
    def _mock_config_get(self, key, default=None):
        """Mock implementation of config_manager.get."""
        config = {
            "database.mode": "external",  # Use external mode to avoid starting a MongoDB process
            "database.uri": "mongodb://localhost:27017/claude_memory_test",
        }
        return config.get(key, default)
    
    @patch('src.infinite_memory_mcp.db.mongo_manager.MongoClient')
    def test_init(self, mock_mongo_client):
        """Test initializing the MongoDB manager."""
        manager = MongoDBManager()
        
        # Check the manager was initialized correctly
        self.assertEqual(manager.mode, "external")
        self.assertEqual(manager.uri, "mongodb://localhost:27017/claude_memory_test")
        self.assertEqual(manager.db_name, "claude_memory_test")
        self.assertEqual(manager.db_path, self.test_db_path)
        
        # Check the database directory was created
        self.assertTrue(os.path.exists(self.test_db_path))
    
    @patch('src.infinite_memory_mcp.db.mongo_manager.MongoClient')
    def test_start_external(self, mock_mongo_client):
        """Test starting the MongoDB manager in external mode."""
        # Configure the mock client
        mock_db = MagicMock()
        mock_client = MagicMock()
        mock_client.__getitem__.return_value = mock_db
        mock_mongo_client.return_value = mock_client
        
        # Configure the mock database
        mock_db.list_collection_names.return_value = []
        
        # Create and start the manager
        manager = MongoDBManager()
        result = manager.start()
        
        # Check the connection was successful
        self.assertTrue(result)
        self.assertEqual(manager.client, mock_client)
        self.assertEqual(manager.db, mock_db)
        
        # Check the client was created with the correct URI
        mock_mongo_client.assert_called_once_with(
            "mongodb://localhost:27017/claude_memory_test",
            serverSelectionTimeoutMS=5000
        )


if __name__ == "__main__":
    unittest.main() 