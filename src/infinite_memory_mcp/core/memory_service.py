"""
Memory service for InfiniteMemoryMCP.

This module implements the main memory operations, providing high-level
functions for storing and retrieving memories.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from ..embedding.embedding_service import embedding_service
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
        
        # Initialize the embedding service
        embedding_service.initialize()
    
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
    
    def update_memory(
        self,
        memory_id: str,
        content: Optional[str] = None,
        scope: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Update an existing memory.
        
        Args:
            memory_id: The ID of the memory to update
            content: New text content (if None, keep existing)
            scope: New scope (if None, keep existing)
            tags: New tags (if None, keep existing)
            
        Returns:
            Dictionary with status
        """
        # Get the existing memory
        memory = memory_repository.get_conversation_memory(memory_id)
        
        if not memory:
            return {
                "status": "ERROR",
                "message": f"Memory with ID {memory_id} not found"
            }
        
        # Update fields if provided
        if content is not None:
            memory.text = content
        
        if scope is not None:
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
            
            memory.scope = scope
        
        if tags is not None:
            memory.tags = tags
        
        # Update timestamp
        memory.timestamp = datetime.now()
        
        # Store the updated memory
        success = memory_repository.update_conversation_memory(memory)
        
        if success:
            logger.info(f"Updated memory with ID: {memory_id}")
            return {
                "status": "OK",
                "memory_id": memory_id
            }
        else:
            logger.error(f"Failed to update memory with ID: {memory_id}")
            return {
                "status": "ERROR",
                "message": f"Failed to update memory with ID {memory_id}"
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
        
        # Perform hybrid search (semantic + keyword)
        memory_tuples = memory_repository.perform_hybrid_search(
            query_text=query,
            scope=scope,
            top_k=top_k,
            similarity_threshold=0.3
        )
        
        # Filter by tags if provided
        if tags:
            memory_tuples = [
                (memory, score) for memory, score in memory_tuples
                if all(tag in memory.tags for tag in tags)
            ]
        
        # Filter by time range if provided
        if time_range:
            try:
                from_time = datetime.fromisoformat(time_range.get("from", "0001-01-01T00:00:00"))
                to_time = datetime.fromisoformat(time_range.get("to", "9999-12-31T23:59:59"))
                
                memory_tuples = [
                    (memory, score) for memory, score in memory_tuples
                    if from_time <= memory.timestamp <= to_time
                ]
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid time range format: {e}")
        
        # Prepare the results
        results = []
        for memory, score in memory_tuples:
            results.append({
                "memory_id": memory.id,
                "text": memory.text,
                "scope": memory.scope,
                "tags": memory.tags,
                "timestamp": memory.timestamp.isoformat(),
                "confidence": score
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
            # If a query is provided, use semantic search within the tagged memories
            memory_tuples = []
            memory_ids = [memory.id for memory in memories]
            
            if memory_ids:
                # Perform semantic search on just these memories
                filtered_memory_tuples = memory_repository.get_conversations_by_semantic_search(
                    query_text=query,
                    scope=None,  # Don't filter by scope since we already filtered by tag
                    top_k=len(memory_ids),  # Get all matches
                    similarity_threshold=0.1  # Lower threshold since we already filtered by tag
                )
                
                # Keep only the memories that were in the tag search results
                memory_tuples = [(memory, score) for memory, score in filtered_memory_tuples
                                if memory.id in memory_ids]
            
            # Convert to list of memories
            memories = [memory for memory, _ in memory_tuples]
        
        # Convert to result format
        results = []
        for memory in memories:
            results.append({
                "text": memory.text,
                "source": "conversation",
                "timestamp": memory.timestamp.isoformat(),
                "scope": memory.scope,
                "tags": memory.tags,
                "confidence": 1.0,  # Use 1.0 for tag-based search without query
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
        if query:
            # If query is provided, use semantic search
            memory_tuples = memory_repository.get_conversations_by_semantic_search(
                query_text=query,
                scope=scope,
                top_k=10,  # Retrieve more for scope-based search
                similarity_threshold=0.1  # Lower threshold for scope search
            )
            
            # Extract memories from tuples
            memories = [memory for memory, _ in memory_tuples]
        else:
            # Otherwise, get all memories in the scope
            memories = memory_repository.get_conversations_by_scope(scope)
        
        # Convert to result format
        results = []
        for memory in memories:
            results.append({
                "text": memory.text,
                "source": "conversation",
                "timestamp": memory.timestamp.isoformat(),
                "scope": memory.scope,
                "tags": memory.tags,
                "confidence": 1.0,  # Default confidence for scope search
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
        
        Args:
            memory_id: ID of a specific memory to delete
            scope: Delete all memories in this scope
            tag: Delete all memories with this tag
            query: Delete memories matching this query (not implemented yet)
            forget_mode: How to delete ("soft" or "hard")
            
        Returns:
            Dictionary with status and deleted count
        """
        # Currently "forget_mode" is not used, all deletions are hard deletes
        # In the future, we could implement soft deletion by just flagging items
        
        deleted_count = 0
        
        # Delete by ID if provided
        if memory_id:
            success = memory_repository.delete_memory(memory_id)
            deleted_count = 1 if success else 0
        
        # Delete by scope if provided and no ID
        elif scope:
            deleted_count = memory_repository.delete_memories_by_scope(scope)
        
        # Delete by tag if provided and no ID or scope
        elif tag:
            deleted_count = memory_repository.delete_memories_by_tag(tag)
        
        # Delete by query if provided and no ID, scope, or tag
        elif query:
            # Not implemented yet
            # Future: semantically search for memories matching the query and delete them
            logger.warning("Delete by query not implemented yet")
            return {
                "status": "ERROR",
                "message": "Delete by query not implemented yet"
            }
        
        else:
            return {
                "status": "ERROR",
                "message": "No deletion criteria provided"
            }
        
        logger.info(f"Deleted {deleted_count} memories")
        
        return {
            "status": "OK",
            "deleted_count": deleted_count,
            "scope": scope if scope else None
        }
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """
        Get memory statistics.
        
        Returns:
            Dictionary with memory statistics
        """
        return memory_repository.get_memory_stats()
    
    def store_conversation_history(
        self,
        messages: List[Dict[str, Any]],
        conversation_id: Optional[str] = None,
        scope: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Store a batch of conversation messages.
        
        Args:
            messages: List of message dictionaries with 'speaker' and 'text'
            conversation_id: The ID of the conversation (generated if not provided)
            scope: The scope to store the memories in
            
        Returns:
            Dictionary with conversation_id and status
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
        
        # Store the conversation batch
        result = memory_repository.store_conversation_batch(
            messages=messages,
            conversation_id=conversation_id,
            scope=scope
        )
        
        logger.info(f"Stored conversation batch with ID: {result['conversation_id']}")
        
        return {
            "status": "OK",
            "conversation_id": result['conversation_id'],
            "memory_ids": result['memory_ids']
        }
    
    def get_conversation_history(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
        offset: Optional[int] = 0
    ) -> Dict[str, Any]:
        """
        Get the conversation history for a specific conversation.
        
        Args:
            conversation_id: The ID of the conversation
            limit: Maximum number of messages to return (default: all)
            offset: Number of messages to skip from the beginning
            
        Returns:
            Dictionary with status and conversation history
        """
        memories = memory_repository.get_conversation_history(
            conversation_id=conversation_id,
            limit=limit,
            offset=offset
        )
        
        results = []
        for memory in memories:
            results.append({
                "text": memory.text,
                "speaker": memory.speaker,
                "timestamp": memory.timestamp.isoformat(),
                "memory_id": memory.id,
                "scope": memory.scope,
                "tags": memory.tags
            })
        
        return {
            "status": "OK",
            "conversation_id": conversation_id,
            "messages": results,
            "count": len(results)
        }
    
    def get_conversations_list(
        self,
        limit: int = 10,
        scope: Optional[str] = None,
        include_messages: bool = False
    ) -> Dict[str, Any]:
        """
        Get a list of recent conversations.
        
        Args:
            limit: Maximum number of conversations to return
            scope: Optional scope to filter by
            include_messages: Whether to include the first few messages
            
        Returns:
            Dictionary with status and conversations list
        """
        # Use default scope if none provided
        if not scope:
            scope = self.default_scope
        
        conversations = memory_repository.get_conversations_list(
            limit=limit,
            scope=scope,
            include_messages=include_messages
        )
        
        # Format datetime objects for JSON response
        for conv in conversations:
            conv["first_timestamp"] = conv["first_timestamp"].isoformat()
            conv["last_timestamp"] = conv["last_timestamp"].isoformat()
            if include_messages and "preview_messages" in conv:
                for msg in conv["preview_messages"]:
                    msg["timestamp"] = msg["timestamp"].isoformat()
        
        return {
            "status": "OK",
            "conversations": conversations,
            "count": len(conversations)
        }
    
    def create_conversation_summary(
        self,
        conversation_id: str,
        summary_text: Optional[str] = None,
        generate_summary: bool = True
    ) -> Dict[str, Any]:
        """
        Create a summary for a conversation.
        
        Args:
            conversation_id: The ID of the conversation to summarize
            summary_text: Optional pre-generated summary text
            generate_summary: Whether to auto-generate summary if not provided
            
        Returns:
            Dictionary with status and summary information
        """
        # Get the conversation messages
        memories = memory_repository.get_conversation_history(conversation_id)
        
        if not memories:
            return {
                "status": "ERROR",
                "message": f"No conversation found with ID {conversation_id}"
            }
        
        # Get the conversation scope
        scope = memories[0].scope
        
        # If no summary text is provided and generate_summary is True, 
        # generate a summary from the conversation
        generated = False
        if not summary_text and generate_summary:
            summary_text = self._generate_conversation_summary(memories)
            generated = True
        
        if not summary_text:
            return {
                "status": "ERROR",
                "message": "No summary text provided or generated"
            }
        
        # Create the summary object
        summary = SummaryMemory(
            conversation_id=conversation_id,
            summary_text=summary_text,
            scope=scope,
            tags=["summary"],
            time_range={
                "from": memories[0].timestamp,
                "to": memories[-1].timestamp
            },
            message_refs=[m.id for m in memories]  # Reference all messages
        )
        
        # Store the summary
        summary_id = memory_repository.store_summary(summary)
        
        return {
            "status": "OK",
            "summary_id": summary_id,
            "conversation_id": conversation_id,
            "summary_text": summary_text,
            "generated": generated
        }
    
    def get_conversation_summaries(
        self,
        conversation_id: Optional[str] = None,
        limit: int = 10,
        scope: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get summaries for conversations.
        
        Args:
            conversation_id: Optional specific conversation ID
            limit: Maximum number of summaries to return
            scope: Optional scope to filter by
            
        Returns:
            Dictionary with status and summaries
        """
        if conversation_id:
            # Get summaries for a specific conversation
            summaries = memory_repository.get_summaries_by_conversation(conversation_id)
        else:
            # Get latest summaries
            # Use default scope if none provided
            if not scope:
                scope = self.default_scope
                
            summaries = memory_repository.get_latest_conversation_summaries(
                limit=limit,
                scope=scope
            )
        
        results = []
        for summary in summaries:
            time_range = None
            if summary.time_range:
                time_range = {
                    "from": summary.time_range.get("from", "").isoformat() if isinstance(summary.time_range.get("from"), datetime) else summary.time_range.get("from"),
                    "to": summary.time_range.get("to", "").isoformat() if isinstance(summary.time_range.get("to"), datetime) else summary.time_range.get("to")
                }
                
            results.append({
                "summary_id": summary.id,
                "conversation_id": summary.conversation_id,
                "summary_text": summary.summary_text,
                "timestamp": summary.timestamp.isoformat(),
                "scope": summary.scope,
                "tags": summary.tags,
                "time_range": time_range,
                "message_count": len(summary.message_refs) if summary.message_refs else 0
            })
        
        return {
            "status": "OK",
            "summaries": results,
            "count": len(results)
        }
    
    def _generate_conversation_summary(self, memories: List[ConversationMemory]) -> str:
        """
        Generate a summary for a conversation.
        
        This is a placeholder implementation. In a production system, this would
        likely use an LLM or summarization algorithm.
        
        Args:
            memories: List of conversation memories to summarize
            
        Returns:
            Generated summary text
        """
        # This is a simple implementation that just extracts key points
        # A real implementation would use more sophisticated summarization
        
        # Count messages per speaker
        user_messages = [m for m in memories if m.speaker == "user"]
        assistant_messages = [m for m in memories if m.speaker == "assistant"]
        
        # Get time range
        start_time = memories[0].timestamp
        end_time = memories[-1].timestamp
        duration = end_time - start_time
        
        # Extract some content snippets (first user message, last assistant message)
        first_user_text = user_messages[0].text if user_messages else ""
        last_assistant_text = assistant_messages[-1].text if assistant_messages else ""
        
        # Build a simple summary
        summary = [
            f"Conversation with {len(user_messages)} user messages and {len(assistant_messages)} assistant responses.",
            f"Duration: {duration.total_seconds() / 60:.1f} minutes.",
            f"Started with: \"{first_user_text[:100]}{'...' if len(first_user_text) > 100 else ''}\"",
        ]
        
        if last_assistant_text:
            summary.append(f"Ended with: \"{last_assistant_text[:100]}{'...' if len(last_assistant_text) > 100 else ''}\"")
        
        return "\n".join(summary)
        
        # Note: In a real implementation, we would use an LLM to generate a proper summary
        # For example:
        # return llm_service.generate_summary(memories)


# Create a singleton instance
memory_service = MemoryService() 