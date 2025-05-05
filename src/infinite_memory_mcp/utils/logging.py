"""
Logging configuration for InfiniteMemoryMCP.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional

from .config import config_manager


def setup_logging(
    level: Optional[str] = None, 
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    Configure and get the logger for InfiniteMemoryMCP.

    Args:
        level: Log level to use. If None, use the level from config.
        log_file: Path to the log file. If None, use the path from config.

    Returns:
        The configured logger instance.
    """
    if level is None:
        level = config_manager.get("logging.level", "INFO")
    
    if log_file is None:
        log_file = config_manager.get_log_file_path()
    
    # Create directory for log file if it doesn't exist
    log_dir = os.path.dirname(log_file)
    os.makedirs(log_dir, exist_ok=True)
    
    # Get the numeric log level
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        print(f"Invalid log level: {level}, using INFO")
        numeric_level = logging.INFO
    
    # Configure the root logger
    logger = logging.getLogger("infinite_memory_mcp")
    logger.setLevel(numeric_level)
    
    # Create handlers
    console_handler = logging.StreamHandler(sys.stdout)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5, encoding="utf-8"
    )
    
    # Set the level for handlers
    console_handler.setLevel(numeric_level)
    file_handler.setLevel(numeric_level)
    
    # Initialize the filters attribute
    console_handler.filters = []
    file_handler.filters = []
    
    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Set formatter and add handlers
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    # Return logger without calling logger.info to avoid issues in tests
    return logger


# Create a singleton logger instance
logger = setup_logging() 