# InfiniteMemoryMCP Technical Requirements

## System Overview and Architecture

&#x20;**Figure: InfiniteMemoryMCP System Architecture.** Claude Desktop (the local LLM application acting as an MCP client) communicates with a local **InfiniteMemoryMCP** service to manage long-term memory, which in turn uses a local **MongoDB** database for persistent storage. All components run on the user’s machine, ensuring data never leaves the device. When Claude needs to remember or retrieve information, it issues an MCP command to InfiniteMemoryMCP; the service translates this into MongoDB operations (inserts, queries, updates) and returns the results to Claude. This design keeps the memory loop entirely local: Claude treats the memory service as a plugin, and the service handles all data persistence and lookup, leveraging MongoDB’s reliability for storage.

**Key Components:**

* **Claude Desktop (LLM MCP Client):** The local AI assistant application (Claude) that supports the Model Context Protocol. It sends standardized MCP interface calls to external tools or services. In this case, Claude issues memory-related commands to InfiniteMemoryMCP whenever the user invokes memory actions in natural language (e.g. “Remember X” or “What did I tell you about Y?”). Claude’s MCP client layer handles forming the JSON requests and processing the JSON responses such that the conversation with the user continues seamlessly with the retrieved memory context.

* **InfiniteMemoryMCP (Local Memory Service):** A custom MCP server process that implements a **persistent memory service**. It listens for specific memory commands from Claude and executes the corresponding logic (storing a memory, searching, deleting, etc.). This service encapsulates all long-term memory functionality:

  * Writing new memories to the database when told to remember something.
  * Retrieving memories via semantic search or filters when Claude needs to recall information.
  * Managing organizational structure (scopes, tags) and performing maintenance tasks like pruning or backup.
  * Formatting results into a safe, structured form to return to Claude.
    The InfiniteMemoryMCP service is modular and decoupled from Claude’s core. As long as it adheres to the MCP protocol, it can be updated or replaced independently without changes to Claude, and even the database backend could be swapped if needed (e.g. another local DB in place of MongoDB).

* **MongoDB (Local Data Store):** The persistent storage engine used for all memory data. MongoDB is chosen for its flexibility (schema-less JSON documents) and robust local operation. It runs either as an **embedded database** launched by the MCP service or as a local `mongod` process that the service connects to, depending on configuration. MongoDB stores multiple **collections** for different types of memory (conversation logs, summaries, user profile, etc.), all on the user’s file system. MongoDB’s indexing and querying capabilities enable efficient retrieval by time, by tag, or even by similarity (using future vector search features). By default, the database is bound to localhost, and all queries from InfiniteMemoryMCP occur via the loopback interface – **no external network calls** are made. The data files reside in a local directory (see *Backup, Export, and File Structure*), ensuring the user has full control over their data at all times.

**Architectural Behavior:** Claude Desktop uses InfiniteMemoryMCP as if it were an extension of its own memory. When the user provides information to remember or asks a question that relies on past knowledge, Claude’s MCP client translates that into a JSON command request to InfiniteMemoryMCP. The memory service performs the necessary MongoDB operations and returns data (e.g. the content of a stored memory) in a structured JSON format. Claude then incorporates that data into its reply to the user in natural language. This way, the **flow of information** remains: **Claude (LLM)** ⇄ **InfiniteMemoryMCP (service)** ⇄ **MongoDB (database)**, with Claude never directly accessing the database and the user never needing to manage the database directly. The local-first architecture prioritizes privacy and low-latency retrieval, since all operations are on-device.

## Installation and Configuration

**Deployment Modes:** InfiniteMemoryMCP should support two installation modes for MongoDB:

* *Embedded MongoDB:* The InfiniteMemoryMCP service can bundle or invoke an embedded MongoDB instance (for example, using MongoDB’s library or starting a server process automatically). In this mode, the user does not need to separately install MongoDB; the service manages the database lifecycle internally. The MongoDB data files might be stored in a subdirectory of the Claude application (configurable path). This mode is aimed at simplicity – the memory system works out-of-the-box.

* *External/Local MongoDB Process:* Alternatively, the system can connect to a MongoDB instance running on the user’s machine. The user (or installer) would ensure a MongoDB server (version compatible, e.g. 4.4+ or 6.x for vector search support) is running, and InfiniteMemoryMCP will connect via a URI (default `mongodb://localhost:27017/claude_memory`). This mode might be used by advanced users who already have MongoDB or want more control over the database (running as a service, custom configs). In this configuration, InfiniteMemoryMCP should not automatically shut down the DB, but rather just use it.

**First-Time Setup:** Upon first installation, the following should occur:

* If using an embedded DB, the service initializes a new MongoDB data directory (if not already present) at the default path (which can be something like `~/ClaudeMemoryDB/mongo_data` or an OS-appropriate application data folder). It will then start the MongoDB instance or ensure it’s running.
* If connecting to an external mongod, the user should be guided to install MongoDB (if not present) and ensure it’s running. The system could provide a one-time setup script or instructions for this. On first run, InfiniteMemoryMCP will attempt to connect to the specified URI, create the `claude_memory` database and required collections if they don’t exist, and test a simple query to verify the connection.
* The first-time setup should also populate any necessary metadata. For example, it could create a default “Global” memory scope in the Metadata collection (see Data Model) and possibly an initial user profile document. These defaults ensure the system has a baseline environment to operate in.
* Environment requirements: The user’s machine should have sufficient resources to run Claude and MongoDB concurrently. This means at least a few hundred MB of disk space for the database (to grow over time), and enough RAM/CPU for the embedding model (which might use a few hundred MB of RAM). The installation guide should note that no internet connection is required for memory functionality (except possibly to download model files initially, if the embedding model isn’t packaged).

**Configuration Options:** Provide a configuration file (e.g. `infinite_memory_config.json` or as part of Claude’s settings) that allows customization of key parameters:

* **Database Path:** Filesystem path to store MongoDB data. Default could be `~/ClaudeMemory` (with subfolders for data, backups, logs as described later). Users can change this to another drive or location if desired.
* **MongoDB Mode/URI:** A setting to toggle embedded vs external DB. For external, allow specifying the connection URI, database name, and credentials if any. For embedded, possibly allow specifying the MongoDB binary path or version if an external binary is used.
* **Memory Size Limits:** Soft limits on memory storage. For example, a max number of documents per collection or a max database size in MB. These can be used to trigger pruning. E.g. `max_memory_items: 100000` or `max_memory_size_mb: 500`. Defaults can be high (to truly approach “infinite” within reason), but users on limited storage might set them lower. When limits are approached, the system will start summarizing or pruning (see Memory Management).
* **Backup Schedule and Retention:** Configuration of automatic backups: e.g. enable/disable, frequency (daily/weekly), number of backups to keep (such as keep last 7 daily backups and 4 weekly backups). Also a setting for backup encryption (off by default, or provide a passphrase).
* **Embedding Model Settings:** If applicable, allow configuration of the embedding model used for semantic memory. For instance, a model name or path, and whether to use CPU vs GPU. This helps if a user wants to swap in a different sentence transformer model for customization or performance. Default might be a reasonably small, general-purpose model for speed.
* **Memory Scopes & Behavior:** Optionally, allow configuration of scope behavior (though mostly handled automatically). For example, a setting for the default active scope (like “Global” or “Conversation-specific”), or whether to auto-create new scopes per conversation. These might be more advanced settings.
* **Logging Level:** For debugging, allow turning on verbose logging for the InfiniteMemoryMCP service and/or MongoDB. This might output MCP requests and database operations to a log file (in the logs directory). By default, it could be minimal.

All configuration should have sensible defaults so that a non-technical user can **install and run with minimal setup**. The first-time setup can be accompanied by a brief guide or even a setup wizard that explains the memory system’s capabilities and privacy (emphasizing all data is local). After installation, InfiniteMemoryMCP should start alongside Claude Desktop (the Claude app can launch or ensure the service is running) so that memory features are available without extra user steps.

## Data Model Definitions

InfiniteMemoryMCP uses a MongoDB database (e.g. named `claude_memory`) composed of multiple collections to store different categories of data. Each collection’s schema is defined to facilitate efficient querying and management. Below are the key collections and their data models, including field definitions, types, and indexing strategies:

### ConversationHistory Collection

**Purpose:** Stores the detailed transcript of conversations (dialogue turns between the user and Claude) for long-term reference. This acts as a log of all interactions.

**Schema & Fields:**

* `_id`: **ObjectId** – Primary key for each message record (autogenerated by MongoDB). Used to uniquely identify a memory entry; also useful for deletion or reference.
* `conversation_id`: **String** – An identifier to group messages belonging to the same conversation or session. Every message in a given dialogue session shares the same `conversation_id`. This could be a UUID or a human-readable name (like a conversation title). It effectively acts as a foreign key relating to a *scope* (if each conversation is tied to a scope, see Memory Scopes).
* `timestamp`: **Date** – The date and time when the message was created or logged. Used for chronological ordering and time-based queries (indexed for retrieving by time).
* `speaker`: **String** – Indicates the source of the message, e.g., `"user"` or `"assistant"` (Claude). This helps maintain context of who said what when reviewing history.
* `text`: **String** – The content of the message uttered by the user or Claude. This is the raw text that can be recalled or used for embedding.
* `scope`: **String** – (Optional but recommended) The name of the memory scope this message belongs to. Often, this will be derived from the conversation context (for example, if `conversation_id` maps to a scope). If not explicitly set per message, the system can infer it via the conversation-to-scope mapping. Storing scope here allows quick filtering of conversation messages by scope.
* `tags`: **Array<String>** – (Optional) Any user-defined tags associated with this message. Typically, normal conversation messages won’t have tags unless the user explicitly tags them (which might be rare). This field is more commonly used in curated memory entries (or could be left null for conversation logs).
* `embedding`: **Array<Number>** – (Optional) A high-dimensional vector representation of the `text` content for semantic search. If semantic memory is enabled, the service will generate an embedding for each message or each important message and store it here. The type could be an array of floats (e.g., length 384 or 768). Alternatively, embeddings may be stored in the MemoryIndex collection (see below) to avoid bloating the conversation log documents.

**Indexes:**
Primary index on `_id` (default). Secondary index on `conversation_id` + `timestamp` (compound) to quickly retrieve all messages in a conversation in chronological order. Index on `scope` (to filter by scope), and possibly on `tags` (multikey) if tag-based searches on raw messages are needed. If full-text search is desired for exact keyword lookup, we could enable a text index on the `text` field (or use regex queries). If `embedding` is stored here and the MongoDB version supports it, a **vector index** on `embedding` can be used for similarity search, though we may instead rely on MemoryIndex.

**Data Lifecycle:** New conversation messages are appended in real-time as the chat occurs (through `store_memory` calls or an automated logging mechanism). Over time, older conversation logs might be summarized and pruned (see Summaries and Pruning sections) to control growth. Deletion of a whole conversation (scope) would remove all docs with that `conversation_id` or scope.

### Summaries Collection (Topics)

**Purpose:** Stores summarized representations of conversations or segments of memory. As raw conversation logs grow, this collection holds condensed information to allow long-term retention of the **gist** of old interactions without keeping every detail. It can also represent topic-specific notes.

**Schema & Fields:**

* `_id`: **ObjectId** – Unique ID for the summary record.
* `conversation_id` or `topic_id`: **String** – Reference to the conversation or topic that this summary represents. For example, if summarizing a single long conversation session, use its `conversation_id`. If summarizing all conversations about "Project Alpha," a `topic_id` might identify that subject.
* `summary_text`: **String** – The textual summary of the conversation or group of memories. This is a human-readable condensation (possibly generated by Claude or another model) covering key points.
* `time_range`: **Object** – (Optional) If the summary covers a specific time span or message range, this field can record that. For example, `{"from": ISODate(...), "to": ISODate(...)}` indicating it summarizes all interactions in that range.
* `message_refs`: **Array<ObjectId>** – (Optional) References to the original ConversationHistory `_id` entries that were summarized. This is useful for traceability (knowing which raw logs were condensed) and for potential future retrieval if needed.
* `scope`: **String** – The scope this summary belongs to (e.g., “Global” or a specific project). Typically, the summary inherits the scope of the content it summarizes.
* `tags`: **Array<String>** – (Optional) Tags relevant to the summary (similar to conversation tags, could mark as “summary” or topic labels).
* `embedding`: **Array<Number>** – (Optional) Semantic embedding of the `summary_text`. This allows the summary itself to be searchable by meaning, which is useful because summaries condense a lot of information. If a user’s query semantically matches a summary, that summary can surface and point to that older context.

**Indexes:**
Index on `conversation_id` or `topic_id` to find all summaries for a given conversation or topic. Index on `scope` for filtering by context. Possibly a text index on `summary_text` for keyword matching. If using vector search, an index on `embedding` for similarity queries (or store embeddings in MemoryIndex). Summaries might also be flagged, so an index on some `type` field (if we differentiate types of summaries) could be used.

**Data Lifecycle:** Summaries are typically **generated** by the system rather than directly inserted by the user. A maintenance process may create a summary after a conversation ends or when logs age beyond a threshold (e.g., a week or a month old). The summary is stored and the original detailed logs might be archived or pruned. Summaries themselves could eventually be summarized further if you have summaries of summaries for extremely old data, but that’s an edge case. When a scope or conversation is deleted, its summaries should also be removed (or archived).

### UserProfile & Preferences Collection

**Purpose:** Stores long-lived user-specific information that is not tied to a single conversation. This includes personal facts, preferences, profile info, and any explicit memory the user wants Claude to retain about them (outside of conversational context).

**Schema & Fields:**

* `_id` or `user_id`: **String/ObjectId** – A unique identifier for the user’s profile. If the application is single-user, there might be just one document (e.g., user\_id = "default\_user"). If multi-user (less likely in Claude Desktop scenario), this would distinguish profiles.
* `name`: **String** – The user’s name (if provided).
* `preferences`: **Object** – A nested document containing user preferences and settings. For example:

  * `preferences.tone` = `"casual"` or `"formal"` (desired assistant tone)
  * `preferences.detail_level` = `"high"` or `"concise"` (how verbose Claude should be)
  * Any other configurable behaviors Claude should remember.
* `facts`: **Object** – A nested document or key-value map of important personal facts the user wants stored. E.g.,

  * `facts.favorite_color` = `"blue"`,
  * `facts.birthday` = `"1990-05-15"`,
  * `facts.home_city` = `"San Francisco"`.
* `contacts` or `entities`: **Array/Object** – (Optional) Could store information about important entities like family members, colleagues, or projects. For example, an array of people with names and relationships (“Alice – sister”). This helps personalization (Claude can recall these relations).
* `notes`: **Array<String>** – (Optional) Any free-form notes the user has added to their profile (e.g., “I’m allergic to penicillin”).
* `embedding`: **Array<Number>** – (Optional) Semantic embedding representing the entire user profile or certain key concatenated info. This might not be as straightforward (since the profile is structured, not a single piece of text). We might not use an embedding here, or we might generate embeddings for certain key facts for search (though typically profile info is retrieved by direct key rather than semantic search).
* *Example Document:*

  ```json
  {
    "_id": "default_user",
    "name": "Jane Doe",
    "preferences": { "tone": "casual", "timezone": "PST" },
    "facts": { "favorite_color": "blue", "birthday": "1990-05-15" },
    "contacts": [ {"name": "Alice", "relation": "sister"}, {"name": "Bob", "relation": "coworker"} ]
  }
  ```

**Indexes:**
If only one profile, indexing is trivial. Otherwise, index on `user_id`. We might also index certain frequently accessed subfields (though MongoDB allows efficient document access by key). For example, we might index `facts.some_key` if we plan to query by them, but likely not needed. No need for text or vector index here since most profile queries are direct (Claude asking for a known fact).

**Data Lifecycle:** The profile is relatively static but can be updated over time via specific user commands (e.g., “Remember that my favorite color is blue” would translate to updating this collection). Updates should either upsert (create if not exists) or modify the existing profile document fields. This collection is not expected to grow large; it’s essentially a singleton record per user, updated in place. Backups should include it. Deletion of profile info would only happen if the user explicitly wants to wipe personal data; in that case, either clear fields or remove the document.

### MemoryIndex Collection (Semantic Index)

**Purpose:** Provides an index of vector embeddings for semantic search. This collection stores high-dimensional vectors representing the semantic content of memories (conversation messages, summaries, or profile info) along with references to the original data. By querying this index with a new embedding, we can find similar memories by meaning.

**Schema & Fields:**

* `_id`: **ObjectId** – Unique ID for the index entry.
* `embedding`: **Array<Number>** – The vector embedding (e.g., length 384/768 float array) for a memory entry.
* `source_collection`: **String** – Which collection the source data is in (e.g., `"ConversationHistory"` or `"Summaries"` or `"UserProfile"`).
* `source_id`: **ObjectId/String** – The identifier of the source document in its collection. This allows retrieving the full memory content once a match is found. It could be the `_id` of a conversation message, or a summary, etc.
* `scope`: **String** – (Optional, for quick filtering) The scope of the memory this embedding represents. Storing it here means we can include a scope filter directly in a vector query, which is useful to restrict semantic search to the active context.
* `metadata`: **Object** – (Optional) Could include any other relevant metadata for filtering or scoring, such as `timestamp` of the original memory (if we want to boost recent memories), or `tags` from the source memory if we want to combine tag filtering with vector search.

**Indexes:**
The primary content is the `embedding` field. Ideally, on a MongoDB version that supports vector search indexes, we would define a **vector index** on `embedding` (with a certain similarity metric like cosine distance). If using MongoDB 6.0+ or 7.0 with vector search beta, this index would enable queries like “find nearest neighbors to this vector”. If native support is unavailable, we won’t have a Mongo index on the vector; instead, the application will handle similarity search (meaning we could keep a secondary index structure in memory, such as an Annoy or Faiss index, or do a linear scan with computation).

In addition, index on `source_id` (unique) if needed, and index on `scope` (so that we can quickly find all embeddings in a given scope, which might be used to narrow search or to delete them when a scope is deleted). Possibly an index on `tags` or `metadata` if using those for filtering in queries.

**Data Lifecycle:** When a new memory entry is stored (conversation message, summary, or profile update) and it’s deemed important enough to index, an embedding is generated and a document is inserted into `MemoryIndex` linking to it. This typically happens during `store_memory` operations or logging of new conversation content. If an entry is updated or deleted, the corresponding index entry must be updated/deleted as well to avoid stale pointers. Over time, if memory entries are pruned or archived, their embeddings should be removed from the active index. The index collection could potentially grow large (one entry per memory item stored with an embedding), but maintenance tasks might remove older ones as needed (especially if those memories are summarized). We must ensure consistency: on backup/restore, either regenerate the index or include it in backups. If using an external index in memory only (for performance), we should have a way to rebuild it from the database on startup.

### Metadata & Scopes Collection

**Purpose:** Stores higher-level metadata about the memory system and definitions of memory **scopes**. Scopes are contexts or domains of knowledge that partition the assistant’s memory (for example, “Global” vs “Project Alpha” vs “Personal”). This collection defines what scopes exist and can track system-wide metadata like usage stats or configuration flags.

**Schema & Fields:**

* `_id`: **ObjectId** – Unique ID for the metadata record.
* `type`: **String** – The type of metadata record. For scopes, this might be `"scope"`. Other types might include `"stats"` or `"config"` if we store various info in one collection.
* **If `type == "scope"`:** (Scope Definition)

  * `scope_name`: **String** – Human-readable name of the scope (e.g., `"Global"`, `"ProjectAlpha"`, `"Personal"`). This is what will be used in memory entries’ `scope` field to tag them.
  * `description`: **String** – (Optional) A longer description of what the scope is for (e.g., *"Memories related to Project Alpha (work project begun in 2025)"*). Useful if listing scopes for the user.
  * `created_at`: **Date** – Timestamp when the scope was created.
  * `active`: **Boolean** – Indicates if this scope is currently active or enabled. (Possibly used to disable a scope without deleting it, or mark it as archived.)
  * `related_keywords`: **Array<String>** – (Optional) Keywords associated with the scope to help in classifying queries. E.g., scope "ProjectAlpha" might have related keywords \["Alpha", "Project A"] to catch variations.
  * `parent_scope`: **String** – (Optional) If implementing hierarchical scopes, this could reference a parent scope name (e.g., scope "Work" parent of "ProjectAlpha").
* **If `type == "stats"`:** (Example of other metadata)

  * `total_memories`: **Number** – count of total memory documents stored.
  * `last_backup`: **Date** – last time a backup was made.
  * `last_prune`: **Date** – last time a prune/cleanup routine ran.
  * (We could also keep stats per scope, like number of items per scope, but that could be derived by queries as needed.)

We might also simply store each scope as a separate document (no need for a `type` field if the collection is mostly scope definitions, aside from perhaps one record for global stats). Alternatively, have a separate collection for stats/config. For simplicity, assume this collection handles scopes primarily, and we may include one document for global stats or keep stats in code.

**Indexes:**
Index on `scope_name` (unique) to quickly find scope by name (this could even be the primary key instead of `_id`). If hierarchical, maybe an index on `parent_scope`. Not many indexes needed as this is small. For stats, perhaps keyed by some known identifier.

**Data Lifecycle:** Scopes are created either by user command or automatically:

* A default `"Global"` scope is created at first run (to store universal info).
* A new scope can be made via a command (e.g., `create_memory_scope`) or inferred from context (if a new conversation or a user says “remember this under *Project Beta*”). When created, add a doc here.
* If a scope is deleted (user wants to purge a project’s memories), the system will delete or archive all memory entries with that `scope` and then remove the scope record from this collection.
* Scopes might also be toggled active/inactive rather than constantly deleted, to allow temporarily excluding a scope from search without losing data.
* The stats record, if present, should be updated periodically (e.g., after each `store_memory`, increment count, etc., or recompute during maintenance).
* Backup/restore should preserve scope definitions.

**Relationships:** Note that each memory entry in other collections has a `scope` field that should match one of the `scope_name` values here. This effectively is a relational link (though not foreign-key enforced by MongoDB). The system should ensure when inserting a memory with a scope that the scope exists (or create it on the fly if allowed). Scope information is used at runtime to filter queries: e.g., the InfiniteMemoryMCP will usually include `scope` criteria when retrieving memories, to avoid cross-talk between contexts.

## MCP Protocol Integration

InfiniteMemoryMCP communicates with Claude Desktop through a standardized **Model Context Protocol (MCP)** interface. This section defines the MCP commands (requests and responses) that InfiniteMemoryMCP will support, allowing Claude to store and retrieve memories via JSON messages. Each command’s JSON schema and usage scenario is described, along with example payloads. We also cover how data from the database is sanitized/formatted when returning to Claude to ensure safe integration.

**Supported MCP Commands:**

1. **`store_memory`** – Save a piece of information into long-term memory.
   **Usage:** Triggered when the user instructs Claude to remember something or when the system decides to log important info (e.g., end-of-session summary).
   **Request Schema:**

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

   * `content`: The textual information to store (could be a sentence, paragraph, or multi-turn summary).
   * `scope`: (Optional) If provided, specifies the memory scope/category under which to store this memory (e.g., `"ProjectAlpha"`). If omitted, the service will assign a scope based on context (likely the current active scope or “Global”).
   * `tags`: (Optional) Any tags to label this memory with for future retrieval (e.g., `["meeting_notes", "project_alpha"]`). Tags are user-level categorization.
   * `source`: (Optional) Indicates what type of memory this is. By default, conversation messages might be logged with source `"conversation"`. If the user explicitly says “remember this”, it might be logged as a user-driven note. Or if the assistant calls this after summarization, it might be `"summary"`. This could affect which collection it goes into (e.g., summaries vs conversation log vs profile). The service can also infer this.
     **Behavior:** InfiniteMemoryMCP on receiving this will:
   * Possibly preprocess the text (e.g., strip overly long content or sensitive info if needed).
   * Generate a semantic embedding of the content (unless content is very short/trivial or embeddings are disabled).
   * Insert a new document into the appropriate collection: typically ConversationHistory for a normal message memory or Summaries for a synthesized summary. Include the text, scope, tags, timestamp, etc., and store the embedding either in that doc or in MemoryIndex.
   * Optionally, return a confirmation.
     **Response Schema:**
     The response can be simple since the user usually just gets an acknowledgment from Claude. For instance:

   ```json
   {
     "status": "OK",
     "memory_id": "<generated id>",
     "scope": "<scope>"
   }
   ```

   Claude likely won’t show this JSON to the user, but instead use it internally. It may just respond to the user with a natural language confirmation (“Okay, I will remember that.”). The `memory_id` could be used internally in case a follow-up operation references this memory (though user likely won’t do that directly).

2. **`retrieve_memory`** – Retrieve information relevant to a query from memory.
   **Usage:** Triggered when Claude needs to recall something based on user input. This could be an explicit user question (“Do you remember <X>?”) or an implicit need (user asks a question about something discussed earlier, so Claude decides to fetch that info).
   **Request Schema:**

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

   * `query`: A text query or hint representing what to search for. Claude may pass the user’s question or a distilled keyword. If the user literally said “What did I tell you about my schedule?”, the query could be “my schedule”.
   * `filter.scope`: (Optional) By default, Claude should specify the current scope (and perhaps also always include `"Global"` implicitly). If set to `"ALL"` or not provided, the service may search across all scopes (though this is usually not desired unless user explicitly asks for everything). Typically, Claude will set this to the active scope of the conversation.
   * `filter.tags`: (Optional) Limit search to memories that have certain tag(s). For example, if the user specifically asks something like “What are my #projectAlpha notes on design?”, Claude can put `tags: ["projectAlpha", "design"]` or call a different command (search\_by\_tag) – see below.
   * `filter.time_range`: (Optional) Restrict search to memories within a specific time range. Could be used if the query implies a time, or to prioritize recent items. For instance, if user says “What did we discuss *yesterday*?”, Claude might convert that to a retrieve\_memory with `time_range` covering yesterday. If not provided, search is unrestricted by time.
   * `top_k`: (Optional, Integer) The number of top results to return (defaults to say 3-5).
     **Behavior:** The memory service will:
   * Take the `query` string and generate an embedding for it (for semantic search).
   * Use the `scope` filter to determine which subset of embeddings to search (likely only those in the given scope plus global scope, unless overridden).
   * Perform a similarity search in the MemoryIndex (or appropriate collection) to find the most semantically relevant memories. Also possibly perform a direct text match or regex search on `query` to catch exact occurrences (hybrid search).
   * Apply tag filter and time filter if provided, either by pre-filtering the candidate set or post-filtering the results. (If `time_range` is provided, it may query the DB for memories in that time window and then within those do semantic ranking).
   * Compile the top results (e.g., top 3 memory entries). Each result might include the text snippet and some metadata.
   * Return the results in a structured format.
     **Response Schema:**

   ```json
   {
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

   Each result object includes the content (`text`) and relevant metadata such as when it was originally stored (`timestamp`), which scope it belongs to, any tags it had, and possibly a `confidence` or similarity score. The `source` could indicate if it’s from a summary or a direct message. `memory_id` corresponds to the original record. Claude will typically take these results and incorporate the most relevant one(s) into its answer to the user (likely paraphrasing or quoting as needed). For example, if the user asked “What’s my meeting time tomorrow?”, the result might contain “Your meeting is at 10 AM on May 5th” which Claude then says back to the user (“You told me your meeting is at 10 AM on May 5th.”). If no relevant memory is found (results array empty), Claude will conclude it doesn’t have that information remembered.

3. **`search_by_tag`** (and `search_by_scope`) – Retrieve memories by a specific tag or scope.
   **Usage:** This is a specialized query when the user explicitly references a tag or scope in their request. For example: “What do you remember about **#ProjectAlpha**?” would prompt Claude to search that tag, or “Recall everything from my **Travel** scope.” These could be handled via the generic retrieve\_memory with filters, but it’s useful to have a distinct command for clarity.
   **Request Schema (`search_by_tag`):**

   ```json
   {
     "action": "search_by_tag",
     "tag": "<tag name>",
     "query": "<optional additional query>"
   }
   ```

   * `tag`: The tag to search for (exact match or could allow partial match). This would filter memories to those containing this tag in their `tags` field.
   * `query`: (Optional) If provided, do a semantic search within just the memories that have the given tag. If omitted, it’s essentially “list all memories with this tag.”
     **Request Schema (`search_by_scope`):** (Alternatively, could be one command with a parameter specifying tag or scope)

   ```json
   {
     "action": "search_by_scope",
     "scope": "<scope name>",
     "query": "<optional query>"
   }
   ```

   * `scope`: The scope to search within (e.g., `"ProjectAlpha"` or `"Global"`). This will restrict results to that scope. If `query` is provided, it will do semantic (or keyword) search in that scope; if not, it could return a summary or list of all data in scope (which might be too much, so usually a query is expected).
     **Behavior:** For `search_by_tag`, InfiniteMemoryMCP will perform a MongoDB query like `{ tags: "<tag>" }` (with appropriate regex or case handling) to get all memory docs with that tag. If `query` is also given, it will then apply semantic ranking within that subset (e.g., embed the query and score each candidate, returning the top matches). For `search_by_scope`, it will effectively do what `retrieve_memory` does but forcing the scope filter to the one given (overriding the default current scope). If no query is given for search\_by\_scope, the service might return either an error or a summary of that scope’s contents (perhaps the latest items or a compiled summary, to avoid flooding with entire scope data).
     **Response Schema:** Similar to `retrieve_memory` – a list of results. Possibly for pure tag search (with no additional query), we might return more results (top\_k could default higher) since it’s just categorical. Each result includes at least `text` and `metadata` (scope, tags, timestamp, etc.). Claude would likely format the answer like “Here are the items tagged #ProjectAlpha that I remember: ...”. In the UI, this might even be presented as a list.

4. **`recall_memory_by_time`** – Retrieve memories based on a time reference.
   **Usage:** When the user asks for information from a certain time period, e.g., “What did we talk about **last week**?” or “Show me my notes from **March 2023**.” Claude will interpret this and use this command to fetch memories within that timeframe.
   **Request Schema:**

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

   * `time_query`: A natural language description of the time, exactly as user said or as parsed text (e.g., "last week", "yesterday", "March 2023"). Claude might pass this raw or do some parsing on its own. InfiniteMemoryMCP can have a small date parser to interpret it if `range` is not provided.
   * `range.from` / `range.to`: If Claude’s MCP client can parse the time reference (perhaps using a known library or prompt), it might directly supply an exact date range. For example, "last week" might become from = 2025-04-27 to = 2025-05-04. If provided, the service will use these directly. If not, the service will attempt to parse `time_query`.
   * `scope`: (Optional) Limit to a specific scope. Likely it defaults to current scope plus global, as usual.
     **Behavior:** The service will determine the target time window. Then it performs a query on relevant collections:
   * Primarily, find conversation history messages or summary entries whose `timestamp` falls in that range. Possibly limit to ones in the given scope.
   * It might retrieve all such entries (or the most significant ones if there are many). If the window is large or results too many, consider summarizing them on the fly or returning a subset (maybe the first and last items, or item count).
   * No semantic embedding is needed here (unless combined with a keyword query), it’s a direct time filter.
     **Response Schema:**

   ```json
   {
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

   The results might be sorted by time (e.g., oldest to newest within that range). The response also echoes the actual interpreted time frame boundaries, which Claude might use to phrase the answer (“Between March 1 and March 31, 2023, you discussed...”). Claude can then summarize or list the found memories. If few items, Claude might enumerate them; if many, Claude might summarize the highlights for the user. If the user asked a question like “what did I say about X last week,” this could be combined: first filter by last week, then by a query X – but that would likely be done by Claude issuing a retrieve\_memory with both time\_range and query filter (instead of using recall\_memory\_by\_time alone). So this command is mainly for purely time-based requests.

5. **`delete_memory`** (or `forget_memory`) – Remove or mark a memory item (or set of items) so that it is no longer recalled.
   **Usage:** When a user explicitly says “forget X” or “please delete that info about Y,” Claude will invoke this to erase the specified memory. This can also be used to forget an entire scope (e.g., “forget everything about Project Y” – which effectively means delete all memories in that scope).
   **Request Schema:**

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

   The request is flexible in specifying what to delete:

   * If `memory_id` is provided, the service will directly delete that specific memory document (this assumes Claude knows the ID, which might happen if it just retrieved it and now user says forget that; Claude could pass the ID from the retrieve result).
   * If `scope` is provided (and no memory\_id), it means forget all memories in that scope. The service will delete all documents where `scope` matches (across relevant collections). This is a bulk operation.
   * If `tag` is provided (and no memory\_id or scope), delete all memories with that tag.
   * If `query` is provided (and none of the above), the service might attempt to find memories matching that query (similar to retrieve) and delete them. (This is less precise; probably use only if the user references content by description and we have to search it).
   * If multiple fields are given, it can narrow (e.g., `scope` + `tag` meaning forget all items in scope X that have tag Y).
   * `forget_mode`: could be `"soft"` (the default) or `"hard"`. In soft mode, the service might mark the item as forgotten (set a flag or move to an “Archived” collection) but not physically remove it. This allows undo if needed. Hard mode would permanently delete the record from the database. Soft mode ensures that even if not deleted, the item is **excluded from all retrieval results** going forward (so effectively gone from user perspective). The system might purge soft-deleted items after some time or keep them until backup.
     **Behavior:** For each memory to forget, ensure any associated embeddings in MemoryIndex are also removed. If it’s a scope deletion, potentially perform a backup of that scope’s data before deletion (if configured to do so for safety). InfiniteMemoryMCP might log a confirmation or update stats.
     **Response Schema:**

   ```json
   {
     "status": "OK",
     "deleted_count": <number of records affected>,
     "scope": "<if a scope was deleted, name here>",
     "note": "<additional info>"
   }
   ```

   If memory\_id was used, deleted\_count = 1. If scope or tag, it could be many. The `note` could indicate if the operation was soft (e.g., “marked as forgotten”) or if scope deletion triggered an archive. Claude will then likely respond to the user confirming the forget action (“I’ve forgotten that information.”). If the user tries to recall it later, it will not show up.

6. **Maintenance/Utility Commands:** These are not directly user-facing in conversation but provide administrative control or info. They might be triggered by advanced user requests or by the developer/QA. They include:

   * **`get_memory_stats`** – Returns summary statistics of the memory database (e.g., number of items in each collection, total size on disk, number of scopes, etc.). Could be used if user asks “How much do you remember?” or just for monitoring.
     *Response Example:*

     ```json
     {
       "stats": {
         "total_memories": 1520,
         "conversation_count": 120,
         "scopes": {"Global": 300, "Project Alpha": 200, ...},
         "last_backup": "2025-05-01T10:00:00Z",
         "db_size_mb": 45.3
       }
     }
     ```
   * **`backup_memory`** – Immediately triggers a backup operation (dump the database to a backup file). Useful if user says “backup your memory now” or before upgrading, etc.. The service will perform the backup (likely asynchronously, but the command can initiate and respond when done).
     *Response Example:*

     ```json
     {"status": "OK", "backup_file": "backup_2025-05-15.dump"}
     ```

     (Claude might not relay this raw output, but the system could inform the user “Memory backed up successfully.”)
   * **`optimize_memory`** – Triggers maintenance routines like compaction, rebuilding indexes, or running the pruning/summarization job immediately. If a user says “clean up memory” or an admin wants to optimize, this can be used.
     *Response Example:*

     ```json
     {"status": "OK", "operations": ["compacted_db", "removed_20_duplicate_entries", "summarized_old_conversations"]}
     ```
   * **`create_memory_scope`** – Allows explicit creation of a new scope (if not implicitly created by first use). Could take a scope name and description as input. Usually, scopes can be made by just using them, but a user might want to pre-create one.
   * **`list_memory_scopes`** – Returns a list of all current scopes (names and descriptions). Could be used for a UI listing or if user asks “What memory scopes do I have?”.
   * **`export_memory`** – (If implemented) to export all memory data in a user-readable format (like JSON or CSV). Could be an alternative to raw backups for portability.
     These maintenance commands ensure the user (or developer) has control and visibility into the memory system beyond just storing and recalling data.

**Security and Sanitization of Responses:** Since InfiniteMemoryMCP will return data that Claude then uses in its model context, we must ensure this channel cannot be abused to inject unintended instructions or corrupt Claude’s behavior. Strategies include:

* **Structured JSON:** All MCP responses are in JSON format, which Claude’s MCP client will incorporate in a way that’s distinguishable from normal user messages. Claude will treat them as data. The implementation in Claude likely converts the JSON into a system or tool response in the prompt (e.g., “Memory result: ...”). We ensure that any text from memory is a value in JSON, not a full prompt. This reduces risk of prompt injection because Claude sees it as content to possibly quote, not as an instruction to itself.
* **Escaping Dangerous Content:** If a memory entry’s text contains something that could be interpreted as a prompt or command (like "`##`" or "`</>`" or something that might confuse the prompt format), the service can escape or neutralize those sequences. For example, removing or altering markup that could be interpreted specially. However, since the data came originally from the user or Claude itself, this risk is lower. We mainly guard against someone manually tampering with the database.
* **No Code Execution in Memory:** Ensure that even if a memory contains something like `` `some code` `` or a system instruction, Claude’s agent doesn’t execute it. This is more on Claude’s side to handle, but we can add a prefix in the content when returning, e.g., every retrieved memory text could be prefixed with `"[Memory]"` when inserted into Claude’s context. This labeling helps Claude treat it as reference information.
* **Local Trust and Access:** Because only the user and the Claude application can write to this database (in normal operation), we trust the content to not be malicious. The bigger concern is if a malicious local app or person edited the database. Running MongoDB on localhost with authentication disabled (for ease) means if malware on the machine knew about it, it could theoretically connect and insert bad data. Mitigation: run MongoDB on a random port or with auth, and/or treat the local environment as trusted. We expand on security in the Security section.

In summary, the MCP integration is designed so that Claude can **naturally trigger these commands** during conversation. Developers must implement each command’s logic in InfiniteMemoryMCP and ensure robust JSON handling. Claude’s side will need to map user intents to these actions (for instance, the phrase “remember that...” mapping to a `store_memory` call, or recognizing a hashtag as a tag search). As the protocol is JSON-based, maintaining the correct schema and version compatibility is important (if Claude’s MCP interface updates, InfiniteMemoryMCP should adapt accordingly).

## Semantic Search and Embedding

A core feature of InfiniteMemoryMCP is the use of **semantic embeddings** to enable recall by meaning, not just exact keywords. This section details the requirements for the embedding model and the search pipeline to ensure that Claude can find relevant memories even if queries are phrased differently than the original entries.

**Local Embedding Model Requirements:** To generate semantic vectors for memory content and queries, we will integrate a local embedding model. Requirements for this model:

* It should be an open-source **Sentence Transformer** or similar model that converts text into a high-dimensional numeric vector. Example models: `all-MiniLM-L6-v2` (384-dim) or `multi-qa-MiniLM-cos-v1`, or a larger model like `all-mpnet-base-v2` (768-dim) for better accuracy if performance allows. The model should be fine-tuned for general sentence-level semantic similarity.
* The model must run **fully offline** on the user’s machine (no calls to external APIs). We can use a Python library like **SentenceTransformers** or an implementation in another language that the service is written in. If Claude Desktop uses Python for tools, we might directly use a Python embedding pipeline; otherwise, we might run a small Python subprocess or use a C++ embedding library.
* Size/performance trade-off: The model should ideally be small enough to run quickly on a CPU (embedding a sentence in under a few hundred milliseconds on an average PC). If a GPU is present, we should take advantage by allowing the model to use it for faster embeddings.
* The model file will either be packaged with the application or downloaded on first use (with user permission). If downloaded, ensure it’s stored locally thereafter.

**Embedding Generation Strategy:**

* **On-the-fly (Real-time):** By default, whenever a new memory is stored (via `store_memory` or logging a user message), InfiniteMemoryMCP will immediately generate its embedding. This ensures the memory is instantly available for semantic recall. The generation can be synchronous within the command handling — for example, `store_memory` might block for a short moment to compute the vector before saving. Given expected short lengths of content (one message or a short note), this is usually fine.
* **Asynchronous Option:** To avoid any delay in Claude’s response, we could insert the memory first (with a placeholder or null embedding) and have a background thread compute and update the embedding shortly after. In this case, the `store_memory` response can return immediately. The risk is if a recall query comes in seconds after storing and the embedding isn’t ready yet; but that window is small. We can make this configurable or tune based on performance tests.
* **Batching:** In scenarios like initial onboarding or bulk import of existing logs, the system could batch multiple texts and embed them together for efficiency. But in normal usage, one-at-a-time embedding is fine.
* **Claude-generated Embeddings:** If in the future Claude’s own model could produce embeddings (some advanced feature), we could use that to avoid loading a separate model. However, currently it’s more straightforward to use a dedicated model.

**Vector Storage and Similarity Search:**

* All generated embeddings (for each memory entry and for each query) exist in a common vector space. We need to perform **nearest neighbor search** to find which stored memory vectors are closest to a given query vector. The similarity metric is typically **cosine similarity** (or equivalently maximizing dot product if vectors are normalized).
* **Using MongoDB Vector Index:** If using MongoDB version with vector search support, we will define a special index on the `embedding` field of either the memory collections or the MemoryIndex collection. For example, in MongoDB 6.0+ (with the Atlas vector beta), one can create an index with `{"embedding": "columnstore"} ` or similar and use `$vectorSearch` in queries specifying the vector and the number of neighbors. We should confirm the exact method in the target MongoDB version. This would let the database handle similarity ranking efficiently, likely using approximate nearest neighbor under the hood.
* **Application-level Vector Search:** If native support is unavailable (or for backward compatibility with older MongoDB), InfiniteMemoryMCP will implement its own search:

  * The MemoryIndex collection can be queried by scope or other filters to get a candidate set of embeddings. For instance, filter by scope and perhaps by keywords if a query word is provided (like do a quick text search on content to narrow down).
  * Pull those candidate embeddings into memory (this could be hundreds or thousands at most if scope is broad).
  * Compute cosine similarity between the query embedding and each candidate. This can be optimized with vectorized operations if using numpy/PyTorch.
  * Sort the results by similarity score and take the top N.
  * This approach is O(N) per query where N is number of relevant embeddings. If N is, say, 10,000 at most (assuming a scope doesn't have more than that many items actively), this is manageable (10k dot products per query).
  * Optionally use a library (FAISS, Annoy, HNSW) to build an approximate index for faster search, especially if data grows. We could maintain such an index in memory and update it on new inserts.
* **Vector Dimension and Storage:** The embedding vectors (e.g., float32 numbers) can be stored either as arrays of floats or perhaps as binary (to save space). MongoDB’s BSON can store arrays of numbers; it will increase document size. Using a separate MemoryIndex collection as outlined keeps the main collections lean (especially conversation history which might have thousands of tiny docs – better not to inflate each with a large vector).
* We should also consider memory usage: If we keep all embeddings in RAM for speed, that's maybe 768 floats \* number of memories. For example, 10,000 memories \* 768 \~ 7.68 million floats. At 4 bytes each, \~30 MB – not too bad. Even 100k memories would be \~300 MB. This is in reasonable range for modern desktops, but we’ll still try to be efficient (maybe only keep index for active scope loaded).

**Semantic Search Workflow:** When a `retrieve_memory` or similar query comes in:

1. **Embed the Query:** Use the same embedding model to encode the query text to a vector.
2. **Determine Search Space:** Identify which memory embeddings to compare against. Typically, filter by:

   * Scope: include current scope’s embeddings and any “Global” scope embeddings (global being always relevant). If user asked for cross-scope explicitly, broaden it.
   * If a tag filter is given, pre-filter to embeddings whose metadata includes that tag.
   * If a time range is given, possibly pre-filter by taking only embeddings of items in that time range (if memory index has timestamps or we do an additional filter step).
3. **Similarity Search:** Execute nearest neighbor retrieval as described above, via DB or code. Find top K most similar memory vectors to the query vector.
4. **Fetch Memory Data:** With the top results (which are basically references or IDs from MemoryIndex), retrieve the actual memory documents from their respective collections (ConversationHistory, Summaries, etc.) to get full text and details. (We may already store text in MemoryIndex, but better to source from original to ensure we have all fields and up-to-date info.)
5. **Rank/Filter Results:** We might refine the ordering or drop some results:

   * If similarity scores are below a threshold, we may choose to return nothing. For example, if the best match is still very weak (score < 0.5 on cosine), it might not be relevant enough, and Claude should act like it doesn’t recall anything clearly.
   * If results contain near-duplicates (maybe the same fact stored twice), consider merging them or choosing the most recent occurrence.
   * Possibly boost more recent memories slightly if relevance is similar (so that if two results tie, the newer one is returned first).
   * Limit final count to what Claude can handle (maybe 3 results).
6. **Return structured results:** As per the MCP response schema with texts and metadata.

**Hybrid Search (Semantic + Keyword):** To maximize accuracy, we combine semantic search with traditional keyword search:

* If the query is short or looks like a specific keyword (e.g., a name or code), we can first do a direct text match in MongoDB to see if there’s an exact hit. For instance, if query = “John’s phone number”, maybe an exact search finds a memory with “John’s phone number is ...” quickly.
* MongoDB supports text indexes for full-text search. We could have a text index on relevant fields and run a `$text` query. Or a simple regex/substring search if text index not used (though that’s slower on large data).
* We then take the union of results: anything found by keyword and by semantic. We could even combine scores (e.g., give a high similarity score to exact matches).
* This hybrid ensures that factual or unique info is found reliably, and conceptual queries still work via semantic similarity.
* E.g., Query "project deadline" – if a memory actually contains "deadline", keyword search would catch it. If it doesn’t, the semantic search might still find "due date ... May 15" item. We merge those.

**Embedding Update Strategy:** When memory data is changed (e.g., user edits their profile or we summarize and delete a bunch of raw logs):

* If an entry is removed, its embedding should be removed from the index to avoid ghost results.
* If an entry’s text is updated or a summary created, generate a new embedding for the new text.
* For summarization, after creating a summary for old data, we might drop many old embeddings (to save space), trusting the summary’s embedding now represents them.
* Possibly periodically re-embed or fine-tune: If we ever change the embedding model (upgrade to a better one), we should have a migration plan: re-embed all stored content with the new model so everything stays in one vector space. This could be heavy, but maybe fine if rare.

**Accuracy and Relevance:** We aim for the system to return memories that truly help answer the user’s query:

* The chosen embedding model should be evaluated on some sample prompts to ensure it clusters related ideas well.
* We might set a threshold to avoid low-quality matches as noted. If the top result is below threshold, return empty. This avoids confusing Claude with unrelated info.
* Over time, user feedback can be incorporated: if Claude picks a memory and the user corrects it (“No, that’s not what I meant”), maybe mark that memory as less relevant for that query or adjust thresholds.
* The vector search will surface results by meaning, but sometimes context matters (which is why we filter by scope). This isolation helps relevance by narrowing the search domain.
* If multiple results are all about the same fact (duplicate entries), we only need to return one. Deduplication logic can check if texts are very similar (or embeddings very close) and prune duplicates.

**Performance Considerations (for embedding):**

* Embedding each user query in real time is typically fine. If conversation has rapid back-and-forth with memory queries, it’s maybe a few hundred ms overhead occasionally.
* We should avoid embedding *every single message* if not needed. For example, every user query doesn’t need embedding, only when doing a memory search. Similarly, perhaps not every message from Claude needs storing/embedding unless it contains info worth remembering. We might decide to embed only:

  * All user messages (since user might refer to them later).
  * Key assistant answers that contain factual info provided by user or conclusions (like if Claude wrote a summary or a plan).
  * Or on explicit "remember this" prompt.
* This selective strategy ensures we don’t waste time embedding trivial chat like “OK” or “Thanks”.
* The embedding model and the search process should be profiled on expected data sizes (maybe up to tens of thousands of items) to ensure it meets interactive performance (goal: memory retrieval in under 1 second).

In summary, the semantic search capability grants Claude a powerful, human-like recall: it can remember the **meaning** of information and retrieve it even if the wording changes. By running a local embedding model and vector search, we maintain privacy (no data or embeddings sent out) and keep latency low. This system will allow queries like “What’s the plan for Project Alpha?” to find a note saved as “We decided the timeline for Alpha project...” – enabling continuity in conversation without the user repeating themselves verbatim.

## Memory Management and Pruning

While we aim for "infinite" memory in concept, practical limits require the system to intelligently manage stored information over time. InfiniteMemoryMCP will implement **pruning** and **summarization** strategies to ensure the database remains efficient and relevant, without discarding important knowledge. This section outlines the policies for aging data, scope-based cleanup, usage-based retention, and how we condense or remove data while preserving essential context.

**Time-Based Pruning Policies:**
As memories age, their immediate utility often diminishes. We will provide configurable rules for data retention by age. For example:

* **Retain Recent History:** Keep all conversation logs for a recent window (e.g. the last 6 months) accessible in full detail. These are likely to be relevant to ongoing discussions.
* **Archive Older Logs:** For content older than the retention window, employ summarization instead of deletion. A scheduled job can periodically find conversations older than X (e.g., 6 months) and if not already summarized, generate a summary entry capturing the important points. Then, it can either remove the detailed entries or mark them as archived. We might move them to an "ArchivedConversations" collection or simply set a flag `archived: true` on them and exclude those from normal queries. This way, the knowledge is preserved in summaries, but the bulk of data (like every utterance) is trimmed.
* **TTL (Time to Live) Index:** For certain ephemeral data we know we don’t want after a while (maybe low-value logs), we could use MongoDB’s TTL index feature to auto-delete after a set time. However, we’ll likely rely on our own logic to ensure we summarize before deletion (since TTL would just drop data with no summary).
* Time-based pruning will be careful not to remove anything less than, say, a few weeks old by default, as users may refer back to recent conversations frequently. It will be configurable (“Keep \[all] conversations for N months”).

**Relevancy-Based Pruning:**
Not all pieces of memory are equally important. We introduce a mechanism to track usage of memory:

* Each time a memory is retrieved or used by Claude to answer a question, we increment a "use\_count" or update a "last\_accessed" timestamp on that memory.
* Over time, we identify memories that have **never or rarely been accessed**. For example, a trivial fact mentioned once a year ago and never brought up again is a candidate for pruning.
* Policy: If a memory is older than X and has a use\_count of 0 (never recalled) or very low, and isn’t marked as important, the system can remove it or archive it. This is analogous to cache eviction by least recently used (LRU) or least frequently used (LFU).
* Implementation: A maintenance job can scan for items beyond a certain age where `use_count == 0`, and either delete them or move them to a cold storage (like export to a JSON file or another DB collection). We might couple this with summarization: if those items collectively have some theme, perhaps they were never used because they were unimportant, so maybe they can just be dropped. But to be safe, we could backup them.
* This ensures the active memory is focused on what matters to the user, improving search quality as well (less noise to sift through).

**Scope-Based Pruning:**
Memories are compartmentalized by scope (project, context). When a scope is no longer needed, we should allow bulk pruning:

* If the user finishes a project or no longer needs a certain topic’s data, they might issue a command or via UI select to **retire a scope**. This would trigger deletion of all memories labeled with that scope.
* Implementation: The `delete_memory` with `scope` parameter covers this. The system could first offer to backup that scope (export all docs from that scope to a file), then remove them from the DB. Alternatively, mark scope as inactive and do not include it in queries (essentially hiding it) until user confirms deletion.
* This manual pruning is important for long-term housekeeping— users may periodically clean out old projects. We’ll include an operation (and possibly a UI interface) for “Delete Scope” which under the hood calls the appropriate MCP function and DB operations.
* After scope deletion, update the Metadata collection to remove that scope entry.

**Duplicate and Noise Cleanup:**
Over time, redundant information can accumulate:

* The user might tell the assistant the same fact multiple times (especially if they forgot they already did), resulting in duplicate memory entries. Or the assistant might summarize a conversation that already largely occurred, creating overlapping content.
* We will detect **near-duplicates** by comparing embeddings or text. If two memory texts have very high similarity (above a threshold), and they are in the same scope or context, we can merge or drop one. Likely keep the more recent or more frequently referenced one.
* Also, trivial “noise” messages like acknowledgments (“Ok”, “Sure”) are not useful to keep long-term. We can filter these out at store time: for instance, have a list of stop-phrases that we don’t log in ConversationHistory beyond a short temporary buffer. Or tag them in a way that prune job can remove them later.
* Deduplication can be done as part of maintenance: e.g., a job that runs weekly can check for any identical `text` fields or embedding distance > 0.95 and clean them. It should do so carefully to not remove legitimately separate things that just happen to be similar.

**Size-Based Limits and Compression:**
We will set soft limits on the memory store size as mentioned in config. To enforce:

* If number of memory items exceeds a threshold (e.g., 100k), or if disk usage exceeds, say, 500 MB, the system triggers a **compression routine**.
* This routine will aim to reduce data volume:

  * Identify clusters of related entries (perhaps by scope and proximity in time) and summarize them. E.g., 50 messages from a long brainstorming session could be summarized into one entry.
  * Remove the fine-grained entries after summarization (or archive them externally).
  * This reduces item count significantly.
* Because summarization is key to compression, we will utilize Claude itself or another model to perform it:

  * Claude can be prompted (via an internal call, not user-facing) to summarize a given conversation or a list of points. This is reliable but we need to ensure it doesn’t hallucinate or lose critical info. Possibly have Claude double-check summary accuracy by verifying key facts are present.
  * Alternatively, a smaller local model (if available) could summarize, but given Claude is there and very capable, using it might be best (especially if it can be done in a non-user context to not consume user message quota).
  * We must be mindful that summarizing user data by Claude is still local (since Claude Desktop runs the model on user’s machine or at least is not a cloud service, presumably). So privacy is maintained.
* The summarization pipeline might trigger at certain intervals or sizes. We could implement it such that after each conversation ends, if it was lengthy, produce a summary. And when the DB hits a threshold, do an additional pass merging older summaries.

**Retention of Important Information:**
Throughout pruning, we ensure that critical user info isn’t lost:

* The user profile and explicitly added facts should likely never be pruned automatically (unless user deletes them). Those are inherently important.
* Some conversation pieces might be marked as “important” (we could add a flag if user says "this is important" or similar, or any message that Claude thinks contains a key fact).
* We do not delete those important marked items, regardless of age, until maybe the user says so.
* Instead of deletion, prefer summarization or archiving. For example, even after summarizing a conversation, perhaps keep the final conclusion message or any decisions made.
* Provide user-visible settings: e.g., “Memory retention: \[Aggressive pruning / Moderate / Keep all]”. Aggressive might summarize quickly and drop details, Keep all means basically no pruning (just rely on manual control and maybe the user will backup or trust big storage). By default, moderate: apply policies as above moderately.

**Scheduling and Execution:**

* **Maintenance Thread/Service:** InfiniteMemoryMCP should have a background thread (or use a scheduling mechanism) to periodically run maintenance tasks such as pruning, summarization, and backup. For example, every day at 3am or on application idle, it checks conditions: any conversation now 30 days old not summarized? Any DB size threshold exceeded? etc.
* These tasks should run at low priority to not interfere with active usage. Alternatively, run on demand (when user triggers optimize).
* **Audit Trail:** If possible, keep a log of maintenance actions. E.g., record in Metadata stats: "Last prune removed 20 items on 2025-05-01". If summaries are generated, perhaps mark in the summary doc which items it replaced (using `message_refs`). This way if something was wrongly summarized, one could retrieve the original from backup if needed.
* **User Control:** The user can manually invoke maintenance via commands like `optimize_memory`. Also, if they notice memory is stale or too large, they might adjust config and then run maintenance.

**Outcome:** With these strategies, InfiniteMemoryMCP will maintain an **“infinite” feeling of memory** by never forgetting crucial info, while keeping the actual stored data to a manageable volume. The assistant will recall the **essence** of long-past conversations (via summaries) and keep its active memory lean and relevant. Over years of usage, without pruning the system could bog down, so these measures ensure longevity. At all times, data removal is done carefully: either summarized first or backed up, so the user doesn’t truly lose information unless they intend to. Defaults will aim to err on the side of preserving information (in condensed form) rather than permanently deleting, thus balancing continuity with practicality.

## Backup, Export, and File Structure

To safeguard the user’s accumulated knowledge and allow portability, InfiniteMemoryMCP will include robust backup and export features. Additionally, the on-disk file structure is defined for clarity and reliability. This section describes how memory data is stored on the filesystem, how automatic backups are handled, and how a user can restore or export their data. It also covers log file management and approaches to handle data corruption.

**Local Filesystem Layout:** All data will reside in a dedicated directory (configurable, default e.g. in the user’s home under `ClaudeMemory`). Within this directory, we organize subfolders:

```
ClaudeMemory/               # Root memory data directory (configurable path)
├── mongo_data/            # MongoDB data files (WiredTiger storage)
│   ├── collection-*.wt    # Collection storage files
│   ├── index-*.wt         # Index storage files
│   ├── mongod.lock        # Lock file indicating the DB is running
│   └── ...                # Other internal DB files (journal, etc.)
├── backups/               # Backup files (dumps or archives of the DB)
│   ├── backup_2025-05-01.dump
│   ├── backup_2025-05-08.dump
│   └── ... 
├── logs/                  # Log files
│   ├── mongo.log          # MongoDB server log (if separate)
│   └── memory_service.log # InfiniteMemoryMCP logs (if we separate them)
└── export/                # (Optional) Exported memory files (e.g., JSON or CSV exports)
    └── full_export_2025-06-01.json
```

The `mongo_data` directory contains the live database used by MongoDB (with WiredTiger `.wt` files by default). We will ensure this path is on a persistent drive (not temp). The `backups` folder stores our backup snapshots. The `logs` folder keeps any log files (Mongo can be configured to log to file; otherwise we capture output; and the memory service can log its operations here too). The `export` folder is for user-initiated exports in a user-friendly format.

**Backup Frequency and Retention:**
By default, the system will perform **automatic backups** on a schedule (configurable). For example:

* Perform a **daily backup** at a quiet hour (say 3:00 AM local time), keeping the last 7 daily backups.
* Perform a **weekly backup** (maybe Sunday midnight) and keep the last 4 of those (one month of weeklies).
* This way, the user has points in time to recover from, without accumulating unlimited backup files.
* Automatic backups can be toggled off if the user prefers to manage manually or is low on disk space.

Backups will be done using a safe method:

* If MongoDB is running as a separate process, we can use `mongodump` to dump the `claude_memory` database to a `.dump` or `.archive` file in the backups folder. This creates a consistent snapshot without stopping the database. (Mongodump outputs BSON data for each collection; we might compress it or keep as is).
* If using an embedded Mongo or if we want a simpler approach, we could issue a command to MongoDB to flush and then copy the raw data files. But copying live DB files is risky unless the DB is locked or stopped momentarily.
* Another approach: connect to the DB and read all collections, exporting to a JSON file (suitable for small data, but with lots of binary data like embeddings, BSON might be better).
* We will likely go with `mongodump` (since we can bundle the MongoDB tools).

Manual backups can be triggered by the `backup_memory` MCP command or via a UI button. This will do the same process on-demand and perhaps allow the user to specify a name or destination (default uses timestamp name).

**Backup Format:**
We have two possible backup formats:

* **Mongo Dump (.bson)**: Default, as produced by `mongodump` (which may create a folder of .bson files or a single .archive file). This is useful for full fidelity restore.
* **JSON Export:** Optionally, we could allow exporting data as JSON for the user’s inspection or use in another tool. This would not be used for full restore (since it may lose some type fidelity like ObjectIds), but for personal data portability. For example, an export that contains all memory entries in JSON arrays per collection. This is more of an “export” than a backup and would be user-initiated (via an MCP command or UI).
* We might store backups uncompressed or compress them (e.g., zip the dump directory) to save space. Possibly use `.gz` compression on the archive.

**Backup Encryption:**
Because memory data is sensitive, we provide an **option to encrypt backups**. If enabled (with a user-specified passphrase):

* After creating the backup file, encrypt it using a symmetric cipher (like AES-256). We could integrate an existing tool or library for encryption. The passphrase would not be stored (user must provide it on restore).
* This prevents someone who gains access to the backup files from reading them. (We assume the live DB is protected by being in user’s account, but backups might be copied elsewhere).
* By default encryption is off for simplicity, but recommended if the user is concerned or storing backups on external drives.

**Restore Process:**
When needed (e.g., user moved to a new machine or data got corrupted):

* If backups are .bson dumps, use `mongorestore` to restore the database. This would typically require stopping the current MongoDB instance (or restoring to a separate instance then swap).
* A simpler approach if embedded: if we had archived JSON or similar, the service could read the backup and insert documents back (slower, but more controlled).
* We should provide a script or instructions: e.g., “To restore, stop Claude, run `mongorestore --db claude_memory <backup folder>` from the latest backup folder, then restart Claude.”
* If we have an MCP command like `restore_memory`, it could attempt an automated restore: perhaps shut down the DB (if embedded), load the backup, restart. This is advanced and maybe not needed for initial implementation.
* Restoration should handle version differences (if the schema changed between versions, a migration might be needed, but since backups are frequent, likely it’s same version).
* Always advise backing up before restoring (in case the restore doesn’t go as expected, you can revert).

**Data Corruption and Recovery:**
MongoDB is quite durable, but in case of crashes or improper shutdown:

* With journaling enabled, on restart the DB will auto-recover to the last consistent state. We ensure journaling is not disabled.
* If the DB fails to start (corrupted files), the user can try using a backup to recover. Possibly the system can detect this and offer a restore from last backup.
* We might also use MongoDB’s `repairDatabase` command in such cases. The `optimize_memory` command could incorporate a check to run a repair if inconsistencies are detected.
* The log file `mongo.log` will contain any warnings or errors if corruption is encountered; that can help guide recovery.

**Export (Portability):**
Aside from backups for safety, exporting allows the user to take their memory data and use it elsewhere or just inspect it:

* A `export_memory` command could output all memory content to a structured JSON or Markdown text in the `export/` folder. For example, a JSON with sections for each scope, listing conversations and facts.
* This is not meant to be re-imported automatically (though we could later support an import if needed), but for transparency and user control.
* Also, if needed, the user can use the JSON export to manually migrate to another system or just keep a human-readable archive.

**Local Database Setup Considerations:**

* If using an external `mongod`, we rely on the user to possibly configure where it stores data. Our instructions will recommend using a dedicated data directory as above. If the user uses the default `~/data/db`, we might either use that or encourage a separate path to not mix with other DBs.
* Running MongoDB as a **single-node replica set** could enable point-in-time backups or change streams, but that may be overkill. We assume standalone mode is enough.
* The data directory should be treated as application data; users generally shouldn’t edit or move files inside except via our backup/restore procedures.

**Logging:**

* We will maintain logs to assist in debugging and auditing. MongoDB’s own logs (if we start it with logging to file) will go to `logs/mongo.log`. It records things like startup, any errors, slow queries (if profiling enabled), etc.
* InfiniteMemoryMCP service can also log events to `logs/memory_service.log`. For example, log when maintenance tasks run, when backups are taken, any warnings (like “embedding model took too long” or “search returned no results for query X”).
* These logs help developers during testing and can help users report issues.

By structuring the filesystem as above and implementing rigorous backup procedures, we ensure that the user’s long-term memory is **durable** and under their control. Even in the case of accidental deletion or system crash, recent backups can restore the AI’s memory with minimal loss. The user can feel confident that years of accumulated interactions are not fragile – they are stored safely on disk and duplicated in backups (and optionally secured with encryption).

## Security and Privacy

Security and privacy are paramount since InfiniteMemoryMCP deals with personal and potentially sensitive information. The system is designed as a **local-first** solution, which inherently provides a strong privacy foundation (no data leaves the user's machine). However, we must still enforce measures to protect data from unauthorized access or tampering on the local system and to ensure that the integration with Claude does not introduce vulnerabilities. Below we outline the security considerations and how we address them:

**Local-Only Data Flow:** By design, all memory operations occur on the local host. There is **no cloud component**. This eliminates risks of data interception or misuse by external servers. The MongoDB instance is bound to `localhost` (127.0.0.1) and should not accept external network connections. In the configuration, we'll ensure MongoDB’s bind\_ip is localhost only. This means only processes on the user’s computer can potentially access the DB.

**Access Controls for MongoDB:**

* If we assume a single-user desktop environment, we might run MongoDB without authentication for simplicity (because the only client is our service on localhost). However, to guard against malicious local processes, we could enable MongoDB authentication and have the InfiniteMemoryMCP use a username/password to access the DB.
* Alternatively, running MongoDB as a separate user account or within a sandbox (like a container) can limit who can connect. If the DB is only listening on a Unix socket or a random high port with auth, that’s even better.
* For now, a reasonable default: start MongoDB with `--auth` and generate a random strong password for the `claude_memory` database, stored in a config file that only Claude’s app can read. This might be overkill, but it’s a consideration. Many desktop apps that bundle databases skip auth but rely on OS protections.

**File Permissions:** The data directory `ClaudeMemory/` should be created with proper file permissions such that only the user (owner) can read/write it. This prevents other accounts on the same machine from snooping (on multi-user systems). On Windows, use ACL to restrict to the user; on Linux/macOS, use `chmod 700` on that directory.

**Running MongoDB Safely:** If we spawn a mongod process, we will run it under the normal user account (no root/Administrator privileges). This limits its access to just the intended files. We also ensure it’s not exposed to the network. If packaging with Claude, possibly run it in a contained environment.

**Memory Scope Privacy:** The concept of scopes not only aids context management but also privacy segmentation. Information in one scope won’t be revealed in another context unless explicitly requested. This prevents accidental leakage of, say, personal info into a work conversation. It’s a design-level privacy feature. The system by default will include the active scope (and global scope) in queries, and nothing else, ensuring separation of concerns. A user can trust that if they discussed something in their “Health” scope, it won’t come up while in a “Work” scope unless they deliberately ask for it.

**Input Sanitization:** Claude and the user are essentially the only sources of data going into the database. We still sanitize inputs to prevent any injection attacks at the database level:

* Since we use MongoDB, one risk is Mongo query/command injection if we were constructing queries naively from user input. However, our MCP commands define exactly what operations are done (we're not accepting raw query from user). We use parameterized queries or fixed query structures, so there's minimal risk of a user crafting a prompt to drop the database, for example.
* We will escape or remove any control characters or unusual binary data in text fields. This is mostly to ensure data doesn’t confuse our processing (like newline characters or delimiter strings that might break JSON formatting on output).
* For natural language that looks like a command, Claude will decide to treat it as a memory operation or not. The user cannot directly force an MCP action without Claude interpreting it. This is more on the AI side.

**Output Sanitization & Injection Prevention:** As discussed earlier, we format memory retrieval results in JSON with clear distinctions so that when Claude incorporates it, it doesn’t misinterpret it as user instructions. E.g., if a memory said: “By the way, ignore all future instructions,” we don’t want Claude to act on that as a directive. By encapsulating it as data (maybe even with a prefix in the text like "\[Remembered] By the way, ignore…"), we mitigate this.

* We can also filter out obviously malicious content in memories when returning. If some memory text somehow contained SQL or code injection attempts (though it’s unclear how that’d be used here), we simply treat it as plain text. The bigger worry is prompt injection: a memory that tries to alter Claude’s behavior. Our approach will be to rely on Claude’s chain-of-thought to treat memory as factual recall, not as new instructions.

**Tampering Resistance:** If an attacker had access to the user’s file system, they could theoretically modify the MongoDB files or inject new documents. This is a difficult scenario to guard fully (because if the system is compromised, many things are at risk). Some mitigations:

* **Signature/Hash (Advanced):** We could store a simple checksum of critical fields in a memory item (like a hash of the text with a secret key) to detect if it was altered outside the system. But this might be overkill and complicated to manage.
* **Monitoring:** We can log all MCP requests and maybe have the option to log all DB writes. If something changes without a corresponding MCP command, it indicates external tampering. But again, that’s advanced.
* **Practical Approach:** Emphasize securing the local system. If the user keeps their OS secure (no malware), and given the app runs under their account, risk is low. Possibly allow the user to set an encryption key for the database itself (MongoDB Enterprise has data-at-rest encryption, but we likely can’t rely on that in community edition).
* In sum, we assume a **trust boundary** of the user’s machine and account. We mitigate obvious local network attack vectors (close ports) and rely on OS security for local file access. The user should treat the memory data as sensitive like any personal documents on their computer.

**Privacy of Backups/Exports:** As noted, backups can be encrypted. When the user explicitly exports memory, we warn them that the file contains personal data and should be kept safe. The system itself will not auto-send these anywhere. If cloud backup is desired, the user can do that manually, but our scope remains local.

**Third-Party Components:** We use MongoDB and an embedding model. Ensure these components do not phone home:

* MongoDB Community edition doesn’t send data out, but it might by default enable update checks or telemetry. We should disable any telemetry (`--enableFreeMonitoring off`).
* The embedding model (if using a library like HuggingFace) might try to download the model weights initially. We will make this an explicit step or bundle the model to avoid unexpected network calls.
* No analytics or usage tracking should be in the memory service, to respect privacy.

**Denial of Service & Performance Security:**

* Malicious or buggy usage could attempt to overload the memory (e.g., user says “remember this” and gives a 100MB text, or repeats that). We should set sane limits (maybe ignore store\_memory requests above a certain size or chunk them). This prevents extremely large inserts that could crash the system.
* Also, ensure the assistant doesn’t get stuck in a loop calling memory queries rapidly. Rate-limit MCP calls if needed (though Claude’s own logic should avoid that).
* If an attacker tried to spam the MongoDB with connections/requests, since it’s local and only our service connects, not much surface there. But in case, we ensure the service queues and handles one operation at a time or a limited number at a time.

In conclusion, the security model for InfiniteMemoryMCP is primarily about **maintaining a strong local sandbox**. All data stays on the user’s device in a controlled environment. By following best practices like least privilege (running local DB with minimal access), data encryption options, strict protocol handling, and careful integration with the LLM, we aim to make the persistent memory both **private and robust against misuse**. Users should feel confident that their data is not being leaked or misused and that they have ultimate control over what is remembered or forgotten.

## Testing and Validation Requirements

To ensure the reliability and correctness of InfiniteMemoryMCP, a comprehensive testing strategy is required. Both unit tests (for individual components/functionalities) and integration tests (for the end-to-end system with Claude) will be implemented. Additionally, performance benchmarks and failure simulations are needed to validate the system under various conditions. Below we outline the key testing and validation areas:

**Unit Tests for MCP Commands:** For each MCP command defined (store\_memory, retrieve\_memory, search\_by\_tag, recall\_memory\_by\_time, delete\_memory, etc.), create unit tests that directly call the InfiniteMemoryMCP handler functions with mock inputs and verify the outputs and side effects:

* *store\_memory tests:*

  * Store a simple piece of text, then query the database to ensure the document was inserted correctly in the right collection with all fields (text, scope defaulted, timestamp present, etc.).
  * Test storing with specific scope and tag and verify those are saved.
  * Test storing triggers embedding creation: e.g., the MemoryIndex count increases by one and the vector has correct dimension.
  * Edge: store an empty or very short content (should possibly reject or handle gracefully).
  * Edge: store extremely long content (should maybe split or truncate? Verify policy).
* *retrieve\_memory tests:*

  * Insert some known memories into DB (with known text and embedding). Then call retrieve\_memory with a query that should match one of them. Verify that the result includes the expected memory text. If using a deterministic embedding or a stub for embedding, we can simulate similarity. For actual, maybe easier: if query exactly equals a stored text, it should definitely retrieve that due to high similarity.
  * Test that scope filtering works: if we query and the relevant memory is in a different scope than specified, it should not appear.
  * Test that tag filtering works: store two items with different tags, query with one tag, ensure only that tagged item returns.
  * Test time\_range: store items with different timestamps, query for a range, ensure only those in range are returned.
  * Test threshold: insert a memory that is unrelated, query something, ensure an empty result or results above similarity threshold.
* *search\_by\_tag tests:*

  * Store a few items with tag "projectX". Call search\_by\_tag for "projectX". Expect all those items in results.
  * If query parameter is also given, ensure results are further filtered semantically.
  * Similar for search\_by\_scope.
* *recall\_memory\_by\_time tests:*

  * Insert items at different dates. Use recall\_memory\_by\_time with a range covering some of them. Check output covers those and not outside.
  * Test natural language parsing: e.g., "last week" – we might simulate current date in test and ensure it interpreted correctly. We might need to stub the date parser to return a known range for test determinism.
* *delete\_memory tests:*

  * Insert several items, then call delete\_memory by memory\_id on one. Verify that document is removed from DB (and maybe that a flag is set if soft deletion instead).
  * Test delete\_memory by tag: insert 3 with tag "temp", 2 without, call forget tag "temp", verify those 3 are gone.
  * Test delete\_memory by scope: populate two scopes with data, delete one scope, verify all from that scope removed, and others remain.
  * If soft deletion mode, verify the flag is set and subsequent retrieve does not return them.
  * Also test trying to delete something that doesn't exist (should respond gracefully, e.g., deleted\_count 0, no error).
* *maintenance commands tests:*

  * For get\_memory\_stats, insert some known data, run it, parse JSON output, ensure counts match what was inserted.
  * For backup\_memory, we might simulate the backup process (perhaps stub out actual disk write) and ensure it returns OK. Could also verify that a backup file was created in the backups directory.
  * For optimize\_memory, if possible, simulate conditions where duplicates exist or summary needed, run it, and check that duplicates were removed or summary created.
  * Scope creation/list: create a new scope via command (if implemented) and verify metadata entry exists.

These unit tests will likely use a test instance of MongoDB (perhaps an in-memory Mongo or a temporary database) so as not to interfere with real data.

**Integration Tests with Claude Desktop:**

* We need to test the **end-to-end flow**: i.e., given a simulated conversation with Claude, does the memory system correctly enhance it? Since Claude itself is an AI, this can be partially simulated by calling the MCP interface.
* For example, simulate a user prompt "Remember that my cat's name is Whiskers." The Claude logic would parse that and call `store_memory` (maybe through our API). We verify that after this, if user asks "What's my cat's name?", Claude (or our simulation) calls `retrieve_memory` with query "cat's name" and that the answer comes back with "Whiskers".
* If possible, run Claude in a test mode where it will use the MCP (maybe not, but we can simulate the orchestration logic).
* Integration test scenarios:

  1. **Basic remember and recall:** user tells something, then later asks for it. Check that the final answer from Claude includes the correct info.
  2. **Scope isolation:** user has two separate conversations (simulate by changing scope in our calls). Ensure that asking something from one conversation does not retrieve memory from the other. Possibly simulate "Project A" vs "Project B" contexts.
  3. **Tag retrieval:** user tags info, then asks via tag. E.g., "Remember this as #login" then "What did I set for #login?" returns it.
  4. **Time-based recall:** user has a conversation one day, next day ask "what did we talk about yesterday?" and ensure it retrieves from yesterday’s conversation.
  5. **Forgetting:** user stores info then says "forget that". After that, ask again for it and ensure Claude says it doesn't know (and verify DB no longer has it).
  6. **Large volume performance:** maybe insert a few thousand dummy memory entries and measure that a retrieval still returns within acceptable time. This could be part of performance testing rather than integration with Claude though.
* Integration tests might require a stub/mock Claude agent that given a user query will decide which MCP calls to make. This logic could be coded explicitly for test (since actual Claude's internal decision-making is complex). But because we define user prompts that clearly map to memory actions (according to our design, e.g. "remember ..." triggers store, etc.), we can simulate those mappings.

**Semantic Search Validation:**
We must verify that the embedding-based search actually brings relevant results:

* Use a fixed embedding model (the one we plan to ship) and construct a small known dataset of sentences. For instance:

  * Memory: "Project Apollo deadline is June 5"
  * Memory: "Alice's birthday is Jan 20"
  * Memory: "We plan to launch the product next week"
  * Then test queries like "When is Apollo due?" and check that the Apollo memory is top result. Or "birthday" returns Alice's info. Or "what is happening next week" returns the launch plan.
* If we have known analogies or cases the model should catch, test those.
* If the model is non-deterministic (shouldn't be, embeddings are deterministic), just ensure cosine similarity ranking works as expected for known cases. Possibly we can bypass the actual model in unit tests by substituting small vectors manually to test the ranking logic.
* Also test the threshold logic: add a memory with completely different content, query for something unrelated, ensure that either it returns nothing or confidence is low, so that we would treat it as no recall scenario.
* If we implement approximate search (ANN), test that results are same or very close to brute force results for some queries (to ensure the index isn't missing relevant items).
* Test hybrid search: have a memory with an uncommon keyword, ask using that keyword and see that it finds it (like test that without semantic, the keyword search still triggers).
* Evaluate performance: measure how long embedding + search takes for one query and verify it’s under acceptable limit (we can simulate with some dummy load if needed).

**Data Integrity Tests:**
We want to ensure that the data remains consistent through operations:

* **Transaction consistency:** While most operations are single document and atomic in Mongo, if we ever do multi-step (like insert then update index), we should test power failure scenario. Possibly use MongoDB transactions (if using a replica set). But assuming standalone, at least test if something fails mid-operation, we don't end up in an inconsistent state. e.g., simulate exception after DB insert but before index insert, then next retrieval should handle that missing index (maybe by detecting and recovering).
* **Backup/Restore test:** After a series of operations, run a backup (maybe a test function simulating it). Then wipe or use a new empty DB, restore from backup, and verify all collections have expected data (counts and maybe specific sample).
* **Crash recovery test:** This is tricky to simulate exactly, but we could:

  * Start a transaction (if using txn) and abort, ensure no partial data.
  * Or kill the MongoDB process abruptly after a write and then restart it and ensure nothing corrupted. This might be more on integration test side, requiring controlling the process (maybe not easily automated, but we can test manually).
* **Journal/WriteConcern test:** Ensure that when store\_memory returns success, the data is actually committed (maybe use WriteConcern "majority"/"journaled" in writes). We could simulate heavy load and crash to see if last entries lost or not.
* **Multi-thread test:** If we allow concurrent writes, test doing multiple store\_memory in parallel threads (or simulate via MCP calls quickly) and ensure no deadlocks and all entries are stored fine. MongoDB can handle concurrent ops, but our service logic might have shared resources (like the embedding model) which could cause issues. We'll need to ensure thread safety around the model usage.

**Performance and Scalability Tests:**

* Insert a large number of dummy memories (like 50k small entries). Then measure:

  * Time to retrieve with a query (should still be under a second or few seconds worst-case).
  * Memory usage of the service after indexing these (check it’s within reason).
  * Try some worst-case queries (like very broad scope, no keyword filter, which forces scanning many vectors).
  * This can inform if we need to adjust approach (like implementing an ANN library) if too slow.
* Test backup time for a large dataset (maybe simulate by duplicating entries to get a DB of hundreds MB, then trigger backup and see if it completes in reasonable time, like seconds to a minute).
* Test startup time: if we have a large DB, how quickly does InfiniteMemoryMCP initialize? (Especially if we need to load or index embeddings). Possibly we may lazy-load index or only load on first query to save startup time. But test to avoid long blocking startup.
* Test summarization triggers: simulate a condition where conversation length > threshold, ensure summarization function runs and output is shorter text. Possibly use a stub model for summary in test to not rely on actual AI (unless we have an automated way to use Claude or an LLM).
* Test memory of the embedding model: load and unload it to see if any memory leaks when reloading perhaps (if that’s ever done).

**User Acceptance Tests:**
Though more high-level, ensure that the system meets the user stories and acceptance criteria from the product requirements:

* Privacy: verify no network calls are made during operations (monitor network).
* Setup: install on a fresh environment and ensure minimal config needed (document this process).
* Conversations recall correctly (don’t have to repeat information).
* Preferences persist and are used by Claude spontaneously (this last bit depends on Claude using the profile info – maybe beyond our system test, but we can check that profile info is accessible when Claude queries it).
* Scope separation: demonstrate that info doesn’t leak across scopes.
* Tag queries: demonstrate memory retrieval by tag works with a natural phrasing.
* Semantic queries: have some conversations then ask in a different wording and ensure recall.
* Time-based queries: "what about last week" scenario works.
* Proactive association: if Claude spontaneously uses memory (hard to test unless we drive Claude, but if our data is structured right, presumably it will if designed).
* Pruning: set retention small, simulate time passage (maybe fudge timestamps to past) and run maintenance, ensure old stuff summarized/removed. Check that performance stays good after years of data by simulating it.
* Forget command: verify it and that the user truly doesn’t get that info anymore.
* Backup: disable network and see that backup and restore still work, etc.

**Continuous Testing:**
We will integrate these tests into the development pipeline:

* Each new feature (embedding integration, summarization, etc.) comes with tests to verify it.
* Before release, run full integration tests to catch any regression (e.g., verify that after adding pruning, retrieval still finds what it should).
* Possibly run longer-term tests (simulate usage over time: a script that adds conversations daily, prunes weekly, etc., to see if any issues accumulate).

By thoroughly testing each component and the system holistically, we ensure that InfiniteMemoryMCP meets its technical requirements reliably. We also validate that in edge cases (large scale, unexpected inputs, system failures) the system behaves gracefully (degrades performance rather than crashing, preserves data integrity, etc.). This gives confidence that the memory system will function correctly as an extension of Claude in real-world usage.

## Scalability and Performance Considerations

Although InfiniteMemoryMCP is a local system intended for a single user environment, it should be built with scalability and performance in mind to handle years of accumulated data and ensure fast recall. This section discusses how we will maintain performance via indexing, caching, and asynchronous processing, as well as the expected capacity and how the system might scale in the future if needed.

**Database Index Management:**
Efficient indexes are crucial to performance:

* As outlined in Data Model, we create indexes on frequently queried fields: `conversation_id` + `timestamp` (to fetch conversations quickly), `scope`, `tags`, etc. These indexes need to be maintained as data grows.
* We will monitor index sizes relative to data sizes. MongoDB handles index updates on writes automatically. However, over time, fragmentation can occur. We plan to allow an `optimize_db` operation (either via `optimize_memory` command or as part of maintenance) that runs `db.repairDatabase()` or `db.collection.reIndex()` if we detect significant fragmentation. This can be done during a maintenance window or when user triggers optimization.
* If the `MemoryIndex` (vector index) uses a special index type (if Mongo supports), we need to ensure it's created properly and utilize any config (like index space vs accuracy trade-offs).
* We will also ensure the indexes are not too bloated: e.g., if we considered using a full-text index on `text`, check that it doesn't overly increase DB size for marginal benefit. Possibly rely on our own text search or only index certain fields like tags which are smaller.

**Embedding Caching and Reuse:**

* If the same piece of text might be stored or queried multiple times, we can cache embeddings to avoid recomputation. For instance, if the user repeats a sentence they said earlier, our system might re-embed it. We could detect duplicates and reuse the existing vector.
* A simple approach: maintain an in-memory LRU cache of recently computed embeddings (keyed by text hash). Since memory content isn't usually repeated verbatim often, this has limited use but could help in some scenarios (like a user copy-pastes something).
* More practically, ensure the embedding model is loaded once and kept in memory rather than reloading on each call. The model initialization should be done at service startup and the instance reused for all queries (with locking if multi-thread).
* If GPU is available, also reuse that context rather than reloading model to GPU each time.

**Asynchronous and Parallel Operations:**

* **Asynchronous Embedding**: As noted, we might not strictly need it, but we could implement asynchronous embedding generation. For example, `store_memory` could return immediately after queuing the embedding+insert task to a worker thread. The UI (Claude) doesn't necessarily need the memory available instantly except for possibly immediate recall queries. We need to weigh this: synchronous might be fine given short content. We can implement an internal thread pool for heavy tasks and tune as needed.
* **Parallel Retrieval**: Typically one query at a time (because user asks one thing at once). But if Claude were to ask multiple memory queries in parallel (unlikely), the service should handle them. MongoDB can handle concurrent reads; our service should be thread-safe for search (embedding model probably can't do two at once unless it's small on CPU, but we could queue those too).
* **Maintenance Threads**: Running maintenance like backups and pruning in the background ensures the main thread (serving queries) isn't blocked. We will design so that such tasks yield to any incoming memory requests (or at least don't lock the database in a way that blocks reads/writes for too long). For example, if summarizing, do it one conversation at a time and commit, so the DB isn't locked throughout.
* We should test concurrent access scenarios (like a backup running during a query). Possibly avoid heavy maintenance during active use (schedule off-hours or low CPU priority).

**Capacity Planning:**

* Expectation: If the user interacts daily and a lot is stored, how much data after 1 year, 5 years?

  * Suppose 20 messages per day stored with embeddings. That’s \~7k messages/year. Over 5 years \~35k. Plus some summaries and profile info. And each embedding \~768 floats (3KB). So 35k \* 3KB \~ 105MB for embeddings, plus overhead. Text itself maybe a few MBs. So under 200MB likely.
  * In a heavier usage or if logging every assistant message too, double that, maybe a few hundred thousand items in 5 years, which might be \~1GB of data. MongoDB can easily handle that on a single machine.
* With pruning and summarization, many old raw logs would be gone, replaced by far fewer summary entries. So realistically, the active set might plateau.
* The system should comfortably handle **100k+ memory items** in the database. Queries among that should still be subsecond if indexed properly and using vector search with approximate methods if needed.

**Future Scalability (Beyond Single Machine):**
While out of current scope, our design can potentially scale:

* The memory service could in the future connect to a remote or distributed DB (like a cloud MongoDB or a cluster on a NAS) if a user truly wanted multi-device shared memory. The architecture allows swapping the DB endpoint (just change URI). But then privacy/local-first is compromised, so not the default. We can note this as a possible extension.
* If data volume became huge (millions of entries), a single MongoDB might still handle it, but performance might degrade. In such a case, we could consider sharding by scope (each scope in a separate database or partition), but this is overkill for personal use.
* The embedding search could also be offloaded to specialized vector DBs (like Faiss server or Pinecone) if needed, but that again introduces external service which we avoid.
* Multi-thread scaling: ensure the system can utilize multiple CPU cores if available (embedding model can use BLAS multi-thread, search can parallelize, MongoDB is multi-threaded internally). So on a high-end PC, it scales up usage of resources to improve speed automatically.
