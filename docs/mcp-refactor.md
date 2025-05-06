# InfiniteMemoryMCP Refactoring Plan: Native MCP Implementation

## Problem Analysis

Our current implementation of InfiniteMemoryMCP uses an adapter layer (`mcp_adapter.py`) to interface with Claude Desktop. This approach introduces unnecessary complexity, potential failure points, and maintenance overhead. The adapter must:

1. Translate between our custom API and the Model Context Protocol (MCP)
2. Handle JSON-RPC 2.0 formatting requirements
3. Manage stdio communication channels
4. Implement lifecycle management
5. Handle various edge cases

The root issue is that our system wasn't designed as a native MCP server from the beginning.

## MCP Protocol Requirements

The Model Context Protocol has specific technical requirements that our native implementation must follow:

### Base Protocol 

- **JSON-RPC 2.0 Compliance**: All messages must follow the JSON-RPC 2.0 specification with proper message types (requests, responses, notifications).
- **UTF-8 Encoding**: All JSON-RPC messages must be UTF-8 encoded.
- **Message Structure**: Requests must include method, params (optional), and id; responses must include result or error; notifications include method and params without id.
- **Protocol Version**: We will support the latest MCP protocol version ("2025-03-26") as defined in schema.ts.

### Transport Layer

- **Stdio Transport**: For local integration with Claude Desktop:
  - Server reads JSON-RPC messages from stdin
  - Server writes JSON-RPC messages to stdout
  - Messages are delimited by newlines
  - No embedded newlines in messages
  - Logging/debug output goes to stderr 

- **Streamable HTTP Transport**: For remote or network-based communications:
  - Uses HTTP POST for client-to-server messages
  - Optionally uses SSE (Server-Sent Events) for streaming responses 
  - Requires secure authentication 

### Lifecycle Management

- **Initialization Phase**: 
  - Client sends `initialize` request with supported protocol version and capabilities
  - Server responds with protocol version it supports and its capabilities
  - Client sends `initialized` notification to complete initialization
  - No other communication (except ping) allowed before initialization 

- **Operation Phase**:
  - Normal protocol communication using negotiated capabilities
  - Exchange of requests, responses, and notifications 

- **Shutdown Phase**:
  - Clean termination of the connection
  - For stdio transport, client initiates shutdown 

### Capability Negotiation

- **Client Capabilities**: Declares what features the client supports
- **Server Capabilities**: Declares what features the server provides
  - Our server will announce support for tool-related capabilities
  - We'll support logging capabilities for better debugging
  - Optional support for resources to represent memory scopes
- **Protocol Version**: Negotiation of compatible protocol version 

## Architecture Changes

### Current Architecture
```
Claude Desktop → mcp_adapter.py → memory_service → MongoDB
```

### Target Architecture
```
Claude Desktop → InfiniteMemoryMCP (native MCP server) → MongoDB
```

## Implementation Strategy

### 1. Development Approach

We'll use a direct implementation approach:
1. Build a complete native MCP server with all memory functionality
2. Implement all capabilities in a single development cycle
3. Thoroughly test the implementation with Claude Desktop

### 2. Core MCP Server Implementation

#### MCP Server Framework

We'll implement a native MCP server using the Python MCP SDK, which handles many protocol details for us:

```python
from mcp.server.fastmcp import FastMCP
from contextlib import asynccontextmanager
from dataclasses import dataclass
from collections.abc import AsyncIterator
import uuid
from datetime import datetime
import logging

# MongoDB imports
from pymongo import MongoClient
from bson import ObjectId

# Constants for MCP error codes (from schema.ts)
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# Custom error codes for memory operations
MEMORY_NOT_FOUND = 100
SCOPE_NOT_FOUND = 101
EMBEDDING_GENERATION_FAILED = 102

# Configure logger
logger = logging.getLogger("infinite_memory_mcp")

class MCPError(Exception):
    """MCP protocol-compliant error."""
    
    def __init__(self, code, message, data=None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)

@dataclass
class AppContext:
    """Application context for lifespan management."""
    db: MongoClient

@asynccontextmanager
async def app_lifespan(server) -> AsyncIterator[AppContext]:
    """Manage application lifecycle with MongoDB connection."""
    # Initialize MongoDB connection
    mongo_client = MongoClient("mongodb://localhost:27017/")
    db = mongo_client["claude_memory"]
    
    try:
        yield AppContext(db=db)
    finally:
        # Cleanup on shutdown
        mongo_client.close()

class InfiniteMemoryMCP:
    """Native MCP server for Claude's memory system."""
    
    def __init__(self, config=None):
        # Load configuration
        self.config = config or {}
        self.default_scope = self.config.get("default_scope", "global")
        
        # Create MCP server with appropriate name and dependencies
        self.mcp = FastMCP(
            "InfiniteMemoryMCP", 
            dependencies=["pymongo", "sentence-transformers"],
            lifespan=app_lifespan
        )
        
        # Initialize embedding model
        self._init_embedding_model()
        
        # Register MCP handlers
        self._register_handlers()
        self._register_tools()
        self._register_resources()
        
    def _init_embedding_model(self):
        """Initialize the embedding model for semantic search."""
        from sentence_transformers import SentenceTransformer
        
        model_name = self.config.get("embedding_model", "sentence-transformers/all-MiniLM-L6-v2")
        self.embedding_model = SentenceTransformer(model_name)
        self.embedding_size = self.embedding_model.get_sentence_embedding_dimension()
        logger.info(f"Initialized embedding model {model_name} with dimension {self.embedding_size}")
        
    def _register_handlers(self):
        """Register core MCP protocol handlers."""
        
        @self.mcp.handler("initialize")
        async def handle_initialize(self, params, ctx):
            """Handle initialize request from Claude Desktop."""
            # Extract protocol version and client capabilities from params
            client_protocol_version = params["protocolVersion"]
            client_capabilities = params["capabilities"]
            client_info = params["clientInfo"]
            
            # Log client connection
            logger.info(f"Client connected: {client_info['name']} {client_info['version']}")
            
            # Determine protocol version to use (latest supported)
            server_protocol_version = "2025-03-26"  # From schema.ts LATEST_PROTOCOL_VERSION
            
            # Define our server capabilities
            server_capabilities = {
                "tools": {
                    "listChanged": True
                },
                "logging": {},
                "resources": {
                    "subscribe": True,
                    "listChanged": True
                }
            }
            
            # Return initialization response
            return {
                "protocolVersion": server_protocol_version,
                "capabilities": server_capabilities,
                "serverInfo": {
                    "name": "InfiniteMemoryMCP",
                    "version": "1.0.0"
                },
                "instructions": """
                InfiniteMemoryMCP provides persistent memory capabilities for Claude.
                Available tools:
                - store_memory: Store information in the database
                - retrieve_memory: Search for memories using semantic similarity
                - search_by_tag: Filter memories by specific tags
                - search_by_scope: Retrieve memories from specific scopes
                - delete_memory: Remove specific memories
                - get_memory_stats: View memory usage statistics
                """
            }
            
        @self.mcp.handler("tools/list")
        async def handle_list_tools(self, params, ctx):
            """Handle tools/list request with pagination support."""
            # Extract cursor from params if provided
            cursor = params.get("cursor")
            
            # Get all tools
            all_tools = self._get_all_tools()
            
            # Implement cursor-based pagination (with 10 items per page)
            page_size = 10
            if cursor:
                # Parse the cursor to get the current position
                try:
                    start_idx = int(cursor)
                except ValueError:
                    start_idx = 0
            else:
                start_idx = 0
            
            # Calculate end index and next cursor
            end_idx = min(start_idx + page_size, len(all_tools))
            has_more = end_idx < len(all_tools)
            
            # Slice the tools based on pagination
            tools_page = all_tools[start_idx:end_idx]
            
            # Prepare the next cursor if there are more results
            next_cursor = str(end_idx) if has_more else None
            
            # Return paginated result
            return {
                "tools": tools_page,
                "nextCursor": next_cursor
            }
        
    def _register_tools(self):
        """Register memory tools with proper MCP schema."""
        
        @self.mcp.tool()
        async def store_memory(
            content: str, 
            scope: str = None, 
            tags: list = None, 
            source: str = "conversation",
            conversation_id: str = None,
            speaker: str = "user",
            ctx=None
        ):
            """Store a memory in the database."""
            # Access MongoDB through lifespan context
            db = ctx.db
            
            # Default scope if not provided
            if not scope:
                scope = self.default_scope
            
            # Ensure scope exists
            await self._ensure_scope_exists(db, scope)
            
            # Generate embedding for semantic search
            embedding = await self._generate_embedding(content)
            
            # Create memory document
            memory = {
                "conversation_id": conversation_id or str(uuid.uuid4()),
                "speaker": speaker,
                "text": content,
                "scope": scope,
                "tags": tags or [],
                "timestamp": datetime.now(),
                "embedding": embedding
            }
            
            # Store in MongoDB
            result = await db.conversation_history.insert_one(memory)
            memory_id = str(result.inserted_id)
            
            return {
                "content": [{
                    "type": "text",
                    "text": f"Memory stored successfully with ID: {memory_id}"
                }],
                "isError": False,
                "_meta": {
                    "memory_id": memory_id,
                    "scope": scope
                }
            }
        
        # Register tool metadata
        store_memory.description = "Stores a piece of information in long-term memory for later retrieval"
        store_memory.input_schema = {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The text content to store in memory"
                },
                "scope": {
                    "type": "string",
                    "description": "The scope/namespace to store the memory in (default: global)"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional tags to categorize this memory"
                },
                "source": {
                    "type": "string",
                    "description": "Source of the memory (conversation, document, etc.)"
                },
                "conversation_id": {
                    "type": "string",
                    "description": "ID of the conversation this memory belongs to"
                },
                "speaker": {
                    "type": "string",
                    "description": "Who created this memory (user or assistant)"
                }
            },
            "required": ["content"]
        }
        store_memory.annotations = {
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False
        }
        
        @self.mcp.tool()
        async def retrieve_memory(query: str, filter: dict = None, top_k: int = 5, ctx=None):
            """Retrieve memories based on semantic search."""
            try:
                # Generate embedding for query
                query_embedding = await self._generate_embedding(query)
                
                # Build search pipeline
                pipeline = [
                    {
                        "$search": {
                            "knnBeta": {
                                "vector": query_embedding,
                                "path": "embedding",
                                "k": top_k * 2  # Get more than needed for filtering
                            }
                        }
                    }
                ]
                
                # Add filtering if provided
                if filter:
                    pipeline.append({"$match": filter})
                
                # Execute search
                db = ctx.db
                cursor = db.conversation_history.aggregate(pipeline)
                results = await cursor.to_list(length=top_k)
                
                # Format results according to MCP spec
                content = [{
                    "type": "text",
                    "text": f"Found {len(results)} memories matching '{query}':"
                }]
                
                # Add each memory as a separate text content element
                for idx, memory in enumerate(results):
                    content.append({
                        "type": "text",
                        "text": f"{idx+1}. {memory['text']}",
                        "annotations": {
                            "priority": 0.9,
                            "audience": ["assistant"]
                        }
                    })
                
                return {
                    "content": content,
                    "isError": False,
                    "_meta": {
                        "count": len(results)
                    }
                }
            except Exception as e:
                # Error handling with proper MCP error format
                logger.error(f"Error retrieving memory: {e}")
                return {
                    "content": [{
                        "type": "text",
                        "text": f"Failed to retrieve memories: {str(e)}"
                    }],
                    "isError": True,
                    "_meta": {
                        "errorCode": INTERNAL_ERROR,
                        "errorMessage": str(e)
                    }
                }
        
        # Register tool metadata
        retrieve_memory.description = "Retrieve memories matching a semantic query"
        retrieve_memory.input_schema = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The text query to search for semantically similar memories"
                },
                "filter": {
                    "type": "object",
                    "description": "Optional MongoDB filter to apply (e.g., for specific tags, scopes)"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Maximum number of memories to return",
                    "default": 5
                }
            },
            "required": ["query"]
        }
        retrieve_memory.annotations = {
            "readOnlyHint": True
        }
        
        @self.mcp.tool()
        async def search_by_tag(tags: list, scope: str = None, ctx=None):
            """Search for memories with specific tags."""
            try:
                # Prepare filter
                filter = {"tags": {"$in": tags}}
                if scope:
                    filter["scope"] = scope
                
                # Execute search
                db = ctx.db
                cursor = db.conversation_history.find(filter).sort("timestamp", -1).limit(20)
                results = await cursor.to_list(length=20)
                
                # Format results
                content = [{
                    "type": "text",
                    "text": f"Found {len(results)} memories with tags {tags}:"
                }]
                
                for idx, memory in enumerate(results):
                    content.append({
                        "type": "text",
                        "text": f"{idx+1}. {memory['text']}"
                    })
                
                return {
                    "content": content,
                    "isError": False
                }
            except Exception as e:
                # Error handling
                logger.error(f"Error searching by tag: {e}")
                return {
                    "content": [{
                        "type": "text",
                        "text": f"Failed to search by tags: {str(e)}"
                    }],
                    "isError": True
                }
        
        @self.mcp.tool()
        async def delete_memory(memory_id: str, ctx=None):
            """Delete a memory by ID."""
            try:
                # Convert string ID to ObjectId
                oid = ObjectId(memory_id)
                
                # Execute deletion
                db = ctx.db
                result = await db.conversation_history.delete_one({"_id": oid})
                
                if result.deleted_count == 0:
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"Memory with ID {memory_id} not found."
                        }],
                        "isError": True
                    }
                
                return {
                    "content": [{
                        "type": "text",
                        "text": f"Memory {memory_id} deleted successfully."
                    }],
                    "isError": False
                }
            except Exception as e:
                logger.error(f"Error deleting memory: {e}")
                return {
                    "content": [{
                        "type": "text",
                        "text": f"Failed to delete memory: {str(e)}"
                    }],
                    "isError": True
                }
        
        @self.mcp.tool()
        async def bulk_import_memories(source: str, scope: str = None, ctx=None):
            """Import multiple memories from a source."""
            # Extract progress token if provided
            progress_token = ctx.params.get("_meta", {}).get("progressToken")
            
            try:
                # Parse source and prepare data
                memories = await self._parse_memories(source)
                total = len(memories)
                
                # Send initial progress notification
                if progress_token:
                    await self.mcp.send_progress(progress_token, 0, total, "Starting import")
                
                # Process memories with progress updates
                for i, memory in enumerate(memories):
                    # Store the memory
                    await self._store_memory_internal(memory, scope)
                    
                    # Update progress (every 10% or 10 items, whichever is less frequent)
                    if progress_token and (i % max(1, min(10, total // 10)) == 0):
                        progress_pct = (i + 1) / total
                        await self.mcp.send_progress(
                            progress_token, 
                            i + 1, 
                            total, 
                            f"Imported {i+1}/{total} memories ({progress_pct:.0%})"
                        )
                
                # Final progress update
                if progress_token:
                    await self.mcp.send_progress(progress_token, total, total, "Import complete")
                
                return {
                    "content": [{
                        "type": "text",
                        "text": f"Successfully imported {total} memories"
                    }],
                    "isError": False
                }
            except Exception as e:
                # Error handling...
                return {
                    "content": [{
                        "type": "text",
                        "text": f"Failed to import memories: {str(e)}"
                    }],
                    "isError": True
                }
        
        @self.mcp.tool()
        async def summarize_memories(query: str, top_k: int = 5, ctx=None):
            """Retrieve and summarize memories using the LLM."""
            
            # First retrieve memories
            memories = await self._retrieve_memories(query, top_k, ctx)
            
            # Format memories for the model
            memory_text = "\n\n".join([f"Memory {i+1}: {m['text']}" 
                                     for i, m in enumerate(memories)])
            
            # Request LLM to summarize via sampling
            try:
                response = await self.mcp.create_message(
                    messages=[
                        {
                            "role": "user",
                            "content": {
                                "type": "text",
                                "text": f"Please summarize these memories related to '{query}':\n\n{memory_text}"
                            }
                        }
                    ],
                    model_preferences={
                        "intelligencePriority": 0.8,
                        "hints": [{"name": "claude-3-sonnet"}]
                    },
                    system_prompt="You are a helpful assistant. Summarize the given memories concisely.",
                    max_tokens=300
                )
                
                # Return the summary
                return {
                    "content": [{
                        "type": "text",
                        "text": f"Summary of memories related to '{query}':"
                    }, {
                        "type": "text",
                        "text": response["content"]["text"]
                    }],
                    "isError": False
                }
            except Exception as e:
                # Error handling
                logger.error(f"Error summarizing memories: {e}")
                return {
                    "content": [{
                        "type": "text",
                        "text": f"Failed to summarize memories: {str(e)}"
                    }],
                    "isError": True
                }
    
    def _register_resources(self):
        """Register memory resources that can be accessed by Claude."""
        
        # Define a memory scope resource
        @self.mcp.resource(uri_template="memory:scope/{scope}")
        async def memory_scope_resource(scope: str, ctx):
            """Resource representing a memory scope with its contents."""
            # Fetch memories in this scope
            memories = await self._get_memories_by_scope(scope, ctx)
            
            # Return as a text resource
            content = f"# Memory Scope: {scope}\n\n"
            for memory in memories:
                content += f"- {memory['text']}\n"
            
            return {
                "uri": f"memory:scope/{scope}",
                "name": f"Memory Scope: {scope}",
                "mimeType": "text/plain",
                "text": content
            }
        
        # Define individual memory resource
        @self.mcp.resource(uri_template="memory:id/{memory_id}")
        async def memory_resource(memory_id: str, ctx):
            """Resource representing a single memory."""
            # Fetch the memory
            memory = await self._get_memory_by_id(memory_id, ctx)
            
            # Return as text resource
            return {
                "uri": f"memory:id/{memory_id}",
                "name": f"Memory: {memory_id}",
                "mimeType": "text/plain",
                "text": memory["text"]
            }
    
    async def _generate_embedding(self, text: str):
        """Generate an embedding for the given text."""
        try:
            # Use SentenceTransformer for embeddings
            embedding = self.embedding_model.encode(text)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise MCPError(
                code=EMBEDDING_GENERATION_FAILED,
                message="Failed to generate embedding",
                data={"error": str(e)}
            )
    
    async def _ensure_scope_exists(self, db, scope):
        """Ensure a memory scope exists in the database."""
        # Check if scope exists
        result = await db.memory_scopes.find_one({"name": scope})
        if not result:
            # Create scope if it doesn't exist
            await db.memory_scopes.insert_one({
                "name": scope,
                "created_at": datetime.now(),
                "description": f"Memory scope: {scope}"
            })
    
    async def _get_memories_by_scope(self, scope, ctx):
        """Get all memories in a specific scope."""
        db = ctx.db
        cursor = db.conversation_history.find({"scope": scope}).sort("timestamp", -1)
        return await cursor.to_list(length=100)  # Limit to 100 memories
    
    async def _get_memory_by_id(self, memory_id, ctx):
        """Get a memory by its ID."""
        try:
            db = ctx.db
            oid = ObjectId(memory_id)
            memory = await db.conversation_history.find_one({"_id": oid})
            if not memory:
                raise MCPError(
                    code=MEMORY_NOT_FOUND,
                    message=f"Memory with ID {memory_id} not found",
                    data={"memory_id": memory_id}
                )
            return memory
        except Exception as e:
            logger.error(f"Error retrieving memory: {e}")
            raise
    
    async def _retrieve_memories(self, query, top_k, ctx):
        """Internal method to retrieve memories based on semantic search."""
        # Implementation similar to retrieve_memory tool but returns raw memories
        query_embedding = await self._generate_embedding(query)
        db = ctx.db
        
        pipeline = [
            {
                "$search": {
                    "knnBeta": {
                        "vector": query_embedding,
                        "path": "embedding",
                        "k": top_k
                    }
                }
            }
        ]
        
        cursor = db.conversation_history.aggregate(pipeline)
        return await cursor.to_list(length=top_k)
    
    def run(self):
        """Run the MCP server."""
        self.mcp.run()

# Main entry point
if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="Run the InfiniteMemoryMCP server")
    parser.add_argument("--config", default="config.json", help="Path to config file")
    args = parser.parse_args()
    
    # Load config
    try:
        with open(args.config, "r") as f:
            config = json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        config = {}
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()]
    )
    
    # Start server
    server = InfiniteMemoryMCP(config)
    server.run()
```

#### Protocol Compliance 

We'll ensure our implementation fully complies with MCP specifications:

1. **Base Protocol Implementation**:
   - Proper JSON-RPC 2.0 message handling (handled by SDK)
   - UTF-8 encoding for all communications
   - Correct message structure for requests, responses, and notifications

2. **Lifecycle Management**:
   - Initialization phase with capability negotiation
   - Operation phase with proper message handling
   - Graceful shutdown handling

3. **Tool Implementation**:
   - Convert our existing memory operations to MCP tools with proper schemas:
     - `store_memory`
     - `retrieve_memory` 
     - `search_by_tag`
     - `search_by_scope`
     - `delete_memory`
     - `get_memory_stats`
     - `bulk_import_memories` (with progress tracking)
     - `summarize_memories` (using LLM sampling)

### 3. Error Handling

We'll implement robust error handling according to the MCP specification:

```python
class MCPError(Exception):
    """MCP protocol-compliant error."""
    
    def __init__(self, code, message, data=None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)

# Constants for MCP error codes (from schema.ts)
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# Custom error codes for memory operations
MEMORY_NOT_FOUND = 100
SCOPE_NOT_FOUND = 101
EMBEDDING_GENERATION_FAILED = 102

# Error handling in a tool
try:
    # Memory operation
    result = await db.find_one({"_id": ObjectId(memory_id)})
    if not result:
        raise MCPError(
            code=MEMORY_NOT_FOUND,
            message="Memory not found",
            data={"memory_id": memory_id}
        )
    # Process result...
except MCPError as e:
    # Return as tool error (not protocol error)
    return {
        "content": [{
            "type": "text",
            "text": e.message
        }],
        "isError": True,
        "_meta": {
            "errorCode": e.code,
            "errorData": e.data
        }
    }
except Exception as e:
    # Unexpected errors
    logger.error(f"Internal error: {e}")
    return {
        "content": [{
            "type": "text",
            "text": f"An internal error occurred: {str(e)}"
        }],
        "isError": True,
        "_meta": {
            "errorCode": INTERNAL_ERROR,
            "errorData": {"message": str(e)}
        }
    }
```

### 4. Configuration

We'll create a comprehensive configuration file to support our native MCP implementation:

```json
{
  "server": {
    "name": "InfiniteMemoryMCP",
    "version": "1.0.0",
    "default_protocol_version": "2025-03-26"
  },
  "mongodb": {
    "uri": "mongodb://localhost:27017/",
    "database": "claude_memory",
    "collections": {
      "memories": "conversation_history",
      "scopes": "memory_scopes"
    }
  },
  "embedding": {
    "model": "sentence-transformers/all-MiniLM-L6-v2",
    "dimension": 384,
    "batch_size": 32
  },
  "logging": {
    "level": "info",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  },
  "capabilities": {
    "resources": {
      "enabled": true,
      "subscribe": true,
      "listChanged": true
    },
    "tools": {
      "enabled": true,
      "listChanged": true
    },
    "logging": {
      "enabled": true
    }
  }
}
```

### 5. Claude Desktop Integration

To integrate with Claude Desktop, the following configuration in `claude_desktop_config.json` will be needed:

```json
{
  "mcpServers": {
    "infinite-memory": {
      "command": "python",
      "args": ["-m", "infinite_memory_mcp.main", "--config", "config.json"],
      "cwd": "/path/to/InfiniteMemoryMCP",
      "env": {
        "PYTHONPATH": "/path/to/InfiniteMemoryMCP",
        "LOG_LEVEL": "INFO",
        "MONGODB_URI": "mongodb://localhost:27017/"
      },
      "stdio": true
    }
  },
  "defaultMcpServer": "infinite-memory"
}
```

### 6. Environment Setup

We'll update the project dependencies to include the MCP SDK and other required packages:

```
pymongo>=4.4.0
motor>=3.2.0  # Async MongoDB driver
sentence-transformers>=2.2.2
mcp-server>=1.0.0  # Or latest version
fastmcp>=0.1.0  # FastMCP framework
pydantic>=2.0.0  # For data validation
```

## Migration Strategy

1. **Parallel Development**:
   - Build the new MCP-native implementation alongside existing adapter
   - Start with core functionality (store/retrieve memory)
   - Test with Claude Desktop

2. **Incremental Feature Migration**:
   - Migrate features one by one with comprehensive testing
   - Maintain test coverage for each component
   - Document API differences
   - Implement advanced features (pagination, progress tracking, LLM summarization)

3. **Database Compatibility**:
   - Ensure new implementation can read existing database content
   - Maintain schema compatibility or implement migrations
   - Test with production data snapshots

4. **Testing and Validation**:
   - Test with real Claude Desktop workflows
   - Validate error handling and edge cases
   - Measure performance compared to adapter approach
   - Test pagination with large memory sets

## Performance and Security Considerations

1. **Performance Optimization**:
   - Use async/non-blocking operations for better responsiveness
   - Implement caching for frequently accessed memories
   - Batch embedding generation for multiple memories
   - Profile and optimize critical paths
   - Implement efficient vector search using MongoDB Atlas or similar

2. **Security Hardening**:
   - For stdio transport, ensure proper isolation of process
   - For HTTP transport, implement secure authentication
   - Validate all input data using Pydantic models
   - Sanitize memory content to prevent injection attacks
   - Implement proper access controls for multi-user scenarios

3. **Logging Strategy**:
   - Structured logging to stderr using MCP protocol
   - Configurable log levels via MCP logging capabilities
   - Include request IDs for traceability
   - Implement log rotation for production deployments

## Conclusion

Refactoring InfiniteMemoryMCP as a native MCP server will:
- Eliminate adapter complexity
- Improve reliability and performance
- Ensure better compatibility with Claude Desktop
- Enable rich content responses and progress tracking
- Support pagination for large memory sets
- Provide advanced features like LLM summarization of memories
- Simplify future maintenance and enhancement

By following MCP protocol specifications directly, we'll create a more robust system that integrates seamlessly with Claude Desktop and potentially other MCP-compatible clients in the future. The detailed implementation of initialization, error handling, tool definitions, and resource management will ensure full compliance with the MCP specification while providing a powerful memory capability for Claude.