#!/usr/bin/env python3
"""
Test script for InfiniteMemoryMCP initialization.

This script initializes the necessary components of InfiniteMemoryMCP
and tests the MCP interface with a simple ping request, using a mock
MongoDB implementation for testing without a real MongoDB instance.
"""

import json
import os
import sys
import time

# Add the src directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.infinite_memory_mcp.db.mock_mongo import MockMongoDBManager
from src.infinite_memory_mcp.mcp.commands import register_command_handlers
from src.infinite_memory_mcp.mcp.mcp_server import mcp_server
from src.infinite_memory_mcp.utils.logging import logger


def test_ping():
    """Test the ping command."""
    request = {
        "action": "ping",
        "message": "Hello, InfiniteMemoryMCP!"
    }
    
    # Convert request to JSON string
    request_json = json.dumps(request)
    
    # Process the request
    response = mcp_server.process_request(request_json)
    
    # Print the response
    print(f"Ping response: {json.dumps(response, indent=2)}")
    
    return response


def test_get_memory_stats():
    """Test the get_memory_stats command."""
    request = {
        "action": "get_memory_stats"
    }
    
    # Convert request to JSON string
    request_json = json.dumps(request)
    
    # Process the request
    response = mcp_server.process_request(request_json)
    
    # Print the response
    print(f"Memory stats response: {json.dumps(response, indent=2)}")
    
    return response


def main():
    """Main function."""
    print("Testing InfiniteMemoryMCP initialization with mock MongoDB")
    
    # Create and start a mock MongoDB manager
    mock_mongo = MockMongoDBManager()
    
    # Patch the global mongo_manager with our mock
    import src.infinite_memory_mcp.mcp.commands
    src.infinite_memory_mcp.mcp.commands.mongo_manager = mock_mongo
    
    # Start mock MongoDB connection
    print("\nStarting mock MongoDB...")
    if not mock_mongo.start():
        print("Failed to start mock MongoDB")
        sys.exit(1)
    print("Mock MongoDB started successfully")
    
    # Register MCP command handlers
    print("\nRegistering MCP command handlers...")
    register_command_handlers()
    print("MCP command handlers registered")
    
    # Test ping command
    print("\nTesting ping command...")
    test_ping()
    
    # Test get_memory_stats command
    print("\nTesting get_memory_stats command...")
    test_get_memory_stats()
    
    # Cleanup
    print("\nCleaning up...")
    mock_mongo.stop()
    print("Cleanup complete")
    
    print("\nAll tests completed successfully")


if __name__ == "__main__":
    main() 