"""
Main entry point for InfiniteMemoryMCP.

This module sets up and runs the InfiniteMemoryMCP service, connecting
to MongoDB and starting the MCP server.
"""

import atexit
import signal
import sys
import time

from .db.mongo_manager import mongo_manager
from .mcp.commands import register_command_handlers
from .mcp.mcp_server import mcp_server
from .utils.logging import logger


def setup_signal_handlers():
    """Set up signal handlers for graceful shutdown."""
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down")
        shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def shutdown():
    """Perform cleanup and shutdown."""
    logger.info("Shutting down InfiniteMemoryMCP")
    
    # Stop the MCP server
    mcp_server.stop()
    
    # Stop MongoDB connection
    mongo_manager.stop()
    
    logger.info("Shutdown complete")


def startup():
    """Initialize and start all services."""
    logger.info("Starting InfiniteMemoryMCP")
    
    # Start MongoDB connection
    if not mongo_manager.start():
        logger.error("Failed to connect to MongoDB, exiting")
        sys.exit(1)
    
    # Register MCP command handlers
    register_command_handlers()
    
    # Start MCP server
    mcp_server.start()
    
    logger.info("InfiniteMemoryMCP startup complete")


def main():
    """Main entry point."""
    # Set up signal handlers
    setup_signal_handlers()
    
    # Register shutdown function to run at exit
    atexit.register(shutdown)
    
    # Start all services
    startup()
    
    # Keep the main thread running
    logger.info("InfiniteMemoryMCP running, press Ctrl+C to stop")
    try:
        # Main thread just sleeps, letting the MCP server thread do the work
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        # atexit will call shutdown
        pass


if __name__ == "__main__":
    main() 