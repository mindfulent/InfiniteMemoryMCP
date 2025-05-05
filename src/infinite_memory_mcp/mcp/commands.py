"""
MCP command handlers for InfiniteMemoryMCP.

This module implements handlers for the various MCP commands supported by
InfiniteMemoryMCP.
"""

import time
from typing import Any, Dict, List, Optional

from ..core.memory_service import memory_service
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
    
    # Get memory stats
    stats = memory_service.get_memory_stats()
    
    response = {
        "status": "OK",
        "stats": stats
    }
    
    return response


def handle_store_memory(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle a store_memory request.
    
    Stores a piece of information in the memory database.
    
    Args:
        request: The MCP request containing content to store
        
    Returns:
        A dict containing the response with memory ID
    """
    logger.debug("Handling store_memory request")
    
    # Extract required content
    content = request.get("content", "")
    if not content:
        return {
            "status": "error",
            "error": "Missing required 'content' field"
        }
    
    # Extract optional metadata
    metadata = request.get("metadata", {})
    scope = metadata.get("scope")
    tags = metadata.get("tags", [])
    source = metadata.get("source", "conversation")
    conversation_id = metadata.get("conversation_id")
    speaker = metadata.get("speaker", "user")
    
    # Store the memory
    result = memory_service.store_memory(
        content=content,
        scope=scope,
        tags=tags,
        source=source,
        conversation_id=conversation_id,
        speaker=speaker
    )
    
    return result


def handle_retrieve_memory(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle a retrieve_memory request.
    
    Retrieves memories matching a query.
    
    Args:
        request: The MCP request containing the query
        
    Returns:
        A dict containing the response with matching memories
    """
    logger.debug("Handling retrieve_memory request")
    
    # Extract the query
    query = request.get("query", "")
    if not query:
        return {
            "status": "error",
            "error": "Missing required 'query' field"
        }
    
    # Extract optional filters
    filter_data = request.get("filter", {})
    scope = filter_data.get("scope")
    tags = filter_data.get("tags")
    time_range = filter_data.get("time_range")
    
    # Extract optional top_k
    top_k = request.get("top_k", 5)
    
    # Retrieve matching memories
    result = memory_service.retrieve_memory(
        query=query,
        scope=scope,
        tags=tags,
        time_range=time_range,
        top_k=top_k
    )
    
    return result


def handle_search_by_tag(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle a search_by_tag request.
    
    Retrieves memories with a specific tag.
    
    Args:
        request: The MCP request containing the tag
        
    Returns:
        A dict containing the response with matching memories
    """
    logger.debug("Handling search_by_tag request")
    
    # Extract the tag
    tag = request.get("tag", "")
    if not tag:
        return {
            "status": "error",
            "error": "Missing required 'tag' field"
        }
    
    # Extract optional query
    query = request.get("query")
    
    # Search by tag
    result = memory_service.search_by_tag(tag=tag, query=query)
    
    return result


def handle_search_by_scope(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle a search_by_scope request.
    
    Retrieves memories in a specific scope.
    
    Args:
        request: The MCP request containing the scope
        
    Returns:
        A dict containing the response with matching memories
    """
    logger.debug("Handling search_by_scope request")
    
    # Extract the scope
    scope = request.get("scope", "")
    if not scope:
        return {
            "status": "error",
            "error": "Missing required 'scope' field"
        }
    
    # Extract optional query
    query = request.get("query")
    
    # Search by scope
    result = memory_service.search_by_scope(scope=scope, query=query)
    
    return result


def handle_delete_memory(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle a delete_memory request.
    
    Deletes memories by various criteria.
    
    Args:
        request: The MCP request with deletion criteria
        
    Returns:
        A dict containing the response with deletion results
    """
    logger.debug("Handling delete_memory request")
    
    # Extract the target
    target = request.get("target", {})
    
    # Extract criteria
    memory_id = target.get("memory_id")
    scope = target.get("scope")
    tag = target.get("tag")
    query = target.get("query")
    
    # Extract forget mode
    forget_mode = request.get("forget_mode", "soft")
    
    # Check that at least one criterion is provided
    if not any([memory_id, scope, tag, query]):
        return {
            "status": "error",
            "error": "At least one deletion criterion is required"
        }
    
    # Delete the memories
    result = memory_service.delete_memory(
        memory_id=memory_id,
        scope=scope,
        tag=tag,
        query=query,
        forget_mode=forget_mode
    )
    
    return result


def register_command_handlers():
    """Register all command handlers with the MCP server."""
    # Register basic commands
    mcp_server.register_command("ping", handle_ping)
    mcp_server.register_command("get_memory_stats", handle_get_memory_stats)
    
    # Register memory commands
    mcp_server.register_command("store_memory", handle_store_memory)
    mcp_server.register_command("retrieve_memory", handle_retrieve_memory)
    mcp_server.register_command("search_by_tag", handle_search_by_tag)
    mcp_server.register_command("search_by_scope", handle_search_by_scope)
    mcp_server.register_command("delete_memory", handle_delete_memory)
    
    # Additional commands will be registered here as we implement them 