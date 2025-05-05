# InfiniteMemoryMCP API Documentation

## MCP Protocol Integration

InfiniteMemoryMCP communicates with Claude Desktop through the Model Context Protocol (MCP). This document outlines the available commands, their parameters, and expected responses.

## Protocol Overview

Communication follows a simple request/response pattern:
1. Claude Desktop sends a JSON request to InfiniteMemoryMCP via stdin
2. InfiniteMemoryMCP processes the request and sends a JSON response via stdout
3. Claude Desktop parses the response and incorporates it into the conversation

All commands use the following general format:

**Request:**
```json
{
  "action": "<command_name>",
  "<param1>": "<value1>",
  "<param2>": "<value2>",
  ...
}
```

**Response:**
```json
{
  "status": "OK" | "ERROR",
  "result": { ... },
  "error": "<error_message>" (only if status is ERROR)
}
```

## Available Commands

### `store_memory`

Stores a piece of information in the memory database.

**Request:**
```json
{
  "action": "store_memory",
  "content": "<text to remember>",
  "metadata": {
    "scope": "<scope name or null for default>",
    "tags": ["optional", "tags", "..."],
    "source": "<optional source type (conversation|user_profile|summary)>"
  }
}
```

**Response:**
```json
{
  "status": "OK",
  "memory_id": "<generated id>",
  "scope": "<scope>"
}
```

**Parameters:**
- `content` (required): The textual information to store (sentence, paragraph, etc.)
- `metadata.scope` (optional): The memory scope/category (defaults to current active scope)
- `metadata.tags` (optional): Array of tags for categorization
- `metadata.source` (optional): Type of memory (conversation, user_profile, summary)

**Example:**
```json
// Request
{
  "action": "store_memory",
  "content": "My favorite color is blue",
  "metadata": {
    "scope": "Personal",
    "tags": ["preferences", "colors"]
  }
}

// Response
{
  "status": "OK",
  "memory_id": "60f7b1e77c4c9b001a3e9a4f",
  "scope": "Personal"
}
```

### `retrieve_memory`

Retrieves information relevant to a query from memory.

**Request:**
```json
{
  "action": "retrieve_memory",
  "query": "<user query or key phrase>",
  "filter": {
    "scope": "<scope or 'ALL'>",
    "tags": ["optional tag filter"],
    "time_range": { "from": "<ISODate>", "to": "<ISODate>" }
  },
  "top_k": 5
}
```

**Response:**
```json
{
  "status": "OK",
  "results": [
    {
      "text": "<retrieved memory text>",
      "source": "<collection or type>",
      "timestamp": "<ISODate>",
      "scope": "<scope>",
      "tags": ["tag1", "tag2"],
      "confidence": 0.85,
      "memory_id": "<id>"
    },
    { ... next result ... }
  ]
}
```

**Parameters:**
- `query` (required): Text query representing what to search for
- `filter.scope` (optional): Scope to search within (defaults to current + Global)
- `filter.tags` (optional): Limit search to memories with specified tags
- `filter.time_range` (optional): Restrict search to a specific time period
- `top_k` (optional): Number of results to return (default: 5)

**Example:**
```json
// Request
{
  "action": "retrieve_memory",
  "query": "favorite color",
  "filter": {
    "scope": "Personal"
  },
  "top_k": 3
}

// Response
{
  "status": "OK",
  "results": [
    {
      "text": "My favorite color is blue",
      "source": "user_profile",
      "timestamp": "2023-07-20T15:30:45.123Z",
      "scope": "Personal",
      "tags": ["preferences", "colors"],
      "confidence": 0.95,
      "memory_id": "60f7b1e77c4c9b001a3e9a4f"
    }
  ]
}
```

### `search_by_tag`

Retrieves memories with a specific tag.

**Request:**
```json
{
  "action": "search_by_tag",
  "tag": "<tag name>",
  "query": "<optional additional query>"
}
```

**Response:**
```json
{
  "status": "OK",
  "results": [
    {
      "text": "<memory text>",
      "timestamp": "<ISODate>",
      "scope": "<scope>",
      "tags": ["tag1", "tag2", "..."],
      "memory_id": "<id>"
    },
    { ... next result ... }
  ]
}
```

**Parameters:**
- `tag` (required): The tag to search for
- `query` (optional): Additional semantic filter for the tagged memories

**Example:**
```json
// Request
{
  "action": "search_by_tag",
  "tag": "project-alpha"
}

// Response
{
  "status": "OK",
  "results": [
    {
      "text": "Project Alpha deadline is June 30th",
      "timestamp": "2023-07-15T09:45:30.123Z",
      "scope": "Work",
      "tags": ["project-alpha", "deadlines"],
      "memory_id": "60f7b1e77c4c9b001a3e9a50"
    },
    {
      "text": "Project Alpha team meeting is every Thursday at 2pm",
      "timestamp": "2023-07-10T14:20:15.456Z",
      "scope": "Work",
      "tags": ["project-alpha", "meetings"],
      "memory_id": "60f7b1e77c4c9b001a3e9a51"
    }
  ]
}
```

### `search_by_scope`

Retrieves memories from a specific scope.

**Request:**
```json
{
  "action": "search_by_scope",
  "scope": "<scope name>",
  "query": "<optional query>"
}
```

**Response:**
```json
{
  "status": "OK",
  "results": [
    {
      "text": "<memory text>",
      "timestamp": "<ISODate>",
      "scope": "<scope>",
      "tags": ["tag1", "tag2", "..."],
      "memory_id": "<id>"
    },
    { ... next result ... }
  ]
}
```

**Parameters:**
- `scope` (required): The scope to search within
- `query` (optional): Semantic search within the scope

### `recall_memory_by_time`

Retrieves memories based on a time reference.

**Request:**
```json
{
  "action": "recall_memory_by_time",
  "time_query": "<natural language time reference>",
  "range": {
    "from": "<ISODate>",
    "to": "<ISODate>"
  },
  "scope": "<optional scope>"
}
```

**Response:**
```json
{
  "status": "OK",
  "results": [
    {
      "text": "<memory content>",
      "timestamp": "<ISODate>",
      "scope": "<scope>",
      "source": "<collection>",
      "memory_id": "<id>"
    },
    ... 
  ],
  "time_frame": {
    "from": "<ISODate>",
    "to": "<ISODate>"
  }
}
```

**Parameters:**
- `time_query` (required): Natural language description of time (e.g., "yesterday", "last week")
- `range` (optional): Explicit date range if time_query is not provided
- `scope` (optional): Scope to search within

### `delete_memory`

Removes or marks a memory item so it is no longer recalled.

**Request:**
```json
{
  "action": "delete_memory",
  "target": {
    "memory_id": "<id of memory to delete>",
    "scope": "<scope name>",
    "tag": "<tag name>",
    "query": "<text query>"
  },
  "forget_mode": "soft"
}
```

**Response:**
```json
{
  "status": "OK",
  "deleted_count": 1,
  "scope": "<if a scope was deleted, name here>",
  "note": "<additional info>"
}
```

**Parameters:**
- `target` (required): Specifies what to delete (one of memory_id, scope, tag, or query)
- `forget_mode` (optional): "soft" (default) or "hard" deletion

### Utility Commands

#### `get_memory_stats`

Returns summary statistics of the memory database.

**Request:**
```json
{
  "action": "get_memory_stats"
}
```

**Response:**
```json
{
  "status": "OK",
  "stats": {
    "total_memories": 1520,
    "conversation_count": 120,
    "scopes": {"Global": 300, "Project Alpha": 200, ...},
    "last_backup": "2023-05-01T10:00:00Z",
    "db_size_mb": 45.3
  }
}
```

#### `backup_memory`

Triggers a backup operation.

**Request:**
```json
{
  "action": "backup_memory"
}
```

**Response:**
```json
{
  "status": "OK", 
  "backup_file": "backup_2023-05-15.dump"
}
```

#### `optimize_memory`

Triggers maintenance routines for the database.

**Request:**
```json
{
  "action": "optimize_memory"
}
```

**Response:**
```json
{
  "status": "OK", 
  "operations": ["compacted_db", "removed_20_duplicate_entries", "summarized_old_conversations"]
}
```

#### `create_memory_scope`

Creates a new memory scope.

**Request:**
```json
{
  "action": "create_memory_scope",
  "scope_name": "<name>",
  "description": "<optional description>"
}
```

**Response:**
```json
{
  "status": "OK",
  "scope_id": "<generated id>",
  "scope_name": "<name>"
}
```

#### `list_memory_scopes`

Lists all available memory scopes.

**Request:**
```json
{
  "action": "list_memory_scopes"
}
```

**Response:**
```json
{
  "status": "OK",
  "scopes": [
    {
      "scope_name": "Global",
      "description": "Global scope for general memories",
      "created_at": "<ISODate>"
    },
    {
      "scope_name": "Work",
      "description": "Work-related memories",
      "created_at": "<ISODate>"
    },
    ...
  ]
}
```

## Error Handling

All commands may return an error response if something goes wrong:

```json
{
  "status": "ERROR",
  "error": "Detailed error message",
  "error_code": "ERROR_CODE"
}
```

Common error codes:
- `INVALID_REQUEST`: Missing or invalid parameters
- `CONNECTION_ERROR`: MongoDB connection issues
- `NOT_FOUND`: Requested item not found
- `ALREADY_EXISTS`: Item already exists (e.g., scope with the same name)
- `EMBEDDING_ERROR`: Error generating embeddings
- `INTERNAL_ERROR`: Internal server error

## Best Practices

### When to Use Each Command

- `store_memory`: When the user explicitly wants to remember something, or when capturing important conversation details
- `retrieve_memory`: For general recall queries based on semantic meaning
- `search_by_tag`: When the user explicitly references a tag
- `search_by_scope`: When the user wants information from a specific context
- `recall_memory_by_time`: For time-based queries like "what did we discuss yesterday?"
- `delete_memory`: When the user wants to forget specific information

### Embedding Considerations

The semantic search functionality relies on text embeddings. For optimal results:
- Keep queries focused and specific
- Ensure stored memories are meaningful and not too short
- Consider the embedding model's capabilities and limitations

### Performance Optimization

- Use filters (scope, tags, time) whenever possible to narrow search
- Limit `top_k` to a reasonable number (3-5) for most queries
- Consider batching multiple small memory operations when possible 