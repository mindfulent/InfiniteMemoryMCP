"""
MongoDB manager for InfiniteMemoryMCP.

This module manages the connection to MongoDB, handling both embedded
and external modes.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import ServerSelectionTimeoutError

from ..utils.config import config_manager
from ..utils.logging import logger


class MongoManager:
    """
    Manager for MongoDB connections.
    
    This class handles connecting to MongoDB in both embedded and external
    modes, and provides access to collections.
    """
    
    def __init__(self):
        """Initialize the MongoDB manager."""
        self.client: Optional[MongoClient] = None
        self.db: Optional[Database] = None
        self.embedded_process: Optional[subprocess.Popen] = None
        self.db_path = config_manager.get_database_path() if hasattr(config_manager, 'get_database_path') else config_manager.get(
            "database.path",
            str(Path.home() / "ClaudeMemory" / "mongo_data")
        )
        self.use_embedded = config_manager.get("database.mode", "embedded") == "embedded"
        self.mode = "embedded" if self.use_embedded else "external"
        self.uri = config_manager.get(
            "database.uri",
            "mongodb://localhost:27017/claude_memory"
        )
        # Keep the old attribute for backward compatibility
        self.connection_uri = self.uri
        self.db_name = self.uri.split("/")[-1].split("?")[0] if "/" in self.uri else "claude_memory"
        self.startup_timeout = 30  # seconds
        self.indexes_created = False
    
    def start(self) -> bool:
        """
        Start the MongoDB connection.
        
        If using embedded mode, this will start a MongoDB server process.
        Otherwise, it will connect to an external MongoDB server.
        
        Returns:
            True if connection was successful
        """
        if self.use_embedded:
            return self._start_embedded()
        else:
            return self._connect_external()
    
    def _start_embedded(self) -> bool:
        """
        Start an embedded MongoDB server.
        
        Returns:
            True if server started successfully
        """
        if self.client:
            logger.info("MongoDB already connected")
            return True
        
        logger.info("Starting embedded MongoDB server")
        
        # Create the data directory if it doesn't exist
        Path(self.db_path).mkdir(parents=True, exist_ok=True)
        
        try:
            # Start the MongoDB process
            cmd = [
                "mongod",
                "--dbpath", self.db_path,
                "--port", "27017",
                "--bind_ip", "127.0.0.1",
                "--nohttpinterface"
            ]
            
            # Start the process
            self.embedded_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            
            # Wait for MongoDB to start
            start_time = time.time()
            connected = False
            
            while not connected and time.time() - start_time < self.startup_timeout:
                try:
                    # Try to connect
                    self.client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=1000)
                    self.client.admin.command("ping")
                    connected = True
                except ServerSelectionTimeoutError:
                    # Not ready yet, wait and try again
                    time.sleep(0.5)
            
            if not connected:
                logger.error("Failed to start embedded MongoDB server")
                self._cleanup_embedded()
                return False
            
            # Get the database
            self.db = self.client.get_database(self.db_name)
            
            logger.info("Embedded MongoDB server started successfully")
            
            # Create indexes
            self._ensure_indexes()
            
            return True
        
        except Exception as e:
            logger.error(f"Error starting embedded MongoDB server: {e}")
            self._cleanup_embedded()
            return False
    
    def _cleanup_embedded(self) -> None:
        """Clean up embedded MongoDB resources."""
        if self.embedded_process:
            try:
                # First try to terminate gracefully
                self.embedded_process.terminate()
                try:
                    self.embedded_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # If it doesn't terminate, kill it
                    self.embedded_process.kill()
                    self.embedded_process.wait(timeout=2)
            except Exception as e:
                logger.error(f"Error stopping embedded MongoDB server: {e}")
            
            self.embedded_process = None
        
        if self.client:
            try:
                self.client.close()
            except:
                pass
            self.client = None
            self.db = None
    
    def _connect_external(self) -> bool:
        """
        Connect to an external MongoDB server.
        
        Returns:
            True if connection was successful
        """
        if self.client:
            logger.info("MongoDB already connected")
            return True
        
        logger.info(f"Connecting to external MongoDB: {self.uri}")
        
        try:
            # Connect to MongoDB
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=5000)
            
            # Verify connection
            self.client.admin.command("ping")
            
            # Get the database name from the URI
            if "/" in self.uri:
                self.db_name = self.uri.split("/")[-1]
                if "?" in self.db_name:
                    self.db_name = self.db_name.split("?")[0]
            
            # Get the database - use __getitem__ to be consistent with test expectations
            self.db = self.client[self.db_name]
            
            logger.info("Connected to external MongoDB server successfully")
            
            # Create indexes
            self._ensure_indexes()
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            if self.client:
                try:
                    self.client.close()
                except:
                    pass
                self.client = None
            return False
    
    def stop(self) -> None:
        """Stop the MongoDB connection."""
        if self.use_embedded:
            self._cleanup_embedded()
        else:
            if self.client:
                try:
                    self.client.close()
                except:
                    pass
                self.client = None
                self.db = None
        
        logger.info("MongoDB connection stopped")
    
    def get_collection(self, collection_name: str) -> Collection:
        """
        Get a MongoDB collection.
        
        Args:
            collection_name: The name of the collection
            
        Returns:
            The collection object
            
        Raises:
            RuntimeError: If the MongoDB connection is not established
        """
        if not self.db:
            raise RuntimeError("MongoDB connection not established")
        
        return self.db.get_collection(collection_name)
    
    def get_client(self) -> MongoClient:
        """
        Get the MongoDB client.
        
        Returns:
            The MongoDB client
            
        Raises:
            RuntimeError: If the MongoDB connection is not established
        """
        if not self.client:
            raise RuntimeError("MongoDB connection not established")
        
        return self.client
    
    def get_database(self) -> Database:
        """
        Get the MongoDB database.
        
        Returns:
            The MongoDB database
            
        Raises:
            RuntimeError: If the MongoDB connection is not established
        """
        if not self.db:
            raise RuntimeError("MongoDB connection not established")
        
        return self.db
    
    def _ensure_indexes(self) -> None:
        """
        Ensure that necessary indexes exist on collections.
        
        This improves query performance for common operations.
        """
        if not self.db or self.indexes_created:
            return
        
        try:
            # Conversation history indexes
            conversation_history = self.get_collection("conversation_history")
            conversation_history.create_index([("conversation_id", ASCENDING), ("timestamp", ASCENDING)])
            conversation_history.create_index([("scope", ASCENDING)])
            conversation_history.create_index([("tags", ASCENDING)])
            conversation_history.create_index([("timestamp", DESCENDING)])
            # Optional text index for keyword search
            try:
                conversation_history.create_index([("content", TEXT)])
            except Exception as e:
                logger.warning(f"Could not create text index on conversation_history: {e}")
            
            # Memory index collection (for embeddings)
            memory_index = self.get_collection("memory_index")
            memory_index.create_index([("source_id", ASCENDING)], unique=True)
            memory_index.create_index([("scope", ASCENDING)])
            memory_index.create_index([("source_collection", ASCENDING)])
            
            # Metadata collection
            metadata = self.get_collection("metadata")
            metadata.create_index([("type", ASCENDING)])
            metadata.create_index([("scope_name", ASCENDING)], unique=True, 
                                 partialFilterExpression={"type": "scope"})
            
            # User profile collection
            user_profile = self.get_collection("user_profile")
            user_profile.create_index([("user_id", ASCENDING)], unique=True)
            
            logger.info("Created MongoDB indexes")
            self.indexes_created = True
        
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
    
    def optimize_database(self) -> Dict[str, Any]:
        """
        Optimize the database by performing maintenance operations.
        
        Returns:
            A dict with results of the optimization
        """
        results = {
            "status": "ok",
            "operations_performed": []
        }
        
        if not self.db:
            results["status"] = "error"
            results["error"] = "MongoDB connection not established"
            return results
        
        try:
            # Ensure indexes are created and up to date
            self._ensure_indexes()
            results["operations_performed"].append("indexes_updated")
            
            # Reindex collections to optimize index storage
            collections = ["conversation_history", "memory_index", "metadata", "user_profile"]
            for collection_name in collections:
                try:
                    collection = self.get_collection(collection_name)
                    collection.reindex()
                    results["operations_performed"].append(f"reindexed_{collection_name}")
                except Exception as e:
                    logger.warning(f"Error reindexing {collection_name}: {e}")
            
            # Compact the database if supported by storage engine
            try:
                self.db.command("compact", "conversation_history")
                results["operations_performed"].append("compacted_conversation_history")
            except Exception as e:
                logger.warning(f"Error compacting database: {e}")
            
            # Run server status to get stats
            server_status = self.client.admin.command("serverStatus")
            results["db_stats"] = {
                "connections": server_status.get("connections", {}).get("current", 0),
                "memory_mb": server_status.get("mem", {}).get("resident", 0) / 1024.0
            }
            
            # Run collection stats
            collection_stats = {}
            for collection_name in collections:
                try:
                    collection = self.get_collection(collection_name)
                    stats = self.db.command("collStats", collection_name)
                    collection_stats[collection_name] = {
                        "count": stats.get("count", 0),
                        "size_mb": stats.get("size", 0) / (1024 * 1024),
                    }
                except Exception as e:
                    logger.warning(f"Error getting stats for {collection_name}: {e}")
            
            results["collection_stats"] = collection_stats
            
            logger.info("Database optimization completed successfully")
            return results
        
        except Exception as e:
            logger.error(f"Error optimizing database: {e}")
            results["status"] = "error"
            results["error"] = str(e)
            return results


# Create a singleton instance
mongo_manager = MongoManager() 