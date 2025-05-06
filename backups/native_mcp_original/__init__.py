"""
Native MCP implementation for InfiniteMemoryMCP.

This package provides a native MCP server implementation for InfiniteMemoryMCP,
allowing direct integration with Claude Desktop and other MCP clients without
the need for an adapter layer.
"""

from .server import InfiniteMemoryMCP
from .config import MCPServerConfig, MongoDBConfig, EmbeddingConfig

__all__ = ["InfiniteMemoryMCP", "MCPServerConfig", "MongoDBConfig", "EmbeddingConfig"] 