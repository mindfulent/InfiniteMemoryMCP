#!/usr/bin/env python3
"""
Simple MCP client for testing InfiniteMemoryMCP.

This script simulates a Claude Desktop client sending MCP commands to
InfiniteMemoryMCP.
"""

import json
import os
import subprocess
import sys
import time
from typing import Dict, Any, List, Optional

MCP_COMMANDS = [
    "ping",
    "get_memory_stats",
    # More commands will be added as they are implemented
]


def send_command(process, command: str, payload: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Send an MCP command to the InfiniteMemoryMCP process.
    
    Args:
        process: The subprocess.Popen process running InfiniteMemoryMCP
        command: The MCP command to send
        payload: Additional payload data to include with the command
    
    Returns:
        The response from InfiniteMemoryMCP as a dictionary
    """
    if payload is None:
        payload = {}
    
    # Create the request object
    request = {
        "action": command,
        **payload
    }
    
    # Convert to JSON and send
    request_json = json.dumps(request) + "\n"
    process.stdin.write(request_json)
    process.stdin.flush()
    
    # Read the response
    response_json = process.stdout.readline().strip()
    
    # Parse and return
    try:
        return json.loads(response_json)
    except json.JSONDecodeError:
        print(f"Error parsing response: {response_json}")
        return {"status": "error", "error": "Invalid JSON in response"}


def run_interactive_mcp_client():
    """Run an interactive MCP client session."""
    # Start the InfiniteMemoryMCP process
    print("Starting InfiniteMemoryMCP...")
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    process = subprocess.Popen(
        [sys.executable, "-m", "src.infinite_memory_mcp.main"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        cwd=project_root
    )
    
    # Wait for the process to start
    time.sleep(2)
    
    try:
        print("InfiniteMemoryMCP client ready. Type 'help' for available commands or 'quit' to exit.")
        
        while True:
            # Get command from user
            user_input = input("> ").strip()
            
            # Handle special commands
            if user_input.lower() == "quit" or user_input.lower() == "exit":
                break
            
            if user_input.lower() == "help":
                print("Available commands:")
                for cmd in MCP_COMMANDS:
                    print(f"  {cmd}")
                continue
            
            # Parse the command and payload
            parts = user_input.split(maxsplit=1)
            command = parts[0]
            
            if command not in MCP_COMMANDS:
                print(f"Unknown command: {command}")
                continue
            
            payload = {}
            if len(parts) > 1:
                try:
                    # Try to parse as JSON
                    payload = json.loads(parts[1])
                except json.JSONDecodeError:
                    # If not valid JSON, use as a simple message
                    payload = {"message": parts[1]}
            
            # Send the command
            print(f"Sending: {json.dumps({'action': command, **payload})}")
            response = send_command(process, command, payload)
            
            # Display the response
            print(f"Response: {json.dumps(response, indent=2)}")
    
    finally:
        # Clean up
        print("Stopping InfiniteMemoryMCP...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    run_interactive_mcp_client() 