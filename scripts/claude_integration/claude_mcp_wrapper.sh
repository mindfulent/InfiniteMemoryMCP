#!/bin/bash
# Wrapper script for launching InfiniteMemoryMCP from Claude Desktop

# Print diagnostic information
echo "Starting InfiniteMemoryMCP wrapper script from $(pwd)" >&2
echo "Arguments: $@" >&2

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
echo "Script directory: $SCRIPT_DIR" >&2

# Set up environment variables
export PYTHONPATH="$SCRIPT_DIR"
export LOG_LEVEL="INFO"
export MONGODB_URI="mongodb://localhost:27017/"

echo "Using PYTHONPATH: $PYTHONPATH" >&2

# Find the proper Python executable
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: No Python executable found in PATH" >&2
    exit 1
fi

echo "Using Python command: $PYTHON_CMD" >&2

# Run the MCP server
echo "Starting InfiniteMemoryMCP MCP server..." >&2
$PYTHON_CMD -m src.infinite_memory_mcp.main --config "$SCRIPT_DIR/config/mcp_config.json" "$@" 