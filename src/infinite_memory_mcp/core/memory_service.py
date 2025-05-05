"""
Memory service for InfiniteMemoryMCP.

This module implements the main memory operations, providing high-level
functions for storing and retrieving memories.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from ..utils.config import config_manager
from ..utils.logging import logger
from .memory_repository import memory_repository
from .models import (ConversationMemory, MemoryScope, SummaryMemory,
                     UserProfileItem)


class MemoryService:
    """
    Service for memory operations.
    
    Provides high-level methods for storing and retrieving memories.
    """
    
    def __init__(self):
        """Initialize the memory service."""
        self.default_scope = config_manager.get("memory.default_scope", "Global")
        self.auto_create_scope = config_manager.get("memory.auto_create_scope", True)
    
    def store_memory(
        self,
        content: str,
        scope: Optional[str] = None,
        tags: Optional[List[str]] = None,
        source: str = "conversation",
        conversation_id: Optional[str] = None,
        speaker: str = "user"
    ) -> Dict[str, Any]:
        """
        Store a memory.
        
        Args:
            content: The text content to store
            scope: The scope to store the memory in
            tags: Tags to associate with the memory
            source: The source of the memory (conversation, summary, etc.)
            conversation_id: The ID of the conversation
            speaker: The speaker (user or assistant)
            
        Returns:
            Dictionary with status and memory ID
        """
        # Use default scope if none provided
        if not scope:
            scope = self.default_scope
        
        # Check if scope exists, create if it doesn't and auto-create is enabled
        if self.auto_create_scope:
            scope_obj = memory_repository.get_scope(scope)
            if not scope_obj:
                logger.info(f"Creating new scope: {scope}")
                new_scope = MemoryScope(
                    scope_name=scope,
                    description=f"Auto-created scope: {scope}",
                    created_at=datetime.now(),
                    active=True
                )
                memory_repository.create_scope(new_scope)
        
        # Create memory object
        memory = ConversationMemory(
            conversation_id=conversation_id or str(uuid.uuid4()),
            speaker=speaker,
            text=content,
            scope=scope,
            tags=tags or [],
            timestamp=datetime.now()
        )
        
        # Store the memory
        memory_id = memory_repository.store_conversation_memory(memory)
        
        logger.info(f"Stored memory with ID: {memory_id}")
        
        return {
            "status": "OK",
            "memory_id": memory_id,
            "scope": scope
        }
    
    def retrieve_memory(
        self,
        query: str,
        scope: Optional[str] = None,
        tags: Optional[List[str]] = None,
        time_range: Optional[Dict[str, str]] = None,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Retrieve memories matching a query.
        
        Args:
            query: The text query to search for
            scope: The scope to search in
            tags: Tags to filter by
            time_range: Time range to filter by
            top_k: Number of top results to return
            
        Returns:
            Dictionary with status and results
        """
        # Use default scope if none provided
        if not scope:
            scope = self.default_scope
        
        # Get memories by text search first (basic implementation without embeddings)
        memories = memory_repository.get_conversations_by_text_search(query, scope)
        
        # Filter by tags if provided
        if tags:
            memories = [memory for memory in memories 
                       if all(tag in memory.tags for tag in tags)]
        
        # Filter by time range if provided
        if time_range:
            from_time = None
            to_time = None
            
            if "from" in time_range:
                try:
                    from_time = datetime.fromisoformat(time_range["from"])
                except ValueError:
                    logger.warning(f"Invalid from_time format: {time_range['from']}")
            
            if "to" in time_range:
                try:
                    to_time = datetime.fromisoformat(time_range["to"])
                except ValueError:
                    logger.warning(f"Invalid to_time format: {time_range['to']}")
            
            if from_time and to_time:
                memories = [memory for memory in memories 
                           if from_time <= memory.timestamp <= to_time]
        
        # Limit to top_k results
        memories = memories[:top_k]
        
        # Convert to result format
        results = []
        for memory in memories:
            results.append({
                "text": memory.text,
                "source": "conversation",
                "timestamp": memory.timestamp.isoformat(),
                "scope": memory.scope,
                "tags": memory.tags,
                "confidence": 1.0,  # Placeholder - will be based on embedding similarity later
                "memory_id": memory.id
            })
        
        logger.info(f"Retrieved {len(results)} memories for query: {query}")
        
        return {
            "status": "OK",
            "results": results
        }
    
    def search_by_tag(self, tag: str, query: Optional[str] = None) -> Dict[str, Any]:
        """
        Search memories by tag.
        
        Args:
            tag: The tag to search for
            query: Optional additional text query
            
        Returns:
            Dictionary with status and results
        """
        # Get memories with the specified tag
        memories = memory_repository.get_conversations_by_tag(tag)
        
        # Filter by query if provided
        if query:
            # Simple substring search for now
            memories = [memory for memory in memories 
                       if query.lower() in memory.text.lower()]
        
        # Convert to result format
        results = []
        for memory in memories:
            results.append({
                "text": memory.text,
                "source": "conversation",
                "timestamp": memory.timestamp.isoformat(),
                "scope": memory.scope,
                "tags": memory.tags,
                "confidence": 1.0,  # Placeholder
                "memory_id": memory.id
            })
        
        logger.info(f"Retrieved {len(results)} memories for tag: {tag}")
        
        return {
            "status": "OK",
            "results": results
        }
    
    def search_by_scope(self, scope: str, query: Optional[str] = None) -> Dict[str, Any]:
        """
        Search memories by scope.
        
        Args:
            scope: The scope to search in
            query: Optional additional text query
            
        Returns:
            Dictionary with status and results
        """
        # Get memories in the specified scope
        memories = memory_repository.get_conversations_by_scope(scope)
        
        # Filter by query if provided
        if query:
            # Simple substring search for now
            memories = [memory for memory in memories 
                       if query.lower() in memory.text.lower()]
        
        # Convert to result format
        results = []
        for memory in memories:
            results.append({
                "text": memory.text,
                "source": "conversation",
                "timestamp": memory.timestamp.isoformat(),
                "scope": memory.scope,
                "tags": memory.tags,
                "confidence": 1.0,  # Placeholder
                "memory_id": memory.id
            })
        
        logger.info(f"Retrieved {len(results)} memories for scope: {scope}")
        
        return {
            "status": "OK",
            "results": results
        }
    
    def delete_memory(
        self,
        memory_id: Optional[str] = None,
        scope: Optional[str] = None,
        tag: Optional[str] = None,
        query: Optional[str] = None,
        forget_mode: str = "soft"
    ) -> Dict[str, Any]:
        """
        Delete memories.
        
        Can delete by ID, scope, tag, or query.
        
        Args:
            memory_id: ID of a specific memory to delete
            scope: Scope to delete memories from
            tag: Tag to delete memories with
            query: Query to find memories to delete
            forget_mode: "soft" or "hard" deletion
            
        Returns:
            Dictionary with status and count of deleted memories
        """
        deleted_count = 0
        
        # Handle deletion by ID
        if memory_id:
            result = memory_repository.delete_memory(memory_id)
            deleted_count = 1 if result else 0
        
        # Handle deletion by scope
        elif scope:
            deleted_count = memory_repository.delete_memories_by_scope(scope)
        
        # Handle deletion by tag
        elif tag:
            deleted_count = memory_repository.delete_memories_by_tag(tag)
        
        # Handle deletion by query
        elif query:
            # Get memories by text search
            memories = memory_repository.get_conversations_by_text_search(query)
            
            # Delete each memory
            for memory in memories:
                if memory.id:
                    result = memory_repository.delete_memory(memory.id)
                    if result:
                        deleted_count += 1
        
        logger.info(f"Deleted {deleted_count} memories")
        
        return {
            "status": "OK",
            "deleted_count": deleted_count,
            "scope": scope,
            "note": f"Deleted {deleted_count} memories"
        }
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the memory database.
        
        Returns:
            Dictionary with memory statistics
        """
        return memory_repository.get_memory_stats()


# Create a singleton instance
memory_service = MemoryService() 