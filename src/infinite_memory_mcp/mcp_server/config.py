"""
Configuration settings for the InfiniteMemoryMCP native MCP server.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass
class MongoDBConfig:
    """MongoDB configuration."""
    uri: str = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/")
    database: str = os.environ.get("MONGODB_DATABASE", "claude_memory")
    memories_collection: str = "conversation_history"
    scopes_collection: str = "memory_scopes"

@dataclass
class EmbeddingConfig:
    """Embedding model configuration."""
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    dimension: int = 384
    batch_size: int = 32

@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = os.environ.get("LOG_LEVEL", "INFO")
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

@dataclass
class MCPServerConfig:
    """Main MCP server configuration."""
    name: str = "InfiniteMemoryMCP"
    version: str = "1.0.0"
    protocol_version: str = "2025-03-26"
    default_scope: str = "global"
    mongodb: MongoDBConfig = field(default_factory=MongoDBConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    
    @classmethod
    def from_dict(cls, config_dict: Dict) -> "MCPServerConfig":
        """Create a config object from a dictionary."""
        # Set up server properties
        name = config_dict.get("server", {}).get("name", cls.name)
        version = config_dict.get("server", {}).get("version", cls.version)
        protocol_version = config_dict.get("server", {}).get("default_protocol_version", cls.protocol_version)
        default_scope = config_dict.get("default_scope", cls.default_scope)
        
        # Set up MongoDB config
        mongodb_config = MongoDBConfig(
            uri=config_dict.get("mongodb", {}).get("uri", MongoDBConfig.uri),
            database=config_dict.get("mongodb", {}).get("database", MongoDBConfig.database),
            memories_collection=config_dict.get("mongodb", {}).get("collections", {}).get("memories", MongoDBConfig.memories_collection),
            scopes_collection=config_dict.get("mongodb", {}).get("collections", {}).get("scopes", MongoDBConfig.scopes_collection),
        )
        
        # Set up embedding config
        embedding_config = EmbeddingConfig(
            model_name=config_dict.get("embedding", {}).get("model", EmbeddingConfig.model_name),
            dimension=config_dict.get("embedding", {}).get("dimension", EmbeddingConfig.dimension),
            batch_size=config_dict.get("embedding", {}).get("batch_size", EmbeddingConfig.batch_size),
        )
        
        # Set up logging config
        logging_config = LoggingConfig(
            level=config_dict.get("logging", {}).get("level", LoggingConfig.level),
            format=config_dict.get("logging", {}).get("format", LoggingConfig.format),
        )
        
        return cls(
            name=name,
            version=version,
            protocol_version=protocol_version,
            default_scope=default_scope,
            mongodb=mongodb_config,
            embedding=embedding_config,
            logging=logging_config,
        ) 