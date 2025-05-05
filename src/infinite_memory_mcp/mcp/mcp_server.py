"""
MCP server implementation for InfiniteMemoryMCP.

This module implements a Model Context Protocol (MCP) server that
communicates with Claude Desktop via stdin/stdout, handling memory-related
commands.
"""

import json
import sys
import threading
from typing import Any, Callable, Dict, List, Optional, Union

from ..utils.logging import logger


class MCPServer:
    """
    Model Context Protocol server for InfiniteMemoryMCP.
    
    This class handles communication with Claude Desktop via stdin/stdout,
    parsing MCP commands and dispatching them to the appropriate handlers.
    """
    
    def __init__(self):
        """Initialize the MCP server."""
        self.command_handlers: Dict[str, Callable] = {}
        self.running: bool = False
        self.thread: Optional[threading.Thread] = None
    
    def register_command(self, action: str, handler: Callable) -> None:
        """
        Register a handler for an MCP command.
        
        Args:
            action: The command action name (e.g. 'store_memory')
            handler: A function that takes the command payload and returns a response
        """
        self.command_handlers[action] = handler
        logger.info(f"Registered handler for MCP command: {action}")
    
    def process_request(self, request_json: str) -> Optional[Dict[str, Any]]:
        """
        Process an MCP request.
        
        Args:
            request_json: The JSON string containing the MCP request
            
        Returns:
            A dict containing the response, or None if an error occurred
        """
        try:
            request = json.loads(request_json)
            
            # Extract action from request
            action = request.get("action")
            if not action:
                logger.error("Missing 'action' in MCP request")
                return {"status": "error", "error": "Missing 'action' in request"}
            
            # Check if we have a handler for this action
            handler = self.command_handlers.get(action)
            if not handler:
                logger.error(f"Unknown action: {action}")
                return {"status": "error", "error": f"Unknown action: {action}"}
            
            # Call the handler
            logger.info(f"Processing MCP command: {action}")
            response = handler(request)
            logger.debug(f"MCP response: {response}")
            
            return response
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in MCP request: {e}")
            return {"status": "error", "error": "Invalid JSON in request"}
        
        except Exception as e:
            logger.exception(f"Error processing MCP request: {e}")
            return {"status": "error", "error": str(e)}
    
    def start(self) -> None:
        """Start the MCP server in a separate thread."""
        if self.running:
            logger.warning("MCP server already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_server)
        self.thread.daemon = True
        self.thread.start()
        logger.info("MCP server started")
    
    def stop(self) -> None:
        """Stop the MCP server."""
        if not self.running:
            logger.warning("MCP server not running")
            return
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
            self.thread = None
        
        logger.info("MCP server stopped")
    
    def _run_server(self) -> None:
        """
        Run the MCP server loop, reading from stdin and writing to stdout.
        
        This method runs in a separate thread and continually reads JSON
        requests from stdin, processes them, and writes responses to stdout.
        """
        logger.info("MCP server loop started")
        
        while self.running:
            try:
                # Read a line from stdin
                request_json = sys.stdin.readline().strip()
                
                # Skip empty lines
                if not request_json:
                    continue
                
                # Process the request
                response = self.process_request(request_json)
                
                # Write the response to stdout
                if response:
                    sys.stdout.write(json.dumps(response) + "\n")
                    sys.stdout.flush()
            
            except KeyboardInterrupt:
                logger.info("MCP server interrupted")
                self.running = False
                break
            
            except Exception as e:
                logger.exception(f"Error in MCP server loop: {e}")
                # Try to send an error response
                try:
                    error_response = {"status": "error", "error": str(e)}
                    sys.stdout.write(json.dumps(error_response) + "\n")
                    sys.stdout.flush()
                except:
                    pass
        
        logger.info("MCP server loop ended")


# Create a singleton instance
mcp_server = MCPServer() 