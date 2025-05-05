"""
MongoDB connection management for InfiniteMemoryMCP.
"""

import os
import signal
import subprocess
import time
from typing import Dict, List, Optional, Union

import pymongo
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from ..utils.config import config_manager
from ..utils.logging import logger


class MongoDBManager:
    """
    Manages MongoDB connections and operations.
    
    This class handles both embedded and external MongoDB modes,
    managing the lifecycle of the MongoDB process in embedded mode.
    """

    def __init__(self):
        """Initialize the MongoDB manager."""
        self.client: Optional[MongoClient] = None
        self.db: Optional[Database] = None
        self.mongodb_process: Optional[subprocess.Popen] = None
        self.mode: str = config_manager.get("database.mode", "embedded")
        self.uri: str = config_manager.get("database.uri", "mongodb://localhost:27017/claude_memory")
        self.db_name: str = self.uri.split("/")[-1]
        self.db_path: str = config_manager.get_database_path()
        
        # Ensure MongoDB data directory exists
        os.makedirs(self.db_path, exist_ok=True)
    
    def start(self) -> bool:
        """
        Start the MongoDB connection or server.
        
        In 'embedded' mode, this will start a MongoDB server process.
        In 'external' mode, this will connect to an existing MongoDB server.
        
        Returns:
            True if successful, False otherwise.
        """
        if self.mode == "embedded":
            success = self._start_embedded_mongodb()
            if not success:
                logger.error("Failed to start embedded MongoDB")
                return False
        
        try:
            # Connect to MongoDB
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=5000)
            
            # Test the connection
            self.client.admin.command('ping')
            
            # Get the database
            self.db = self.client[self.db_name]
            
            logger.info(f"Connected to MongoDB database: {self.db_name}")
            
            # Setup collections and indexes
            self._setup_collections()
            
            return True
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"MongoDB connection failed: {e}")
            return False
    
    def _start_embedded_mongodb(self) -> bool:
        """
        Start an embedded MongoDB server process.
        
        Returns:
            True if successful, False otherwise.
        """
        try:
            cmd = [
                "mongod",
                "--dbpath", self.db_path,
                "--port", "27017",
                "--bind_ip", "127.0.0.1",
                "--nojournaling"  # For faster startup in dev environment
            ]
            
            logger.info(f"Starting embedded MongoDB: {' '.join(cmd)}")
            
            # Start MongoDB process
            self.mongodb_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            # Give MongoDB time to start
            time.sleep(2)
            
            # Check if process is still running
            if self.mongodb_process.poll() is not None:
                # Process exited
                stdout, stderr = self.mongodb_process.communicate()
                logger.error(f"MongoDB process failed to start: {stderr}")
                return False
            
            logger.info("Embedded MongoDB started successfully")
            return True
        except Exception as e:
            logger.error(f"Error starting embedded MongoDB: {e}")
            return False
    
    def stop(self) -> None:
        """Stop the MongoDB connection or server."""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
            logger.info("MongoDB connection closed")
        
        if self.mongodb_process:
            logger.info("Stopping embedded MongoDB")
            self.mongodb_process.terminate()
            try:
                self.mongodb_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("MongoDB process did not terminate gracefully, killing")
                self.mongodb_process.kill()
            self.mongodb_process = None
    
    def _setup_collections(self) -> None:
        """
        Setup collections and indexes required by InfiniteMemoryMCP.
        
        Creates all necessary collections and indexes if they don't exist.
        """
        # Create collections if they don't exist
        collections = {
            "conversation_history",
            "summaries",
            "user_profile",
            "memory_index",
            "metadata_scopes"
        }
        
        existing_collections = set(self.db.list_collection_names())
        for collection in collections:
            if collection not in existing_collections:
                self.db.create_collection(collection)
                logger.info(f"Created collection: {collection}")
        
        # Setup indexes
        self._setup_indexes()
        
        # Initialize default data if needed
        self._initialize_default_data()
    
    def _setup_indexes(self) -> None:
        """Create indexes for efficient queries."""
        # Conversation history indexes
        conversation_history = self.db.conversation_history
        conversation_history.create_index([("conversation_id", pymongo.ASCENDING), 
                                          ("timestamp", pymongo.ASCENDING)])
        conversation_history.create_index("scope")
        conversation_history.create_index("tags")
        conversation_history.create_index("timestamp")
        
        # Summaries indexes
        summaries = self.db.summaries
        summaries.create_index("conversation_id")
        summaries.create_index("topic_id")
        summaries.create_index("scope")
        summaries.create_index("tags")
        
        # Memory index indexes
        memory_index = self.db.memory_index
        memory_index.create_index("source_id")
        memory_index.create_index("scope")
        
        # Metadata/scopes indexes
        metadata_scopes = self.db.metadata_scopes
        metadata_scopes.create_index("scope_name", unique=True)
        
        logger.info("MongoDB indexes created/verified")
    
    def _initialize_default_data(self) -> None:
        """
        Initialize default data in the database if needed.
        
        Adds the default Global scope if it doesn't exist.
        """
        default_scope = config_manager.get("memory.default_scope", "Global")
        
        # Check if the default scope exists
        scope_exists = self.db.metadata_scopes.find_one({"scope_name": default_scope})
        if not scope_exists:
            # Create the default scope
            self.db.metadata_scopes.insert_one({
                "type": "scope",
                "scope_name": default_scope,
                "description": "Default global memory scope",
                "created_at": time.time(),
                "active": True
            })
            logger.info(f"Created default scope: {default_scope}")
    
    def get_collection(self, collection_name: str):
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


# Create a singleton instance
mongo_manager = MongoDBManager() 