"""
Memory repository for InfiniteMemoryMCP.

This module implements the repository pattern for memory operations,
providing CRUD operations for various memory types.
"""

import uuid
import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from ..db.mongo_manager import mongo_manager
from ..embedding.embedding_service import embedding_service
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
    
    def __init__(self):
        """Initialize the memory repository."""
        # Lock for thread-safe operations
        self.lock = threading.RLock()
        # Dictionary to track in-progress async operations
        self.pending_operations = {}
    
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
        memory_id = str(result.inserted_id)
        
        # Create an embedding for this memory (asynchronously if enabled)
        text = memory.text
        scope = memory.scope
        self._create_memory_embedding_async(
            text=text,
            source_collection="conversation_history",
            source_id=memory_id,
            scope=scope
        )
        
        # Return the inserted ID
        return memory_id
    
    def update_conversation_memory(self, memory: ConversationMemory) -> bool:
        """
        Update an existing conversation memory.
        
        Args:
            memory: The conversation memory to update
            
        Returns:
            True if update was successful
        """
        if not memory.id:
            logger.error("Cannot update memory: missing ID")
            return False
        
        collection = mongo_manager.get_collection("conversation_history")
        
        # Convert to dict for MongoDB
        memory_dict = dataclass_to_dict(memory)
        if "_id" in memory_dict:
            memory_id = memory_dict["_id"]
            # Remove _id from the update
            del memory_dict["_id"]
        else:
            memory_id = memory.id
        
        # Update the memory
        result = collection.update_one({"_id": memory_id}, {"$set": memory_dict})
        
        # Update the embedding for this memory
        text = memory.text
        scope = memory.scope
        self._update_memory_embedding_async(text, memory_id, scope)
        
        # Return success status
        return result.modified_count > 0
    
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
    
    def _create_memory_embedding(self, text: str, source_collection: str, 
                              source_id: str, scope: str) -> Optional[str]:
        """
        Create a memory embedding for the given text and add it to the index.
        
        Args:
            text: The text to generate embedding for
            source_collection: The collection the source document is in
            source_id: The ID of the source document
            scope: The scope of the memory
            
        Returns:
            The ID of the memory index item, or None if creation failed
        """
        try:
            # Generate the embedding
            embedding_vector = embedding_service.generate_embedding(text)
            
            # Create the memory index item
            index_item = MemoryIndexItem(
                embedding=embedding_vector,
                source_collection=source_collection,
                source_id=source_id,
                scope=scope,
                metadata={
                    "text_preview": text[:100] if len(text) > 100 else text,
                    "timestamp": datetime.now()
                }
            )
            
            # Store the index item
            index_id = self.store_memory_index(index_item)
            logger.info(f"Created embedding for memory {source_id} in index as {index_id}")
            
            return index_id
        
        except Exception as e:
            logger.error(f"Error creating memory embedding: {e}")
            return None
    
    def _create_memory_embedding_async(self, text: str, source_collection: str, 
                                   source_id: str, scope: str) -> None:
        """
        Create a memory embedding asynchronously.
        
        Args:
            text: The text to generate embedding for
            source_collection: The collection the source document is in
            source_id: The ID of the source document
            scope: The scope of the memory
        """
        try:
            # Generate the embedding asynchronously
            embedding_service.generate_embedding_async(
                text,
                self._handle_embedding_creation_callback,
                source_collection,
                source_id,
                scope
            )
            
            # Track this operation
            with self.lock:
                self.pending_operations[source_id] = "embedding_creation"
            
            logger.debug(f"Queued async embedding creation for memory {source_id}")
        
        except Exception as e:
            logger.error(f"Error queuing async embedding creation: {e}")
    
    def _handle_embedding_creation_callback(self, embedding_vector: List[float],
                                        source_collection: str, source_id: str, scope: str) -> None:
        """
        Callback for when an async embedding generation completes.
        
        Args:
            embedding_vector: The generated embedding
            source_collection: The collection the source document is in
            source_id: The ID of the source document
            scope: The scope of the memory
        """
        try:
            # Create the memory index item
            index_item = MemoryIndexItem(
                embedding=embedding_vector,
                source_collection=source_collection,
                source_id=source_id,
                scope=scope,
                metadata={
                    "text_preview": "",  # We don't have the text here
                    "timestamp": datetime.now()
                }
            )
            
            # Store the index item
            index_id = self.store_memory_index(index_item)
            logger.info(f"Created async embedding for memory {source_id} in index as {index_id}")
            
            # Remove from pending operations
            with self.lock:
                self.pending_operations.pop(source_id, None)
        
        except Exception as e:
            logger.error(f"Error in async embedding creation callback: {e}")
            # Remove from pending operations
            with self.lock:
                self.pending_operations.pop(source_id, None)
    
    def _update_memory_embedding(self, text: str, source_id: str, scope: str) -> bool:
        """
        Update the embedding for an existing memory item.
        
        Args:
            text: The new text to generate embedding for
            source_id: The ID of the source document
            scope: The scope of the memory
            
        Returns:
            True if update was successful
        """
        try:
            collection = mongo_manager.get_collection("memory_index")
            
            # Generate the new embedding
            embedding_vector = embedding_service.generate_embedding(text)
            
            # Update the existing index entry
            result = collection.update_one(
                {"source_id": source_id},
                {
                    "$set": {
                        "embedding": embedding_vector,
                        "scope": scope,
                        "metadata.text_preview": text[:100] if len(text) > 100 else text,
                        "metadata.updated_at": datetime.now()
                    }
                }
            )
            
            if result.matched_count == 0:
                # No existing index entry, create a new one
                logger.info(f"No existing embedding found for {source_id}, creating new one")
                # Determine source collection from context
                source_collection = "conversation_history"  # Default
                self._create_memory_embedding(text, source_collection, source_id, scope)
                return True
            
            logger.info(f"Updated embedding for memory {source_id}")
            return result.modified_count > 0
        
        except Exception as e:
            logger.error(f"Error updating memory embedding: {e}")
            return False
    
    def _update_memory_embedding_async(self, text: str, source_id: str, scope: str) -> None:
        """
        Update the embedding for an existing memory item asynchronously.
        
        Args:
            text: The new text to generate embedding for
            source_id: The ID of the source document
            scope: The scope of the memory
        """
        try:
            # Generate the embedding asynchronously
            embedding_service.generate_embedding_async(
                text,
                self._handle_embedding_update_callback,
                text,
                source_id,
                scope
            )
            
            # Track this operation
            with self.lock:
                self.pending_operations[source_id] = "embedding_update"
            
            logger.debug(f"Queued async embedding update for memory {source_id}")
        
        except Exception as e:
            logger.error(f"Error queuing async embedding update: {e}")
    
    def _handle_embedding_update_callback(self, embedding_vector: List[float],
                                      text: str, source_id: str, scope: str) -> None:
        """
        Callback for when an async embedding update completes.
        
        Args:
            embedding_vector: The generated embedding
            text: The text that was embedded
            source_id: The ID of the source document
            scope: The scope of the memory
        """
        try:
            collection = mongo_manager.get_collection("memory_index")
            
            # Update the existing index entry
            result = collection.update_one(
                {"source_id": source_id},
                {
                    "$set": {
                        "embedding": embedding_vector,
                        "scope": scope,
                        "metadata.text_preview": text[:100] if len(text) > 100 else text,
                        "metadata.updated_at": datetime.now()
                    }
                }
            )
            
            if result.matched_count == 0:
                # No existing index entry, create a new one
                logger.info(f"No existing embedding found for {source_id}, creating new one")
                # Determine source collection from context
                source_collection = "conversation_history"  # Default
                
                # Create a new memory index item
                index_item = MemoryIndexItem(
                    embedding=embedding_vector,
                    source_collection=source_collection,
                    source_id=source_id,
                    scope=scope,
                    metadata={
                        "text_preview": text[:100] if len(text) > 100 else text,
                        "timestamp": datetime.now()
                    }
                )
                
                # Store the index item
                self.store_memory_index(index_item)
            else:
                logger.info(f"Updated embedding for memory {source_id}")
            
            # Remove from pending operations
            with self.lock:
                self.pending_operations.pop(source_id, None)
        
        except Exception as e:
            logger.error(f"Error in async embedding update callback: {e}")
            # Remove from pending operations
            with self.lock:
                self.pending_operations.pop(source_id, None)
    
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
    
    def get_conversations_by_semantic_search(
        self,
        query_text: str,
        scope: Optional[str] = None,
        top_k: int = 5,
        similarity_threshold: float = 0.3
    ) -> List[Tuple[ConversationMemory, float]]:
        """
        Get conversation memories by semantic similarity to query.
        
        Args:
            query_text: The text to search for semantically
            scope: Optional scope to filter by
            top_k: Number of top results to return
            similarity_threshold: Minimum similarity score to include
            
        Returns:
            A list of tuples (memory, similarity_score)
        """
        # Get query embedding
        query_embedding = embedding_service.generate_embedding(query_text)
        
        # Get memory indices matching our filters
        memory_index_collection = mongo_manager.get_collection("memory_index")
        
        # Build query
        query = {
            "source_collection": "conversation_history"
        }
        
        # Add scope filter if provided
        if scope:
            query["scope"] = scope
        
        # Get all candidate memory indices
        index_items = list(memory_index_collection.find(query))
        
        if not index_items:
            logger.info(f"No memory index items found for scope {scope}")
            return []
        
        # Extract embeddings and IDs
        candidate_embeddings = [item["embedding"] for item in index_items]
        source_ids = [item["source_id"] for item in index_items]
        
        # Find most similar embeddings
        most_similar_indices = embedding_service.find_most_similar(
            query_embedding,
            candidate_embeddings,
            top_k=top_k,
            threshold=similarity_threshold
        )
        
        # If no similar embeddings found, return empty list
        if not most_similar_indices:
            return []
        
        # Calculate similarity scores for the most similar items
        similarity_scores = []
        for idx in most_similar_indices:
            score = embedding_service.compute_similarity(
                query_embedding, 
                candidate_embeddings[idx]
            )
            similarity_scores.append(score)
        
        # Get the actual memory items
        conversation_collection = mongo_manager.get_collection("conversation_history")
        result_items = []
        
        for i, idx in enumerate(most_similar_indices):
            memory_id = source_ids[idx]
            memory_dict = conversation_collection.find_one({"_id": memory_id})
            
            if memory_dict:
                memory = dict_to_dataclass(memory_dict, ConversationMemory)
                result_items.append((memory, similarity_scores[i]))
        
        # Sort by similarity score (descending)
        result_items.sort(key=lambda x: x[1], reverse=True)
        
        return result_items
    
    def perform_hybrid_search(
        self,
        query_text: str,
        scope: Optional[str] = None,
        top_k: int = 5,
        similarity_threshold: float = 0.3
    ) -> List[Tuple[ConversationMemory, float]]:
        """
        Perform a hybrid search using both semantic and keyword matching.
        
        Args:
            query_text: The text to search for
            scope: Optional scope to filter by
            top_k: Number of top results to return
            similarity_threshold: Minimum similarity score to include
            
        Returns:
            A list of tuples (memory, similarity_score)
        """
        # Get semantic search results
        semantic_results = self.get_conversations_by_semantic_search(
            query_text, scope, top_k, similarity_threshold
        )
        
        # Get keyword search results
        keyword_results = self.get_conversations_by_text_search(query_text, scope)
        
        # Convert keyword results to same format as semantic results
        keyword_result_tuples = [(memory, 1.0) for memory in keyword_results]
        
        # Combine results, prioritizing exact matches
        combined_results = keyword_result_tuples + [
            result for result in semantic_results 
            if result[0].id not in [k[0].id for k in keyword_result_tuples]
        ]
        
        # Deduplicate and sort by similarity score
        seen_ids = set()
        unique_results = []
        for memory, score in combined_results:
            if memory.id not in seen_ids:
                seen_ids.add(memory.id)
                unique_results.append((memory, score))
        
        # Sort by score (highest first)
        unique_results.sort(key=lambda x: x[1], reverse=True)
        
        # Return top_k
        return unique_results[:top_k]
    
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
        
        # Delete the memory's embedding
        self._delete_memory_embedding(memory_id)
        
        # Check if a memory was deleted
        return result.deleted_count > 0
    
    def _delete_memory_embedding(self, source_id: str) -> bool:
        """
        Delete the embedding for a memory.
        
        Args:
            source_id: The ID of the source document
            
        Returns:
            True if the embedding was deleted
        """
        collection = mongo_manager.get_collection("memory_index")
        
        # Delete the embedding
        result = collection.delete_one({"source_id": source_id})
        
        # Return success status
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
        
        # Get IDs of memories to delete (for embedding cleanup)
        memory_dicts = list(collection.find({"scope": scope}, {"_id": 1}))
        memory_ids = [mem["_id"] for mem in memory_dicts]
        
        # Delete memories by scope
        result = collection.delete_many({"scope": scope})
        
        # Also delete embeddings
        memory_index = mongo_manager.get_collection("memory_index")
        memory_index.delete_many({"scope": scope})
        
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
        
        # Get IDs of memories to delete (for embedding cleanup)
        memory_dicts = list(collection.find({"tags": tag}, {"_id": 1}))
        memory_ids = [mem["_id"] for mem in memory_dicts]
        
        # Delete memories by tag
        result = collection.delete_many({"tags": tag})
        
        # Also delete their embeddings
        memory_index = mongo_manager.get_collection("memory_index")
        for memory_id in memory_ids:
            memory_index.delete_one({"source_id": memory_id})
        
        # Return the number of memories deleted
        return result.deleted_count
    
    def create_scope(self, scope: MemoryScope) -> str:
        """
        Create a new memory scope.
        
        Args:
            scope: The scope to create
            
        Returns:
            The ID of the created scope
        """
        collection = mongo_manager.get_collection("metadata_scopes")
        
        # Convert to dict for MongoDB
        scope_dict = dataclass_to_dict(scope)
        
        # Check if scope with this name already exists
        existing = collection.find_one({"scope_name": scope.scope_name})
        if existing:
            return str(existing["_id"])
        
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
        Get memory statistics.
        
        Returns:
            Dictionary with memory statistics
        """
        stats = {
            "total_memories": 0,
            "scopes": {},
            "total_embeddings": 0
        }
        
        # Get conversation memories count
        conversation_collection = mongo_manager.get_collection("conversation_history")
        stats["total_memories"] = conversation_collection.count_documents({})
        
        # Get memory count by scope
        scopes = self.get_all_scopes()
        for scope in scopes:
            count = conversation_collection.count_documents({"scope": scope.scope_name})
            stats["scopes"][scope.scope_name] = count
        
        # Get embedding count
        memory_index = mongo_manager.get_collection("memory_index")
        stats["total_embeddings"] = memory_index.count_documents({})
        
        return stats
    
    def get_conversation_history(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
        offset: Optional[int] = 0
    ) -> List[ConversationMemory]:
        """
        Get the conversation history for a specific conversation.
        
        Args:
            conversation_id: The ID of the conversation
            limit: Maximum number of messages to return (default: all)
            offset: Number of messages to skip from the beginning
            
        Returns:
            List of conversation memories in chronological order
        """
        collection = mongo_manager.get_collection("conversation_history")
        
        # Build the query
        query = {"conversation_id": conversation_id}
        
        # Set up sort and pagination
        cursor = collection.find(query).sort("timestamp", 1)
        
        # Apply offset and limit if provided
        if offset:
            cursor = cursor.skip(offset)
        if limit:
            cursor = cursor.limit(limit)
        
        # Convert to ConversationMemory objects
        memories = [dict_to_dataclass(doc, ConversationMemory) for doc in cursor]
        
        return memories
    
    def store_conversation_batch(
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
            Dictionary with conversation_id and list of memory_ids
        """
        # Generate conversation_id if not provided
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
        
        # Default scope to "Global" if not provided
        if not scope:
            scope = "Global"
        
        memory_ids = []
        
        # Store each message in the batch
        for message in messages:
            memory = ConversationMemory(
                conversation_id=conversation_id,
                speaker=message.get("speaker", "user"),
                text=message.get("text", ""),
                scope=scope,
                tags=message.get("tags", []),
                timestamp=message.get("timestamp", datetime.now())
            )
            
            memory_id = self.store_conversation_memory(memory)
            memory_ids.append(memory_id)
        
        return {
            "conversation_id": conversation_id,
            "memory_ids": memory_ids
        }
    
    def store_summary(self, summary: SummaryMemory) -> str:
        """
        Store a conversation summary.
        
        Args:
            summary: The summary memory to store
            
        Returns:
            The ID of the stored summary
        """
        collection = mongo_manager.get_collection("summaries")
        
        # Convert to dict for MongoDB
        summary_dict = dataclass_to_dict(summary)
        
        # Insert the summary
        result = collection.insert_one(summary_dict)
        summary_id = str(result.inserted_id)
        
        # Create an embedding for this summary (asynchronously if enabled)
        text = summary.summary_text
        scope = summary.scope
        self._create_memory_embedding_async(
            text=text,
            source_collection="summaries",
            source_id=summary_id,
            scope=scope
        )
        
        # Return the inserted ID
        return summary_id
    
    def get_summaries_by_conversation(self, conversation_id: str) -> List[SummaryMemory]:
        """
        Get summaries for a specific conversation.
        
        Args:
            conversation_id: The ID of the conversation
            
        Returns:
            List of summary memories
        """
        collection = mongo_manager.get_collection("summaries")
        
        # Build the query
        query = {"conversation_id": conversation_id}
        
        # Execute the query
        cursor = collection.find(query).sort("timestamp", -1)
        
        # Convert to SummaryMemory objects
        summaries = [dict_to_dataclass(doc, SummaryMemory) for doc in cursor]
        
        return summaries
    
    def get_latest_conversation_summaries(
        self,
        limit: int = 10,
        scope: Optional[str] = None
    ) -> List[SummaryMemory]:
        """
        Get the latest conversation summaries.
        
        Args:
            limit: Maximum number of summaries to return
            scope: Optional scope to filter by
            
        Returns:
            List of summary memories
        """
        collection = mongo_manager.get_collection("summaries")
        
        # Build the query
        query = {}
        if scope:
            query["scope"] = scope
        
        # Execute the query
        cursor = collection.find(query).sort("timestamp", -1).limit(limit)
        
        # Convert to SummaryMemory objects
        summaries = [dict_to_dataclass(doc, SummaryMemory) for doc in cursor]
        
        return summaries
    
    def get_conversations_list(
        self,
        limit: int = 10,
        scope: Optional[str] = None,
        include_messages: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get a list of recent conversations.
        
        Args:
            limit: Maximum number of conversations to return
            scope: Optional scope to filter by
            include_messages: Whether to include the first few messages
            
        Returns:
            List of conversation info dictionaries
        """
        collection = mongo_manager.get_collection("conversation_history")
        
        # Build the pipeline for aggregation
        pipeline = []
        
        # Match by scope if provided
        if scope:
            pipeline.append({"$match": {"scope": scope}})
        
        # Group by conversation_id and get first and last messages
        pipeline.append({
            "$group": {
                "_id": "$conversation_id",
                "conversation_id": {"$first": "$conversation_id"},
                "first_timestamp": {"$min": "$timestamp"},
                "last_timestamp": {"$max": "$timestamp"},
                "message_count": {"$sum": 1},
                "scope": {"$first": "$scope"},
                "first_message": {"$first": {"text": "$text", "speaker": "$speaker"}},
            }
        })
        
        # Sort by most recent activity
        pipeline.append({"$sort": {"last_timestamp": -1}})
        
        # Limit results
        pipeline.append({"$limit": limit})
        
        # Execute the aggregation
        conversations = list(collection.aggregate(pipeline))
        
        # If include_messages is True, fetch the first few messages for each conversation
        if include_messages:
            for conv in conversations:
                conv_id = conv["conversation_id"]
                messages = self.get_conversation_history(conv_id, limit=3)
                conv["preview_messages"] = [
                    {"text": msg.text, "speaker": msg.speaker, "timestamp": msg.timestamp} 
                    for msg in messages
                ]
        
        return conversations


# Create a singleton instance
memory_repository = MemoryRepository() 