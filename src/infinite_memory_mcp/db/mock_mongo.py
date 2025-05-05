"""
Mock MongoDB implementation for testing.

This module provides a mock implementation of the MongoDBManager
that can be used for testing without a real MongoDB instance.
"""

import time
from typing import Dict, List, Any, Optional, Set, Union

from ..utils.logging import logger


class MockCollection:
    """
    Mock implementation of a MongoDB collection.
    """
    
    def __init__(self, name: str):
        """Initialize the mock collection."""
        self.name = name
        self.documents: List[Dict[str, Any]] = []
        self.indexes: List[Dict[str, Any]] = []
    
    def insert_one(self, document: Dict[str, Any]) -> Any:
        """
        Insert a document into the collection.
        
        Args:
            document: The document to insert
            
        Returns:
            A mock InsertOneResult
        """
        # Clone the document to simulate MongoDB's behavior
        doc_copy = document.copy()
        
        # Add _id if not present
        if "_id" not in doc_copy:
            doc_copy["_id"] = f"mock_id_{len(self.documents)}"
        
        self.documents.append(doc_copy)
        return MockInsertOneResult(doc_copy["_id"])
    
    def find_one(self, filter: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Find a document matching the filter.
        
        Args:
            filter: The filter to apply
            
        Returns:
            The first matching document, or None if no match is found
        """
        for doc in self.documents:
            if self._matches_filter(doc, filter):
                return doc.copy()
        return None
    
    def find(self, filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Find documents matching the filter.
        
        Args:
            filter: The filter to apply
            
        Returns:
            A list of matching documents
        """
        if filter is None:
            filter = {}
        
        return [doc.copy() for doc in self.documents if self._matches_filter(doc, filter)]
    
    def create_index(self, keys, unique: bool = False) -> str:
        """
        Create an index on the collection.
        
        Args:
            keys: The keys to index, can be a string or a list of tuples
            unique: Whether the index should enforce uniqueness
            
        Returns:
            A string representing the index name
        """
        if isinstance(keys, str):
            keys = [(keys, 1)]
        
        index_info = {
            "keys": keys,
            "unique": unique,
            "name": f"mock_index_{len(self.indexes)}"
        }
        
        self.indexes.append(index_info)
        return index_info["name"]
    
    def _matches_filter(self, document: Dict[str, Any], filter: Dict[str, Any]) -> bool:
        """
        Check if a document matches a filter.
        
        Args:
            document: The document to check
            filter: The filter to apply
            
        Returns:
            True if the document matches, False otherwise
        """
        for key, value in filter.items():
            if key not in document:
                return False
            
            if document[key] != value:
                return False
        
        return True


class MockInsertOneResult:
    """
    Mock implementation of a MongoDB InsertOneResult.
    """
    
    def __init__(self, inserted_id: Any):
        """Initialize the mock InsertOneResult."""
        self.inserted_id = inserted_id


class MockDatabase:
    """
    Mock implementation of a MongoDB database.
    """
    
    def __init__(self, name: str):
        """Initialize the mock database."""
        self.name = name
        self.collections: Dict[str, MockCollection] = {}
    
    def __getitem__(self, collection_name: str) -> MockCollection:
        """
        Get a collection by name.
        
        Args:
            collection_name: The name of the collection to get
            
        Returns:
            The collection
        """
        if collection_name not in self.collections:
            self.collections[collection_name] = MockCollection(collection_name)
        
        return self.collections[collection_name]
    
    def list_collection_names(self) -> List[str]:
        """
        Get a list of collection names.
        
        Returns:
            A list of collection names
        """
        return list(self.collections.keys())
    
    def create_collection(self, name: str) -> MockCollection:
        """
        Create a new collection.
        
        Args:
            name: The name of the collection to create
            
        Returns:
            The created collection
        """
        if name not in self.collections:
            self.collections[name] = MockCollection(name)
        
        return self.collections[name]


class MockMongoClient:
    """
    Mock implementation of a MongoDB client.
    """
    
    def __init__(self, uri: str, **kwargs):
        """
        Initialize the mock MongoDB client.
        
        Args:
            uri: The URI to connect to (ignored in mock)
            **kwargs: Additional arguments (ignored in mock)
        """
        self.uri = uri
        self.databases: Dict[str, MockDatabase] = {}
        self.admin = MockDatabase("admin")
    
    def __getitem__(self, db_name: str) -> MockDatabase:
        """
        Get a database by name.
        
        Args:
            db_name: The name of the database to get
            
        Returns:
            The database
        """
        if db_name not in self.databases:
            self.databases[db_name] = MockDatabase(db_name)
        
        return self.databases[db_name]
    
    def close(self) -> None:
        """Close the client connection (no-op in mock)."""
        pass


class MockMongoDBManager:
    """
    Mock implementation of the MongoDBManager for testing.
    
    This class simulates the behavior of MongoDBManager without
    requiring a real MongoDB instance.
    """
    
    def __init__(self):
        """Initialize the mock MongoDB manager."""
        self.client: Optional[MockMongoClient] = None
        self.db: Optional[MockDatabase] = None
        self.mongodb_process = None
        self.mode: str = "mock"
        self.uri: str = "mongodb://localhost:27017/claude_memory_mock"
        self.db_name: str = "claude_memory_mock"
        self.db_path: str = "/tmp/claude_memory_mock"
    
    def start(self) -> bool:
        """
        Start the mock MongoDB connection.
        
        Returns:
            True, always succeeds
        """
        logger.info("Starting mock MongoDB connection")
        
        # Create mock client and db
        self.client = MockMongoClient(self.uri)
        self.db = self.client[self.db_name]
        
        # Setup collections and indexes
        self._setup_collections()
        
        logger.info("Mock MongoDB connection started successfully")
        return True
    
    def stop(self) -> None:
        """Stop the mock MongoDB connection."""
        logger.info("Stopping mock MongoDB connection")
        
        self.client = None
        self.db = None
    
    def _setup_collections(self) -> None:
        """
        Setup collections and indexes for the mock MongoDB.
        """
        # Create collections
        collections = {
            "conversation_history",
            "summaries",
            "user_profile",
            "memory_index",
            "metadata_scopes"
        }
        
        for collection in collections:
            self.db.create_collection(collection)
        
        # Setup indexes
        self._setup_indexes()
        
        # Initialize default data
        self._initialize_default_data()
    
    def _setup_indexes(self) -> None:
        """Create indexes for the mock collections."""
        # Conversation history indexes
        conversation_history = self.db["conversation_history"]
        conversation_history.create_index([("conversation_id", 1), ("timestamp", 1)])
        conversation_history.create_index("scope")
        conversation_history.create_index("tags")
        conversation_history.create_index("timestamp")
        
        # Summaries indexes
        summaries = self.db["summaries"]
        summaries.create_index("conversation_id")
        summaries.create_index("topic_id")
        summaries.create_index("scope")
        summaries.create_index("tags")
        
        # Memory index indexes
        memory_index = self.db["memory_index"]
        memory_index.create_index("source_id")
        memory_index.create_index("scope")
        
        # Metadata/scopes indexes
        metadata_scopes = self.db["metadata_scopes"]
        metadata_scopes.create_index("scope_name", unique=True)
    
    def _initialize_default_data(self) -> None:
        """
        Initialize default data in the mock database.
        """
        # Add default scope
        self.db["metadata_scopes"].insert_one({
            "type": "scope",
            "scope_name": "Global",
            "description": "Default global memory scope",
            "created_at": time.time(),
            "active": True
        })
    
    def get_collection(self, collection_name: str) -> Optional[MockCollection]:
        """
        Get a MongoDB collection.
        
        Args:
            collection_name: Name of the collection to get.
            
        Returns:
            The MongoDB collection, or None if not connected.
        """
        if not self.db:
            logger.error("Database not connected")
            return None
        return self.db[collection_name] 