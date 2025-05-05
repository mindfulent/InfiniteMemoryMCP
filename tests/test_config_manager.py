"""
Test the configuration manager functionality.
"""

import json
import os
import tempfile
import unittest
from unittest.mock import patch, mock_open

from src.infinite_memory_mcp.utils.config import ConfigManager, DEFAULT_CONFIG


class TestConfigManager(unittest.TestCase):
    """Test the ConfigManager class."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for test configs
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_config.json")
        
        # Test config data
        self.test_config = {
            "database": {
                "mode": "external",
                "uri": "mongodb://localhost:27017/test_db",
                "path": "/tmp/test_db_path"
            },
            "memory": {
                "default_scope": "TestScope"
            }
        }
        
        # Patch os.path.exists to return True for our test config
        self.exists_patcher = patch('os.path.exists')
        self.mock_exists = self.exists_patcher.start()
        self.mock_exists.side_effect = lambda path: path == self.config_path
        
        # Patch open to return our test config
        self.open_patcher = patch('builtins.open', mock_open(read_data=json.dumps(self.test_config)))
        self.mock_open = self.open_patcher.start()
    
    def tearDown(self):
        """Clean up after tests."""
        # Stop the patchers
        self.exists_patcher.stop()
        self.open_patcher.stop()
        
        # Remove test files
        if os.path.exists(self.config_path):
            os.remove(self.config_path)
        
        # Remove the temporary directory
        os.rmdir(self.temp_dir)
    
    @patch('src.infinite_memory_mcp.utils.config.CONFIG_PATHS', ['/test/config/path'])
    def test_init_load_config(self):
        """Test initializing the ConfigManager loads the config."""
        # Patch os.path.expanduser to return our test path
        with patch('os.path.expanduser', return_value=self.config_path):
            # Create a ConfigManager instance
            manager = ConfigManager()
            
            # Check the config was loaded correctly
            self.assertEqual(manager.config["database"]["mode"], "external")
            self.assertEqual(manager.config["database"]["uri"], "mongodb://localhost:27017/test_db")
            self.assertEqual(manager.config_path, self.config_path)
    
    @patch('src.infinite_memory_mcp.utils.config.CONFIG_PATHS', ['/test/config/path'])
    def test_load_config_fallback_to_default(self):
        """Test falling back to default config if no file exists."""
        # Make os.path.exists return False
        self.mock_exists.return_value = False
        
        # Create a ConfigManager instance
        manager = ConfigManager()
        
        # Check the default config was used
        self.assertEqual(manager.config, DEFAULT_CONFIG)
        self.assertIsNone(manager.config_path)
    
    @patch('src.infinite_memory_mcp.utils.config.CONFIG_PATHS', ['/test/config/path'])
    def test_load_config_handles_json_error(self):
        """Test handling of JSON decode errors."""
        # Make open return invalid JSON
        self.open_patcher.stop()
        self.open_patcher = patch('builtins.open', mock_open(read_data="invalid json"))
        self.mock_open = self.open_patcher.start()
        
        # Create a ConfigManager instance
        manager = ConfigManager()
        
        # Check the default config was used
        self.assertEqual(manager.config, DEFAULT_CONFIG)
    
    def test_get_config_value(self):
        """Test getting a configuration value."""
        # Create a ConfigManager instance with our test config
        manager = ConfigManager()
        manager.config = self.test_config
        
        # Test getting values
        self.assertEqual(manager.get("database.mode"), "external")
        self.assertEqual(manager.get("memory.default_scope"), "TestScope")
        
        # Test getting a nested value
        self.assertEqual(manager.get("database.uri"), "mongodb://localhost:27017/test_db")
        
        # Test getting a non-existent value
        self.assertIsNone(manager.get("non.existent.key"))
        
        # Test getting a non-existent value with a default
        self.assertEqual(manager.get("non.existent.key", "default_value"), "default_value")
    
    def test_set_config_value(self):
        """Test setting a configuration value."""
        # Create a ConfigManager instance with our test config
        manager = ConfigManager()
        manager.config = self.test_config.copy()
        
        # Test setting a value
        manager.set("database.mode", "embedded")
        self.assertEqual(manager.config["database"]["mode"], "embedded")
        
        # Test setting a nested value that doesn't exist yet
        manager.set("new.nested.key", "value")
        self.assertEqual(manager.config["new"]["nested"]["key"], "value")
        
        # Test overwriting a value
        manager.set("memory.default_scope", "NewScope")
        self.assertEqual(manager.config["memory"]["default_scope"], "NewScope")
    
    @patch('json.dump')
    def test_save_config(self, mock_dump):
        """Test saving the configuration to a file."""
        # Create a ConfigManager instance with our test config
        manager = ConfigManager()
        manager.config = self.test_config.copy()
        manager.config_path = self.config_path
        
        # Save the config
        with patch('os.makedirs'):
            manager.save_config()
            
            # Check the file was opened correctly
            self.mock_open.assert_called_once_with(self.config_path, "w", encoding="utf-8")
            
            # Check json.dump was called with the correct arguments
            mock_dump.assert_called_once()
            self.assertEqual(mock_dump.call_args[0][0], self.test_config)
    
    def test_get_database_path(self):
        """Test getting the expanded database path."""
        # Create a ConfigManager instance with our test config
        manager = ConfigManager()
        manager.config = self.test_config.copy()
        
        # Test getting the database path
        with patch('os.path.expanduser', return_value="/expanded/path"):
            self.assertEqual(manager.get_database_path(), "/expanded/path")
    
    def test_get_log_file_path(self):
        """Test getting the expanded log file path."""
        # Create a ConfigManager instance with our test config
        manager = ConfigManager()
        manager.config = {
            "logging": {
                "log_file": "~/logs/test.log"
            }
        }
        
        # Test getting the log file path
        with patch('os.path.expanduser', return_value="/expanded/logs/test.log"):
            self.assertEqual(manager.get_log_file_path(), "/expanded/logs/test.log")


if __name__ == "__main__":
    unittest.main() 