#!/usr/bin/env python3
"""
Direct launcher for InfiniteMemoryMCP MCP server.
This script avoids module imports and directly runs the necessary code.
"""

import os
import sys
import json
import logging
import traceback
from pymongo import MongoClient
from sentence_transformers import SentenceTransformer
from fastmcp import FastMCP, Context
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("infinite_memory_mcp")

# Current directory is the root of the project
current_dir = os.path.dirname(os.path.abspath(__file__))
logger.info(f"Direct launcher starting from: {current_dir}")

# Set up MongoDB connection
MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/")
DB_NAME = os.environ.get("MONGODB_DATABASE", "claude_memory")
logger.info(f"Connecting to MongoDB at {MONGODB_URI}")

try:
    mongo_client = MongoClient(MONGODB_URI)
    db = mongo_client[DB_NAME]
    memories_collection = db["conversation_history"]
    scopes_collection = db["memory_scopes"]
except Exception as e:
    logger.error(f"Error connecting to MongoDB: {e}")
    sys.exit(1)

# Set up embedding model
logger.info("Loading embedding model")
try:
    embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
except Exception as e:
    logger.error(f"Error loading embedding model: {e}")
    sys.exit(1)

# Set up MCP server
logger.info("Initializing FastMCP server")
mcp = FastMCP(
    name="InfiniteMemoryMCP",
    version="1.0.0",
    default_protocol_version="2025-03-26"
)

# Register a basic memory store tool
@mcp.tool("store_memory", "Store a new memory")
async def store_memory(context: Context, text: str, tags=None) -> str:
    memory_doc = {
        "text": text,
        "tags": tags or [],
        "scope": "global",
        "created_at": str(datetime.now())
    }
    memories_collection.insert_one(memory_doc)
    return f"Memory stored: {text}"

# Run the server with stdio transport
logger.info("Starting FastMCP server with stdio transport")
try:
    mcp.run(transport="stdio")
except Exception as e:
    logger.error(f"Error running MCP server: {e}")
    traceback.print_exc()
    sys.exit(1) 