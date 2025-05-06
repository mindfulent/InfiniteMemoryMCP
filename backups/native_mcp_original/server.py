"""
Native MCP server implementation for InfiniteMemoryMCP using FastMCP.

This module implements a Model Context Protocol (MCP) server that enables
Claude to interface directly with the memory database.
"""

import json
import logging
import uuid
from datetime import datetime
from contextlib import asynccontextmanager
from dataclasses import dataclass
from collections.abc import AsyncIterator
import os

from fastmcp import FastMCP, Context, Image
from pymongo import MongoClient
from bson import ObjectId
from sentence_transformers import SentenceTransformer

from .config import MCPServerConfig

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("infinite_memory_mcp")

# Constants for MCP error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# Custom error codes for memory operations
MEMORY_NOT_FOUND = 100
SCOPE_NOT_FOUND = 101
EMBEDDING_GENERATION_FAILED = 102

@dataclass
class AppContext:
    """Application context for lifespan management."""
    db: MongoClient
    embedding_model: SentenceTransformer
    config: MCPServerConfig

@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle with MongoDB connection and embedding model."""
    # Load configuration
    config = MCPServerConfig()
    
    # Initialize MongoDB connection
    logger.info(f"Connecting to MongoDB at {config.mongodb.uri}")
    mongo_client = MongoClient(config.mongodb.uri)
    db = mongo_client[config.mongodb.database]
    
    # Initialize embedding model
    logger.info(f"Loading embedding model {config.embedding.model_name}")
    embedding_model = SentenceTransformer(config.embedding.model_name)
    
    try:
        yield AppContext(db=db, embedding_model=embedding_model, config=config)
    finally:
        # Cleanup on shutdown
        logger.info("Shutting down native MCP server")
        mongo_client.close()

class InfiniteMemoryMCPContext:
    """Context for InfiniteMemoryMCP operations."""
    
    def __init__(self, db_client, memories_collection, scopes_collection, 
                 embedding_model, config, scope="global"):
        """Initialize the context."""
        self.db_client = db_client
        self.memories_collection = memories_collection
        self.scopes_collection = scopes_collection
        self.embedding_model = embedding_model
        self.config = config
        self.scope = scope
        # Add lifespan_context for compatibility
        self.lifespan_context = {"scope": scope}
        
    def with_scope(self, scope):
        """Return a new context with the specified scope."""
        new_context = InfiniteMemoryMCPContext(
            self.db_client, 
            self.memories_collection,
            self.scopes_collection,
            self.embedding_model,
            self.config,
            scope
        )
        return new_context

class InfiniteMemoryMCP:
    """Native MCP server for Claude's memory system."""
    
    def __init__(self, config=None):
        """Initialize the InfiniteMemoryMCP server.
        
        Args:
            config: Either a MCPServerConfig object or a path to a config JSON file
        """
        # Load configuration
        if isinstance(config, str) and os.path.exists(config):
            # If config is a file path, load it
            with open(config, 'r') as f:
                config_dict = json.load(f)
                self.config = MCPServerConfig.from_dict(config_dict)
        elif isinstance(config, MCPServerConfig):
            # If it's already a config object, use it directly
            self.config = config
        else:
            # Create default config
            self.config = MCPServerConfig()
            
        # Set basic properties
        self.name = self.config.name
        self.version = self.config.version
        
        # Initialize FastMCP instance
        self.mcp = FastMCP(
            name=self.name,
            version=self.version,
            default_protocol_version=self.config.protocol_version
        )
        
        # Set up logging
        logging_level = getattr(logging, self.config.logging.level.upper(), logging.INFO)
        logger.setLevel(logging_level)
        
        # Initialize database connection
        self._init_db_connection()
        
        # Initialize embedding model
        self._init_embedding_model()
        
        # Create a default context
        self.default_context = InfiniteMemoryMCPContext(
            self.db_client,
            self.memories_collection,
            self.scopes_collection,
            self.embedding_model,
            self.config,
            self.config.default_scope
        )
        
        # Register tools
        self._register_tools()
        
        # Register resource handlers
        self._register_resource_handlers()
        
        logger.info(f"InfiniteMemoryMCP native MCP server initialized with {self.name} v{self.version}")
        
    async def _get_context(self, context):
        """Get a context object for the given MCP context."""
        # If the context has a lifespan_id, try to get the associated scope
        scope = self.config.default_scope
        if context and hasattr(context, "lifespan_id") and context.lifespan_id:
            # Extract scope from lifespan_id if possible
            try:
                # Assuming lifespan_id might be scope-related in some way
                # This is a placeholder for actual scope resolution logic
                scope = context.lifespan_id
            except Exception as e:
                logger.warning(f"Error extracting scope from lifespan_id: {e}")
        
        # Create a new context with the determined scope
        return self.default_context.with_scope(scope)
    
    def _init_db_connection(self):
        """Initialize the database connection."""
        try:
            # Connect to MongoDB
            logger.info(f"Connecting to MongoDB at {self.config.mongodb.uri}")
            self.db_client = MongoClient(self.config.mongodb.uri)
            db = self.db_client[self.config.mongodb.database]
            
            # Get collections
            self.memories_collection = db[self.config.mongodb.memories_collection]
            self.scopes_collection = db[self.config.mongodb.scopes_collection]
            
            # Create indices for faster searches
            self.memories_collection.create_index("scope")
            self.memories_collection.create_index("tags")
            
        except Exception as e:
            logger.error(f"Error connecting to MongoDB: {e}")
            raise

    def _init_embedding_model(self):
        """Initialize the embedding model."""
        try:
            # Load the embedding model
            logger.info(f"Loading embedding model {self.config.embedding.model_name}")
            self.embedding_model = SentenceTransformer(self.config.embedding.model_name)
        except Exception as e:
            logger.error(f"Error loading embedding model: {e}")
            raise

    def _register_tools(self):
        """Register tools with the MCP server."""
        # Store memory
        @self.mcp.tool("store_memory", "Store a new memory in the database")
        async def store_memory(context: Context, text: str, tags: list = None, 
                           scope: str = None, metadata: dict = None) -> str:
            return await self.handle_store_memory(context, text, tags, scope, metadata)
        
        # Retrieve memory
        @self.mcp.tool("retrieve_memory", "Retrieve memories using semantic search")
        async def retrieve_memory(context: Context, query: str, limit: int = 10, 
                              threshold: float = 0.6, scope: str = None) -> str:
            return await self.handle_retrieve_memory(context, query, limit, threshold, scope)
        
        # Search by tag
        @self.mcp.tool("search_by_tag", "Find memories with specific tags")
        async def search_by_tag(context: Context, tags: list, limit: int = 10, scope: str = None) -> str:
            return await self.handle_search_by_tag(context, tags, limit, scope)
        
        # Search by scope
        @self.mcp.tool("search_by_scope", "Retrieve memories from a specific scope")
        async def search_by_scope(context: Context, scope: str, limit: int = 10) -> str:
            return await self.handle_search_by_scope(context, scope, limit)
        
        # Delete memory
        @self.mcp.tool("delete_memory", "Delete a specific memory")
        async def delete_memory(context: Context, memory_id: str) -> str:
            return await self.handle_delete_memory(context, memory_id)
        
        # Get memory stats
        @self.mcp.tool("get_memory_stats", "Get statistics about stored memories")
        async def get_memory_stats(context: Context, scope: str = None) -> str:
            return await self.handle_get_memory_stats(context, scope)
        
        # Summarize memories
        @self.mcp.tool("summarize_memories", "Summarize memories by scope or tags")
        async def summarize_memories(context: Context, scope: str = None, tags: list = None) -> str:
            return await self.handle_summarize_memories(context, scope, tags)
    
    def _register_resource_handlers(self):
        """Register memory resources with the MCP server."""
        
        @self.mcp.resource("memory:scope/{scope}")
        async def memory_scope_resource(scope: str, context: Context = None) -> str:
            """Resource representing a memory scope with its contents."""
            try:
                # Get the appropriate context
                ctx = await self._get_context(context)
                
                # Fetch memories in this scope
                memories = list(ctx.memories_collection.find({"scope": scope}).limit(20))
                
                if not memories:
                    return f"# Memory Scope: {scope}\n\nNo memories found in this scope."
                
                # Return as a text resource
                content = [f"# Memory Scope: {scope}\n"]
                for memory in memories:
                    created_at = memory.get('created_at', datetime.now().isoformat())
                    content.append(f"- [{created_at}] {memory['text']}")
                
                return "\n".join(content)
            
            except Exception as e:
                logger.error(f"Error fetching scope resource: {e}")
                return f"Error fetching memories for scope '{scope}': {str(e)}"
        
        @self.mcp.resource("memory:stats")
        async def memory_stats_resource(context: Context = None) -> str:
            """Resource providing statistics about memory usage."""
            # Get the appropriate context
            ctx = await self._get_context(context)
            
            # Return memory stats
            return await self.handle_get_memory_stats(context)
    
    async def _ensure_scope_exists(self, db, scope):
        """Ensure a memory scope exists in the database."""
        # Check if scope exists
        scopes_collection = db[self.config.mongodb.scopes_collection]
        result = scopes_collection.find_one({"name": scope})
        if not result:
            # Create scope if it doesn't exist
            scopes_collection.insert_one({
                "name": scope,
                "created_at": datetime.now(),
                "description": f"Memory scope: {scope}"
            })
    
    async def _generate_embedding(self, app_ctx, text):
        """Generate an embedding for the given text."""
        try:
            # Use SentenceTransformer for embeddings
            embedding = app_ctx.embedding_model.encode(text)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise Exception(f"Failed to generate embedding: {str(e)}")
    
    def run(self, transport="stdio", host="127.0.0.1", port=8000):
        """Run the MCP server with the specified transport."""
        logger.info(f"Starting InfiniteMemoryMCP native MCP server with {transport} transport")
        
        # Pass transport-specific arguments based on the transport type
        if transport == "stdio":
            # For stdio transport, don't pass host and port
            self.mcp.run(transport=transport)
        elif transport == "sse":
            # For SSE transport, pass host and port
            self.mcp.run(transport=transport, host=host, port=port)
        else:
            # For other transports, pass all arguments and let the library handle it
            self.mcp.run(transport=transport, host=host, port=port)

    async def handle_store_memory(self, context, text, tags=None, scope=None, metadata=None):
        """Store a memory in the database."""
        try:
            # Get the appropriate context
            ctx = await self._get_context(context)
            
            # Use scope from the context if not provided
            if not scope:
                scope = ctx.scope
                
            # Generate an ID for the memory
            memory_id = str(uuid.uuid4())
            
            # Create the memory object
            memory = {
                "_id": memory_id,
                "text": text,
                "tags": tags or [],
                "scope": scope,
                "metadata": metadata or {},
                "created_at": datetime.now().isoformat(),
                "embedding": None  # Will be computed asynchronously
            }
            
            # Insert the memory into the database
            ctx.memories_collection.insert_one(memory)
            
            # Generate and store the embedding asynchronously
            # For now, we're doing it synchronously for simplicity
            embedding = ctx.embedding_model.encode(text).tolist()
            ctx.memories_collection.update_one(
                {"_id": memory_id},
                {"$set": {"embedding": embedding}}
            )
            
            return f"Memory stored with ID: {memory_id}"
        except Exception as e:
            logger.error(f"Error storing memory: {e}")
            return f"Failed to store memory: {str(e)}"
    
    async def handle_retrieve_memory(self, context, query, limit=10, threshold=0.6, scope=None):
        """Retrieve memories based on semantic similarity."""
        try:
            # Get the appropriate context
            ctx = await self._get_context(context)
            
            # Use scope from the context if not provided
            if not scope:
                scope = ctx.scope
                
            # Generate embedding for the query
            query_embedding = ctx.embedding_model.encode(query).tolist()
            
            # Create the aggregation pipeline
            pipeline = [
                {
                    "$match": {
                        "scope": scope,
                        "embedding": {"$ne": None}
                    }
                },
                {
                    "$addFields": {
                        "similarity": {
                            "$function": {
                                "body": """
                                function(a, b) {
                                    if (!a || !b) return 0;
                                    let dotProduct = 0;
                                    let normA = 0;
                                    let normB = 0;
                                    for (let i = 0; i < a.length; i++) {
                                        dotProduct += a[i] * b[i];
                                        normA += a[i] * a[i];
                                        normB += b[i] * b[i];
                                    }
                                    return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
                                }
                                """,
                                "args": ["$embedding", query_embedding],
                                "lang": "js"
                            }
                        }
                    }
                },
                {
                    "$match": {
                        "similarity": {"$gte": threshold}
                    }
                },
                {
                    "$sort": {"similarity": -1}
                },
                {
                    "$limit": limit
                }
            ]
            
            # Execute the aggregation
            results = list(ctx.memories_collection.aggregate(pipeline))
            
            if not results:
                return "No relevant memories found."
                
            # Format the results
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "id": result["_id"],
                    "text": result["text"],
                    "similarity": round(result["similarity"], 4),
                    "created_at": result["created_at"],
                    "tags": result["tags"]
                })
                
            return json.dumps(formatted_results)
        except Exception as e:
            logger.error(f"Error retrieving memory: {e}")
            return f"Failed to retrieve memories: {str(e)}"

    async def handle_search_by_tag(self, context, tags, limit=10, scope=None):
        """Search for memories with specific tags."""
        try:
            # Get the appropriate context
            ctx = await self._get_context(context)
            
            # Use scope from the context if not provided
            if not scope:
                scope = ctx.scope
                
            # Build the query
            query = {"tags": {"$in": tags}}
            if scope:
                query["scope"] = scope
                
            # Execute the query
            results = list(ctx.memories_collection.find(query).limit(limit))
            
            if not results:
                return f"No memories found with tags: {tags}"
                
            # Format the results
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "id": result["_id"],
                    "text": result["text"],
                    "tags": result["tags"],
                    "created_at": result["created_at"]
                })
                
            return json.dumps(formatted_results)
        except Exception as e:
            logger.error(f"Error searching by tag: {e}")
            return f"Failed to search by tags: {str(e)}"
    
    async def handle_search_by_scope(self, context, scope, limit=10):
        """Search for memories in a specific scope."""
        try:
            # Get the appropriate context
            ctx = await self._get_context(context)
            
            # Execute the query
            results = list(ctx.memories_collection.find({"scope": scope}).limit(limit))
            
            if not results:
                return f"No memories found in scope: {scope}"
                
            # Format the results
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "id": result["_id"],
                    "text": result["text"],
                    "tags": result["tags"],
                    "created_at": result["created_at"]
                })
                
            return json.dumps(formatted_results)
        except Exception as e:
            logger.error(f"Error searching by scope: {e}")
            return f"Failed to search by scope: {str(e)}"
    
    async def handle_delete_memory(self, context, memory_id):
        """Delete a memory by ID."""
        try:
            # Get the appropriate context
            ctx = await self._get_context(context)
            
            # Delete the memory
            result = ctx.memories_collection.delete_one({"_id": memory_id})
            
            if result.deleted_count == 0:
                return f"No memory found with ID: {memory_id}"
                
            return f"Memory with ID {memory_id} successfully deleted"
        except Exception as e:
            logger.error(f"Error deleting memory: {e}")
            return f"Failed to delete memory: {str(e)}"
    
    async def handle_get_memory_stats(self, context, scope=None):
        """Get statistics about memory usage."""
        try:
            # Get the appropriate context
            ctx = await self._get_context(context)
            
            # Build the basic query
            match_query = {}
            if scope:
                match_query["scope"] = scope
                
            # Get total count
            total_count = ctx.memories_collection.count_documents(match_query)
            
            # Get count by scope
            scope_pipeline = [
                {"$group": {"_id": "$scope", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            if match_query:
                scope_pipeline.insert(0, {"$match": match_query})
            scope_results = list(ctx.memories_collection.aggregate(scope_pipeline))
            
            # Get count by tag
            tag_pipeline = [
                {"$unwind": "$tags"},
                {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 10}
            ]
            if match_query:
                tag_pipeline.insert(0, {"$match": match_query})
            tag_results = list(ctx.memories_collection.aggregate(tag_pipeline))
            
            # Build the stats object
            stats = {
                "total_memories": total_count,
                "scopes": [{"scope": r["_id"], "count": r["count"]} for r in scope_results],
                "top_tags": [{"tag": r["_id"], "count": r["count"]} for r in tag_results]
            }
            
            return json.dumps(stats)
        except Exception as e:
            logger.error(f"Error getting memory stats: {e}")
            return f"Failed to get memory statistics: {str(e)}"
    
    async def handle_summarize_memories(self, context, scope=None, tags=None):
        """Summarize memories by scope or tags."""
        try:
            # Get the appropriate context
            ctx = await self._get_context(context)
            
            # Build the query
            query = {}
            if scope:
                query["scope"] = scope
            if tags:
                query["tags"] = {"$in": tags}
                
            # If no filters provided, use the context's scope
            if not query:
                query["scope"] = ctx.scope
                
            # Get the memories
            memories = list(ctx.memories_collection.find(query).limit(20))
            
            if not memories:
                return "No memories found to summarize."
                
            # Format the memories for the summary
            memory_texts = [f"- {m['text']}" for m in memories]
            memory_context = "\n".join(memory_texts)
            
            # For now, we just return the list of memories since we don't have LLM access here
            # In a real implementation, we would use an LLM to summarize these memories
            summary = f"Summary of {len(memories)} memories"
            if scope:
                summary += f" in scope '{scope}'"
            if tags:
                summary += f" with tags {tags}"
            summary += ":\n\n" + memory_context
            
            return summary
        except Exception as e:
            logger.error(f"Error summarizing memories: {e}")
            return f"Failed to summarize memories: {str(e)}"

# For direct execution
if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="Run the InfiniteMemoryMCP native MCP server")
    parser.add_argument("--config", help="Path to config file")
    parser.add_argument("--transport", default="stdio", choices=["stdio", "sse"], help="Transport type")
    parser.add_argument("--host", default="127.0.0.1", help="Host for HTTP transport")
    parser.add_argument("--port", type=int, default=8000, help="Port for HTTP transport")
    args = parser.parse_args()
    
    # Start server
    server = InfiniteMemoryMCP(args.config)
    server.run(transport=args.transport, host=args.host, port=args.port) 