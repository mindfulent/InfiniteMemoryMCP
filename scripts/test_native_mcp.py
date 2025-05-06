#!/usr/bin/env python3
"""
Test script for InfiniteMemoryMCP native MCP server.

This script tests the native MCP implementation by connecting to it using the MCP
client protocol and executing some basic operations.
"""

import asyncio
import json
import os
import sys
from datetime import datetime

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_native_mcp():
    """Run tests against the native MCP server."""
    print("Testing InfiniteMemoryMCP native MCP server...")
    
    # Set up server parameters with the full path to Python
    server_params = StdioServerParameters(
        command="/Library/Frameworks/Python.framework/Versions/3.11/bin/python3",  # Full path to Python executable
        args=["-m", "src.infinite_memory_mcp.main_native", "--config", "config/native_mcp_config.json"],  # Module and args
        env={"PYTHONPATH": os.getcwd()},  # Environment variables
    )
    
    # Connect to the server
    async with stdio_client(server_params) as (read, write):
        print("Connected to the MCP server")
        
        # Create client session
        async with ClientSession(read, write) as session:
            # Initialize the connection
            print("Initializing connection...")
            result = await session.initialize()
            protocol_version = result.protocolVersion
            server_info = result.serverInfo
            print(f"Connected to server: {server_info.name} v{server_info.version}")
            print(f"Using protocol version: {protocol_version}")
            
            # List available tools
            print("\nListing available tools...")
            tools_result = await session.list_tools()
            
            # Print tools details for debugging
            print(f"Tools structure: {type(tools_result)}")
            print(f"Tools attributes: {dir(tools_result)}")
            
            # Try to access tools in different ways
            tools = []
            if hasattr(tools_result, 'tools'):
                tools = tools_result.tools
            elif hasattr(tools_result, 'get_tools'):
                tools = tools_result.get_tools()
            
            # Display the tools
            if tools:
                print(f"Found {len(tools)} tools")
                tool_names = []
                for tool in tools:
                    if hasattr(tool, 'name'):
                        tool_names.append(tool.name)
                    elif hasattr(tool, 'getName'):
                        tool_names.append(tool.getName())
                    else:
                        tool_names.append(str(tool))
                print(f"Available tools: {', '.join(tool_names)}")
            else:
                print("No tools available or could not access tool list.")
            
            # List available resources
            print("\nListing available resources...")
            try:
                resources = await session.list_resources()
                resource_uris = [resource.uri for resource in resources]
                print(f"Available resources: {', '.join(resource_uris)}")
            except Exception as e:
                print(f"Error listing resources: {e}")
            
            # Test store_memory tool
            print("\nTesting store_memory tool...")
            memory_content = f"Test memory created at {datetime.now()}"
            try:
                result = await session.call_tool("store_memory", {
                    "text": memory_content,
                    "scope": "test",
                    "tags": ["test", "mcp"],
                    "metadata": {"source": "test_script"}
                })
                print(f"store_memory result: {result.content[0].text}")
            except Exception as e:
                print(f"Error storing memory: {e}")
            
            # Test retrieve_memory tool
            print("\nTesting retrieve_memory tool...")
            try:
                result = await session.call_tool("retrieve_memory", {
                    "query": "test memory",
                    "scope": "test",
                    "limit": 5
                })
                print(f"retrieve_memory result: {result.content[0].text}")
            except Exception as e:
                print(f"Error retrieving memory: {e}")
            
            # Test search_by_tag tool
            print("\nTesting search_by_tag tool...")
            try:
                result = await session.call_tool("search_by_tag", {
                    "tags": ["test"],
                    "scope": "test",
                    "limit": 10
                })
                print(f"search_by_tag result: {result.content[0].text}")
            except Exception as e:
                print(f"Error searching by tag: {e}")
            
            # Test get_memory_stats tool
            print("\nTesting get_memory_stats tool...")
            try:
                result = await session.call_tool("get_memory_stats", {})
                print(f"get_memory_stats result: {result.content[0].text}")
            except Exception as e:
                print(f"Error getting memory stats: {e}")
            
            # Test memory scope resource
            print("\nTesting memory:scope/test resource...")
            try:
                content, mime_type = await session.read_resource("memory:scope/test")
                print(f"Resource content ({mime_type}):")
                print(content)
            except Exception as e:
                print(f"Error reading resource: {e}")
    
    print("\nAll tests completed!")

if __name__ == "__main__":
    asyncio.run(test_native_mcp()) 