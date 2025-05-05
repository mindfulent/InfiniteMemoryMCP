"""
Memory repository for InfiniteMemoryMCP.

This module implements the repository pattern for memory operations,
providing CRUD operations for various memory types.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from ..db.mongo_manager import mongo_manager
from ..utils.logging import logger
from .models import (ConversationMemory, MemoryBase, MemoryIndexItem,
                     MemoryScope, SummaryMemory, UserProfileItem,
                     dataclass_to_dict, dict_to_dataclass)


class MemoryRepository:
    """
    Repository for memory operations.
    
    Provides methods for storing, retrieving, and manipulating memory items
    in the MongoDB database.
    """
    
    def store_conversation_memory(self, memory: ConversationMemory) -> str:
        """
        Store a conversation memory.
        
        Args:
            memory: The conversation memory to store
            
        Returns:
            The ID of the stored memory
        """
        collection = mongo_manager.get_collection("conversation_history")
        
        # Convert to dict for MongoDB
        memory_dict = dataclass_to_dict(memory)
        
        # If no conversation_id is provided, generate one
        if not memory.conversation_id:
            memory_dict["conversation_id"] = str(uuid.uuid4())
        
        # Insert the memory
        result = collection.insert_one(memory_dict)
        
        # Return the inserted ID
        return str(result.inserted_id)
    
    def store_memory_index(self, index_item: MemoryIndexItem) -> str:
        """
        Store a memory index item.
        
        Args:
            index_item: The memory index item to store
            
        Returns:
            The ID of the stored index item
        """
        collection = mongo_manager.get_collection("memory_index")
        
        # Convert to dict for MongoDB
        index_dict = dataclass_to_dict(index_item)
        
        # Insert the index item
        result = collection.insert_one(index_dict)
        
        # Return the inserted ID
        return str(result.inserted_id)
    
    def get_conversation_memory(self, memory_id: str) -> Optional[ConversationMemory]:
        """
        Get a conversation memory by ID.
        
        Args:
            memory_id: The ID of the memory to retrieve
            
        Returns:
            The conversation memory, or None if not found
        """
        collection = mongo_manager.get_collection("conversation_history")
        
        # Find the memory by ID
        memory_dict = collection.find_one({"_id": memory_id})
        
        if not memory_dict:
            return None
        
        # Convert to ConversationMemory
        return dict_to_dataclass(memory_dict, ConversationMemory)
    
    def get_conversations_by_scope(self, scope: str) -> List[ConversationMemory]:
        """
        Get all conversation memories in a specific scope.
        
        Args:
            scope: The scope to retrieve memories from
            
        Returns:
            A list of conversation memories
        """
        collection = mongo_manager.get_collection("conversation_history")
        
        # Find memories by scope
        memory_dicts = collection.find({"scope": scope})
        
        # Convert to ConversationMemory objects
        return [dict_to_dataclass(memory_dict, ConversationMemory) 
                for memory_dict in memory_dicts]
    
    def get_conversations_by_tag(self, tag: str) -> List[ConversationMemory]:
        """
        Get all conversation memories with a specific tag.
        
        Args:
            tag: The tag to search for
            
        Returns:
            A list of conversation memories
        """
        collection = mongo_manager.get_collection("conversation_history")
        
        # Find memories by tag
        memory_dicts = collection.find({"tags": tag})
        
        # Convert to ConversationMemory objects
        return [dict_to_dataclass(memory_dict, ConversationMemory)
                for memory_dict in memory_dicts]
    
    def get_conversations_by_time_range(
        self, 
        start_time: datetime, 
        end_time: datetime,
        scope: Optional[str] = None
    ) -> List[ConversationMemory]:
        """
        Get all conversation memories within a time range.
        
        Args:
            start_time: The start of the time range
            end_time: The end of the time range
            scope: Optional scope to filter by
            
        Returns:
            A list of conversation memories
        """
        collection = mongo_manager.get_collection("conversation_history")
        
        # Build query
        query = {
            "timestamp": {
                "$gte": start_time,
                "$lte": end_time
            }
        }
        
        # Add scope filter if provided
        if scope:
            query["scope"] = scope
        
        # Find memories by time range
        memory_dicts = collection.find(query)
        
        # Convert to ConversationMemory objects
        return [dict_to_dataclass(memory_dict, ConversationMemory)
                for memory_dict in memory_dicts]
    
    def get_conversations_by_text_search(
        self, 
        search_text: str,
        scope: Optional[str] = None
    ) -> List[ConversationMemory]:
        """
        Get all conversation memories matching a text search.
        
        This performs a basic text search (not semantic).
        
        Args:
            search_text: The text to search for
            scope: Optional scope to filter by
            
        Returns:
            A list of conversation memories
        """
        collection = mongo_manager.get_collection("conversation_history")
        
        # Build query (simple regex search)
        query = {
            "text": {"$regex": search_text, "$options": "i"}
        }
        
        # Add scope filter if provided
        if scope:
            query["scope"] = scope
        
        # Find memories by text search
        memory_dicts = collection.find(query)
        
        # Convert to ConversationMemory objects
        return [dict_to_dataclass(memory_dict, ConversationMemory)
                for memory_dict in memory_dicts]
    
    def delete_memory(self, memory_id: str) -> bool:
        """
        Delete a memory by ID.
        
        Args:
            memory_id: The ID of the memory to delete
            
        Returns:
            True if the memory was deleted, False otherwise
        """
        collection = mongo_manager.get_collection("conversation_history")
        
        # Delete the memory
        result = collection.delete_one({"_id": memory_id})
        
        # Check if a memory was deleted
        return result.deleted_count > 0
    
    def delete_memories_by_scope(self, scope: str) -> int:
        """
        Delete all memories in a specific scope.
        
        Args:
            scope: The scope to delete memories from
            
        Returns:
            The number of memories deleted
        """
        collection = mongo_manager.get_collection("conversation_history")
        
        # Delete memories by scope
        result = collection.delete_many({"scope": scope})
        
        # Return the number of memories deleted
        return result.deleted_count
    
    def delete_memories_by_tag(self, tag: str) -> int:
        """
        Delete all memories with a specific tag.
        
        Args:
            tag: The tag to delete memories for
            
        Returns:
            The number of memories deleted
        """
        collection = mongo_manager.get_collection("conversation_history")
        
        # Delete memories by tag
        result = collection.delete_many({"tags": tag})
        
        # Return the number of memories deleted
        return result.deleted_count
    
    def create_scope(self, scope: MemoryScope) -> str:
        """
        Create a new memory scope.
        
        Args:
            scope: The memory scope to create
            
        Returns:
            The ID of the created scope
        """
        collection = mongo_manager.get_collection("metadata_scopes")
        
        # Convert to dict for MongoDB
        scope_dict = dataclass_to_dict(scope)
        
        # Check if scope already exists
        existing_scope = collection.find_one({"scope_name": scope.scope_name})
        if existing_scope:
            # Return existing scope ID
            return str(existing_scope["_id"])
        
        # Insert the scope
        result = collection.insert_one(scope_dict)
        
        # Return the inserted ID
        return str(result.inserted_id)
    
    def get_scope(self, scope_name: str) -> Optional[MemoryScope]:
        """
        Get a memory scope by name.
        
        Args:
            scope_name: The name of the scope to retrieve
            
        Returns:
            The memory scope, or None if not found
        """
        collection = mongo_manager.get_collection("metadata_scopes")
        
        # Find the scope by name
        scope_dict = collection.find_one({"scope_name": scope_name})
        
        if not scope_dict:
            return None
        
        # Convert to MemoryScope
        return dict_to_dataclass(scope_dict, MemoryScope)
    
    def get_all_scopes(self) -> List[MemoryScope]:
        """
        Get all memory scopes.
        
        Returns:
            A list of all memory scopes
        """
        collection = mongo_manager.get_collection("metadata_scopes")
        
        # Find all scopes
        scope_dicts = collection.find({"type": "scope"})
        
        # Convert to MemoryScope objects
        return [dict_to_dataclass(scope_dict, MemoryScope)
                for scope_dict in scope_dicts]
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the memory database.
        
        Returns:
            A dictionary containing memory statistics
        """
        db = mongo_manager.db
        
        # Get total number of memories
        total_memories = db.conversation_history.count_documents({})
        
        # Get number of conversations
        conversation_ids = db.conversation_history.distinct("conversation_id")
        conversation_count = len(conversation_ids)
        
        # Get counts by scope
        scopes = {}
        for scope in db.metadata_scopes.find({"type": "scope"}):
            scope_name = scope["scope_name"]
            scope_count = db.conversation_history.count_documents({"scope": scope_name})
            scopes[scope_name] = scope_count
        
        # Get last backup time (placeholder for now)
        last_backup = None
        
        # Get approximate database size
        db_size_mb = 0
        for collection_name in db.list_collection_names():
            collection_stats = db.command("collStats", collection_name)
            db_size_mb += collection_stats.get("size", 0) / (1024 * 1024)
        
        return {
            "total_memories": total_memories,
            "conversation_count": conversation_count,
            "scopes": scopes,
            "last_backup": last_backup,
            "db_size_mb": round(db_size_mb, 2)
        }


# Create a singleton instance
memory_repository = MemoryRepository() 