"""
Configuration management for InfiniteMemoryMCP.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

CONFIG_PATHS = [
    "./config/config.json",
    "~/ClaudeMemory/config.json",
    "/etc/claude/infinite_memory_config.json",
]

DEFAULT_CONFIG = {
    "database": {
        "mode": "embedded",
        "uri": "mongodb://localhost:27017/claude_memory",
        "path": "~/ClaudeMemory/mongo_data",
        "max_memory_items": 100000,
        "max_memory_size_mb": 500,
    },
    "embedding": {
        "model_name": "all-MiniLM-L6-v2",
        "device": "cpu",
    },
    "backup": {
        "enabled": True,
        "frequency": "daily",
        "retention": 7,
        "encryption_enabled": False,
        "encryption_passphrase": "",
    },
    "memory": {
        "default_scope": "Global",
        "auto_create_scope": True,
        "retention_days": 180,
    },
    "logging": {
        "level": "INFO",
        "file": "~/ClaudeMemory/logs/memory_service.log",
    },
}


class ConfigManager:
    """Manages configuration for the InfiniteMemoryMCP system."""

    def __init__(self):
        """Initialize the configuration manager."""
        self.config: Dict[str, Any] = {}
        self.config_path: Optional[str] = None
        self.load_config()

    def load_config(self) -> None:
        """
        Load configuration from a file.

        Searches through CONFIG_PATHS to find a valid config file.
        Falls back to default configuration if no file is found.
        """
        for path in CONFIG_PATHS:
            expanded_path = os.path.expanduser(path)
            if os.path.exists(expanded_path):
                try:
                    with open(expanded_path, "r", encoding="utf-8") as f:
                        self.config = json.load(f)
                    self.config_path = expanded_path
                    print(f"Loaded configuration from {expanded_path}")
                    return
                except (json.JSONDecodeError, OSError) as e:
                    print(f"Error loading config from {expanded_path}: {e}")

        # No valid config found, use defaults
        self.config = DEFAULT_CONFIG
        print("Using default configuration")

    def save_config(self, path: Optional[str] = None) -> None:
        """
        Save the current configuration to a file.

        Args:
            path: Optional path to save the config. If None, uses the path
                 the config was loaded from, or the first path in CONFIG_PATHS.
        """
        if path is None:
            path = self.config_path or CONFIG_PATHS[0]

        path = os.path.expanduser(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
            print(f"Configuration saved to {path}")
        except OSError as e:
            print(f"Error saving configuration to {path}: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: The key to look up, using dot notation for nested keys.
            default: The default value to return if the key is not found.

        Returns:
            The configuration value, or the default if not found.
        """
        keys = key.split(".")
        value = self.config
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value.

        Args:
            key: The key to set, using dot notation for nested keys.
            value: The value to set.
        """
        keys = key.split(".")
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value

    def get_database_path(self) -> str:
        """
        Get the expanded database path.

        Returns:
            The expanded path to the MongoDB data directory.
        """
        path = self.get("database.path", "~/ClaudeMemory/mongo_data")
        return os.path.expanduser(path)

    def get_log_file_path(self) -> str:
        """
        Get the expanded log file path.

        Returns:
            The expanded path to the log file.
        """
        path = self.get("logging.log_file", "~/ClaudeMemory/logs/memory_service.log")
        return os.path.expanduser(path)


# Create a singleton instance
config_manager = ConfigManager() 