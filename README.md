# InfiniteMemoryMCP

## Overview
InfiniteMemoryMCP is a MongoDB-powered persistent memory system for Claude Desktop. It enables Claude to maintain context and recall information across conversations through a local-first architecture, ensuring privacy while providing "infinite" memory capabilities.

## Features
- Local-first architecture for complete privacy
- Persistent memory storage using MongoDB
- Semantic search capabilities for natural recall
- Memory scopes to organize information contextually
- Memory tagging for efficient organization
- Comprehensive memory management with pruning and backup
- Async embedding generation for improved performance
- Circuit breaker pattern for resilience
- Hybrid search combining semantic and keyword search

## Installation

### Prerequisites
- Python 3.8+
- MongoDB 4.4+ (6.0+ recommended for vector search capabilities)

### Setup
1. Clone the repository
   ```
   git clone <repository-url>
   cd InfiniteMemoryMCP
   ```

2. Install dependencies
   ```
   pip install -r requirements.txt
   ```

3. Install MongoDB (if not already installed)
   - macOS (using Homebrew):
     ```
     brew tap mongodb/brew
     brew install mongodb-community
     ```
   - Windows/Linux: Follow the [official MongoDB installation guide](https://docs.mongodb.com/manual/installation/)

4. Start MongoDB service
   - macOS:
     ```
     brew services start mongodb-community
     ```
   - Windows (run as Administrator):
     ```
     net start MongoDB
     ```
   - Linux:
     ```
     sudo systemctl start mongod
     ```

5. Configure the system
   ```
   cp config/config.example.json config/config.json
   # Edit config.json with your preferred settings
   ```
   
   The default configuration uses external MongoDB mode (recommended):
   ```json
   {
       "database": {
           "mode": "external",
           "uri": "mongodb://localhost:27017/claude_memory",
           "path": "~/ClaudeMemory/mongo_data",
           ...
       },
       ...
   }
   ```

6. Run the service
   ```
   python -m src.infinite_memory_mcp.main
   ```
   
   Or use the provided script:
   ```
   chmod +x run.sh  # Make it executable (first time only)
   ./run.sh
   ```

### Configuration Options

#### MongoDB Connection Modes

InfiniteMemoryMCP supports two MongoDB connection modes:

1. **External Mode (Recommended)**: Connect to a separately running MongoDB instance
   - Set `database.mode` to `"external"` in config.json
   - Ensure MongoDB is installed and running before starting InfiniteMemoryMCP
   - This is more stable and allows better control over your MongoDB instance

2. **Embedded Mode**: The application attempts to start and manage MongoDB itself
   - Set `database.mode` to `"embedded"` in config.json
   - Requires `mongod` executable to be in your system PATH
   - Useful for quick testing but less reliable for production use

## Usage
InfiniteMemoryMCP integrates with Claude Desktop using the Model Context Protocol (MCP). When running, it will listen for MCP commands on stdin and respond on stdout.

### Configuring Claude Desktop

To use InfiniteMemoryMCP with Claude Desktop, you need to configure the MCP server in Claude Desktop's configuration file. This file tells Claude Desktop which MCP servers to start when the application launches.

#### Configuration File Location

The Claude Desktop configuration file is located at:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

If the file doesn't exist, you can create it. Open the Claude menu on your computer, select "Settings...", click on "Developer" in the left-hand bar, and then click on "Edit Config".

#### Configuration Settings

Add the following configuration to your `claude_desktop_config.json` file:

```json
{
  "mcpServers": {
    "infinite-memory": {
      "command": "python",
      "args": [
        "-m",
        "src.infinite_memory_mcp.main"
      ],
      "cwd": "/absolute/path/to/your/InfiniteMemoryMCP"
    }
  }
}
```

Make sure to replace `/absolute/path/to/your/InfiniteMemoryMCP` with the actual absolute path to where you cloned the InfiniteMemoryMCP repository.

For Windows users, use the appropriate path format:

```json
{
  "mcpServers": {
    "infinite-memory": {
      "command": "python",
      "args": [
        "-m",
        "src.infinite_memory_mcp.main"
      ],
      "cwd": "C:\\absolute\\path\\to\\your\\InfiniteMemoryMCP"
    }
  }
}
```

#### Restart Claude Desktop

After updating the configuration file, restart Claude Desktop for the changes to take effect. You should see the MCP tools icon appear in the input box, which allows Claude to access the memory capabilities.

### Key Commands
Here are the main commands supported by the system:

- `store_memory`: Store a new memory in the system
- `retrieve_memory`: Retrieve memories using semantic search
- `search_by_tag`: Find memories with specific tags
- `search_by_scope`: Find memories in a specific scope
- `delete_memory`: Remove memories from the system
- `get_memory_stats`: Get stats about the memory system

Example MCP command:
```json
{
  "action": "store_memory",
  "content": "This is important information to remember",
  "scope": "ProjectX",
  "tags": ["important", "reference"]
}
```

## Testing
InfiniteMemoryMCP includes a comprehensive test suite:

1. Run all tests:
   ```
   python -m pytest
   ```

2. Run tests for a specific component:
   ```
   python -m pytest tests/test_memory_service.py
   ```

3. Run tests with verbosity:
   ```
   python -m pytest -v
   ```

## Troubleshooting

### Common Issues

1. **MongoDB Connection Error**:
   - Check if MongoDB is running: `brew services list` (macOS) or `systemctl status mongod` (Linux)
   - Ensure your config.json has the correct mode ("external" is recommended)
   - Verify MongoDB is installed and available in your PATH

2. **MCP Server Error**:
   - Check for error messages in the output
   - Verify path to your repository in the Claude Desktop configuration
   - Check your Python environment has all required dependencies

## Project Status
See the [Implementation Status](implementation_status.md) for current progress and future work.

## Documentation
- [Project Plan](docs/project-plan.md): Implementation details and roadmap
- [Product Requirements](docs/product-requirements.md): Functional requirements
- [Technical Requirements](docs/technical-requirements.md): Technical specifications

## Development
To contribute to InfiniteMemoryMCP:

1. Fork the repository
2. Create a feature branch
3. Implement your changes with tests
4. Submit a pull request

## License
[MIT License](LICENSE) 