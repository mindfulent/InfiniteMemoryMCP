"""
MCP command handlers for InfiniteMemoryMCP.

This module implements handlers for the various MCP commands supported by
InfiniteMemoryMCP.
"""

import time
from typing import Any, Dict

from ..utils.logging import logger
from .mcp_server import mcp_server


def handle_ping(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle a ping request. Used for testing the MCP connection.
    
    Args:
        request: The MCP request
        
    Returns:
        A dict containing the response
    """
    logger.debug("Handling ping request")
    
    # Extract message from the request, if any
    message = request.get("message", "")
    
    # Prepare response
    response = {
        "status": "OK",
        "timestamp": time.time(),
        "echo": message
    }
    
    return response


def handle_get_memory_stats(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle a get_memory_stats request.
    
    Returns statistics about the memory database.
    
    Args:
        request: The MCP request
        
    Returns:
        A dict containing the response with memory statistics
    """
    logger.debug("Handling get_memory_stats request")
    
    # For now, return dummy stats
    # This will be implemented properly when we have the database functionality
    response = {
        "status": "OK",
        "stats": {
            "total_memories": 0,
            "conversation_count": 0,
            "scopes": {"Global": 0},
            "last_backup": None,
            "db_size_mb": 0
        }
    }
    
    return response


def register_command_handlers():
    """Register all command handlers with the MCP server."""
    # Register basic commands
    mcp_server.register_command("ping", handle_ping)
    mcp_server.register_command("get_memory_stats", handle_get_memory_stats)
    
    # Additional commands will be registered here as we implement them 