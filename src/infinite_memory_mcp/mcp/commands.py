"""
MCP command handlers for InfiniteMemoryMCP.

This module implements handlers for the various MCP commands supported by
InfiniteMemoryMCP.
"""

import time
from typing import Any, Dict, List, Optional

from ..core.memory_service import memory_service
from ..db.mongo_manager import mongo_manager
from ..embedding.embedding_service import embedding_service
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


def handle_health_check(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle a health_check request.
    
    Checks the health of the memory service and its dependencies.
    
    Args:
        request: The MCP request
        
    Returns:
        A dict containing the response with health status
    """
    logger.debug("Handling health_check request")
    
    # Check MongoDB connection
    mongo_status = "OK"
    try:
        # Ping MongoDB
        mongo_manager.client.admin.command("ping")
    except Exception as e:
        mongo_status = f"ERROR: {str(e)}"
    
    # Check embedding service
    embedding_status = "OK"
    try:
        # Try generating a simple embedding
        embedding_service.generate_embedding("test")
    except Exception as e:
        embedding_status = f"ERROR: {str(e)}"
    
    # Check memory service
    memory_status = "OK"
    try:
        # Get memory stats as a basic test
        memory_service.get_memory_stats()
    except Exception as e:
        memory_status = f"ERROR: {str(e)}"
    
    # Determine overall health
    overall_status = "OK"
    if "ERROR" in mongo_status or "ERROR" in embedding_status or "ERROR" in memory_status:
        overall_status = "ERROR"
    
    response = {
        "status": overall_status,
        "components": {
            "mongodb": mongo_status,
            "embedding": embedding_status,
            "memory_service": memory_status
        },
        "timestamp": time.time()
    }
    
    return response


def handle_store_conversation_history(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle a store_conversation_history request.
    
    Stores a batch of conversation messages.
    
    Args:
        request: The MCP request containing the conversation to store
        
    Returns:
        A dict containing the response with conversation ID
    """
    logger.debug("Handling store_conversation_history request")
    
    # Extract required messages
    messages = request.get("messages", [])
    if not messages:
        return {
            "status": "ERROR",
            "error": "Missing or empty 'messages' field"
        }
    
    # Extract optional fields
    conversation_id = request.get("conversation_id")
    metadata = request.get("metadata", {})
    scope = metadata.get("scope")
    
    # Store the conversation
    result = memory_service.store_conversation_history(
        messages=messages,
        conversation_id=conversation_id,
        scope=scope
    )
    
    return result


def handle_get_conversation_history(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle a get_conversation_history request.
    
    Retrieves the conversation history for a specific conversation.
    
    Args:
        request: The MCP request containing the conversation ID
        
    Returns:
        A dict containing the response with conversation history
    """
    logger.debug("Handling get_conversation_history request")
    
    # Extract required conversation_id
    conversation_id = request.get("conversation_id")
    if not conversation_id:
        return {
            "status": "ERROR",
            "error": "Missing required 'conversation_id' field"
        }
    
    # Extract optional parameters
    limit = request.get("limit")
    offset = request.get("offset", 0)
    
    # Get the conversation history
    result = memory_service.get_conversation_history(
        conversation_id=conversation_id,
        limit=limit,
        offset=offset
    )
    
    return result


def handle_get_conversations_list(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle a get_conversations_list request.
    
    Retrieves a list of recent conversations.
    
    Args:
        request: The MCP request
        
    Returns:
        A dict containing the response with conversations list
    """
    logger.debug("Handling get_conversations_list request")
    
    # Extract optional parameters
    limit = request.get("limit", 10)
    scope = request.get("scope")
    include_messages = request.get("include_messages", False)
    
    # Get the conversations list
    result = memory_service.get_conversations_list(
        limit=limit,
        scope=scope,
        include_messages=include_messages
    )
    
    return result


def handle_create_conversation_summary(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle a create_conversation_summary request.
    
    Creates a summary for a conversation.
    
    Args:
        request: The MCP request containing the conversation ID
        
    Returns:
        A dict containing the response with summary information
    """
    logger.debug("Handling create_conversation_summary request")
    
    # Extract required conversation_id
    conversation_id = request.get("conversation_id")
    if not conversation_id:
        return {
            "status": "ERROR",
            "error": "Missing required 'conversation_id' field"
        }
    
    # Extract optional parameters
    summary_text = request.get("summary_text")
    generate_summary = request.get("generate_summary", True)
    
    # Create the summary
    result = memory_service.create_conversation_summary(
        conversation_id=conversation_id,
        summary_text=summary_text,
        generate_summary=generate_summary
    )
    
    return result


def handle_get_conversation_summaries(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle a get_conversation_summaries request.
    
    Retrieves summaries for conversations.
    
    Args:
        request: The MCP request
        
    Returns:
        A dict containing the response with summaries
    """
    logger.debug("Handling get_conversation_summaries request")
    
    # Extract optional parameters
    conversation_id = request.get("conversation_id")
    limit = request.get("limit", 10)
    scope = request.get("scope")
    
    # Get the summaries
    result = memory_service.get_conversation_summaries(
        conversation_id=conversation_id,
        limit=limit,
        scope=scope
    )
    
    return result


def handle_optimize_memory(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle an optimize_memory request.
    
    Performs optimization operations on the memory database.
    
    Args:
        request: The MCP request
        
    Returns:
        A dict containing the response with optimization results
    """
    logger.debug("Handling optimize_memory request")
    
    # Extract operations to perform (if any)
    operations = request.get("operations", [])
    
    # Default operations if none specified
    if not operations:
        operations = ["compact_db", "reindex", "summarize_old"]
    
    results = {}
    
    # Perform requested operations
    try:
        for op in operations:
            if op == "compact_db":
                # Compact the database (reduce disk usage)
                mongo_manager.client.admin.command("compact", "conversation_history")
                results["compact_db"] = "OK"
            elif op == "reindex":
                # Rebuild indexes
                mongo_manager.get_collection("conversation_history").reindex()
                mongo_manager.get_collection("memory_index").reindex()
                results["reindex"] = "OK"
            elif op == "summarize_old":
                # Summarize old conversations (not implemented yet)
                # This would find conversations older than X that don't have summaries
                # and create summaries for them
                results["summarize_old"] = "Not implemented yet"
            else:
                results[op] = "Unknown operation"
    except Exception as e:
        logger.error(f"Error during optimization: {e}")
        results["error"] = str(e)
    
    return {
        "status": "OK",
        "operations": results
    }


def register_command_handlers():
    """
    Register all command handlers with the MCP server.
    """
    # Basic commands
    mcp_server.register_command("ping", handle_ping)
    mcp_server.register_command("get_memory_stats", handle_get_memory_stats)
    mcp_server.register_command("health_check", handle_health_check)
    
    # Memory operations
    mcp_server.register_command("store_memory", handle_store_memory)
    mcp_server.register_command("retrieve_memory", handle_retrieve_memory)
    mcp_server.register_command("delete_memory", handle_delete_memory)
    
    # Memory search commands
    mcp_server.register_command("search_by_tag", handle_search_by_tag)
    mcp_server.register_command("search_by_scope", handle_search_by_scope)
    
    # Conversation history commands
    mcp_server.register_command("store_conversation_history", handle_store_conversation_history)
    mcp_server.register_command("get_conversation_history", handle_get_conversation_history)
    mcp_server.register_command("get_conversations_list", handle_get_conversations_list)
    
    # Conversation summary commands
    mcp_server.register_command("create_conversation_summary", handle_create_conversation_summary)
    mcp_server.register_command("get_conversation_summaries", handle_get_conversation_summaries)
    
    # Maintenance commands
    mcp_server.register_command("optimize_memory", handle_optimize_memory) 