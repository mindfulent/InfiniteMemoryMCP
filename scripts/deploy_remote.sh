#!/bin/bash
# Deploy the InfiniteMemoryMCP MCP server with SSE transport for remote access

# Check if MongoDB is running
echo "Checking if MongoDB is running..."
mongo --eval "db.version()" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "MongoDB is not running. Starting MongoDB..."
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        brew services start mongodb-community
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        sudo systemctl start mongod
    else
        # Windows or other
        echo "Please start MongoDB manually before running this script."
        exit 1
    fi
fi

# Set up environment
export PYTHONPATH="$(pwd)"
export LOG_LEVEL="INFO"
export MONGODB_URI="mongodb://localhost:27017/"

# Default host and port
HOST=${1:-"0.0.0.0"}
PORT=${2:-"8000"}

echo "Starting InfiniteMemoryMCP MCP server in remote mode..."
echo "Server will be available at: http://$HOST:$PORT/sse"
echo "Press Ctrl+C to stop the server"

# Run the MCP server with SSE transport
echo "Starting InfiniteMemoryMCP MCP server with SSE transport on ${HOST}:${PORT}..."
python3 -m src.infinite_memory_mcp.main --config config/mcp_config.json --transport sse --host ${HOST} --port ${PORT} 