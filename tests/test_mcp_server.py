"""
Test the MCP server functionality.
"""

import json
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

import sys
import os

# Add the src directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.infinite_memory_mcp.mcp.mcp_server import MCPServer
from src.infinite_memory_mcp.mcp.commands import handle_ping


class TestMCPServer(unittest.TestCase):
    """Test the MCPServer class."""
    
    def setUp(self):
        """Set up the test environment."""
        self.server = MCPServer()
        
        # Register a test command handler
        self.server.register_command("ping", handle_ping)
    
    def test_process_request_valid(self):
        """Test processing a valid request."""
        request = json.dumps({
            "action": "ping",
            "message": "test message"
        })
        
        response = self.server.process_request(request)
        
        self.assertIsNotNone(response)
        self.assertEqual(response["status"], "OK")
        self.assertEqual(response["echo"], "test message")
    
    def test_process_request_invalid_json(self):
        """Test processing an invalid JSON request."""
        request = "not valid json"
        
        response = self.server.process_request(request)
        
        self.assertIsNotNone(response)
        self.assertEqual(response["status"], "error")
        self.assertIn("Invalid JSON", response["error"])
    
    def test_process_request_unknown_action(self):
        """Test processing a request with an unknown action."""
        request = json.dumps({
            "action": "unknown_action"
        })
        
        response = self.server.process_request(request)
        
        self.assertIsNotNone(response)
        self.assertEqual(response["status"], "error")
        self.assertIn("Unknown action", response["error"])
    
    def test_process_request_missing_action(self):
        """Test processing a request with a missing action."""
        request = json.dumps({
            "no_action": "value"
        })
        
        response = self.server.process_request(request)
        
        self.assertIsNotNone(response)
        self.assertEqual(response["status"], "error")
        self.assertIn("Missing 'action'", response["error"])


if __name__ == "__main__":
    unittest.main() 