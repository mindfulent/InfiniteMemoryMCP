"""
Main entry point for InfiniteMemoryMCP.

This module sets up and runs the InfiniteMemoryMCP service,
connecting directly to MongoDB and starting the native MCP server without an adapter layer.
"""

import argparse
import json
import logging
import os
import sys
import traceback

from .mcp_server import InfiniteMemoryMCP, MCPServerConfig

def main():
    """Main entry point."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run InfiniteMemoryMCP with native MCP support")
    parser.add_argument("--config", help="Path to config file")
    parser.add_argument("--transport", default="stdio", choices=["stdio", "sse"], 
                        help="Transport type (stdio for Claude Desktop, sse for web integration)")
    parser.add_argument("--host", default="127.0.0.1", help="Host for HTTP/SSE transport")
    parser.add_argument("--port", type=int, default=8000, help="Port for HTTP/SSE transport")
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()]
    )
    logger = logging.getLogger("infinite_memory_mcp")
    
    try:
        # Get configuration file path
        config_file = args.config
        
        # Check if config file exists
        if config_file and not os.path.exists(config_file):
            logger.warning(f"Config file not found: {config_file}, using default configuration")
            config_file = None
            
        # Set up and start the MCP server
        logger.info("Starting InfiniteMemoryMCP with native MCP implementation")
        server = InfiniteMemoryMCP(config_file)
        server.run(transport=args.transport, host=args.host, port=args.port)
        
    except Exception as e:
        logger.error(f"Error starting InfiniteMemoryMCP: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 