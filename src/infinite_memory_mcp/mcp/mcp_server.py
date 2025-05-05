"""
MCP server implementation for InfiniteMemoryMCP.

This module implements a Model Context Protocol (MCP) server that
communicates with Claude Desktop via stdin/stdout, handling memory-related
commands.
"""

import json
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Union

from ..utils.logging import logger


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for MCP commands.
    
    This class helps prevent cascade failures by "breaking the circuit" when
    a command is failing repeatedly, and then allowing it to try again after
    a cooling-off period.
    """
    
    def __init__(self, failure_threshold: int = 3, reset_timeout: int = 60):
        """
        Initialize the circuit breaker.
        
        Args:
            failure_threshold: Number of failures before circuit opens
            reset_timeout: Seconds to wait before trying again
        """
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count: Dict[str, int] = {}
        self.circuit_open: Dict[str, bool] = {}
        self.last_failure_time: Dict[str, float] = {}
        self.lock = threading.RLock()
    
    def is_open(self, command: str) -> bool:
        """
        Check if the circuit is open for a command.
        
        Args:
            command: The command to check
            
        Returns:
            True if the circuit is open (command should not be executed)
        """
        with self.lock:
            # If circuit was open, check if we can try again
            if self.circuit_open.get(command, False):
                last_failure = self.last_failure_time.get(command, 0)
                if time.time() - last_failure > self.reset_timeout:
                    # Reset the circuit to half-open state
                    self.circuit_open[command] = False
                    self.failure_count[command] = 0
                    logger.info(f"Circuit reset for command: {command}")
                    return False
                return True
            return False
    
    def record_success(self, command: str) -> None:
        """
        Record a successful command execution.
        
        Args:
            command: The command that succeeded
        """
        with self.lock:
            self.failure_count[command] = 0
            self.circuit_open[command] = False
    
    def record_failure(self, command: str) -> None:
        """
        Record a command failure.
        
        Args:
            command: The command that failed
        """
        with self.lock:
            # Increment failure count
            count = self.failure_count.get(command, 0) + 1
            self.failure_count[command] = count
            self.last_failure_time[command] = time.time()
            
            # Check if we need to open the circuit
            if count >= self.failure_threshold:
                if not self.circuit_open.get(command, False):
                    logger.warning(f"Circuit opened for command: {command} after {count} failures")
                    self.circuit_open[command] = True


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
        
        # Error handling
        self.circuit_breaker = CircuitBreaker()
        self.max_retry_attempts = 3
        self.retry_delay = 1.0  # seconds
        
        # Metrics
        self.request_count = 0
        self.error_count = 0
        self.slow_request_threshold = 1.0  # seconds
        self.slow_request_count = 0
        
        # Health check
        self.health_status = "ok"
        self.last_error: Optional[str] = None
    
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
        start_time = time.time()
        self.request_count += 1
        
        try:
            request = json.loads(request_json)
            
            # Extract action from request
            action = request.get("action")
            if not action:
                logger.error("Missing 'action' in MCP request")
                self.error_count += 1
                return {"status": "error", "error": "Missing 'action' in request"}
            
            # Check if circuit breaker is open for this command
            if self.circuit_breaker.is_open(action):
                logger.warning(f"Circuit breaker open for {action}, rejecting request")
                self.error_count += 1
                return {
                    "status": "error", 
                    "error": f"Service temporarily unavailable for action: {action}",
                    "retry_after": self.circuit_breaker.reset_timeout
                }
            
            # Check if we have a handler for this action
            handler = self.command_handlers.get(action)
            if not handler:
                logger.error(f"Unknown action: {action}")
                self.error_count += 1
                return {"status": "error", "error": f"Unknown action: {action}"}
            
            # Process the command with retry logic
            return self._execute_with_retry(handler, request, action)
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in MCP request: {e}")
            self.error_count += 1
            return {"status": "error", "error": "Invalid JSON in request"}
        
        except Exception as e:
            logger.exception(f"Error processing MCP request: {e}")
            self.error_count += 1
            self.health_status = "degraded"
            self.last_error = str(e)
            return {"status": "error", "error": str(e)}
        
        finally:
            # Record metrics for slow requests
            elapsed = time.time() - start_time
            if elapsed > self.slow_request_threshold:
                self.slow_request_count += 1
                logger.warning(f"Slow request detected, took {elapsed:.2f}s")
    
    def _execute_with_retry(self, handler: Callable, request: Dict[str, Any], action: str) -> Dict[str, Any]:
        """
        Execute a command handler with retry logic.
        
        Args:
            handler: The command handler to execute
            request: The request payload
            action: The action name (for circuit breaker)
            
        Returns:
            The handler's response
        """
        attempts = 0
        last_error = None
        
        while attempts < self.max_retry_attempts:
            try:
                logger.info(f"Processing MCP command: {action}")
                response = handler(request)
                logger.debug(f"MCP response: {response}")
                
                # Record success with circuit breaker
                self.circuit_breaker.record_success(action)
                
                # Reset health status if it was degraded
                if self.health_status == "degraded":
                    self.health_status = "ok"
                    self.last_error = None
                
                return response
            
            except Exception as e:
                attempts += 1
                last_error = str(e)
                logger.error(f"Error executing {action} (attempt {attempts}/{self.max_retry_attempts}): {e}")
                
                if attempts < self.max_retry_attempts:
                    # Wait before retrying
                    time.sleep(self.retry_delay)
                else:
                    # Record failure with circuit breaker
                    self.circuit_breaker.record_failure(action)
                    
                    # Update health status
                    self.health_status = "degraded"
                    self.last_error = last_error
        
        # All retries failed
        self.error_count += 1
        return {
            "status": "error",
            "error": f"Command failed after {attempts} attempts: {last_error}"
        }
    
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
    
    def get_health(self) -> Dict[str, Any]:
        """
        Get the health status of the MCP server.
        
        Returns:
            A dict containing health information
        """
        return {
            "status": self.health_status,
            "request_count": self.request_count,
            "error_count": self.error_count,
            "slow_request_count": self.slow_request_count,
            "last_error": self.last_error
        }
    
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
                
                # Update health status
                self.health_status = "degraded"
                self.last_error = str(e)
                self.error_count += 1
        
        logger.info("MCP server loop ended")


# Create a singleton instance
mcp_server = MCPServer() 