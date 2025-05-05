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

3. Configure the system
   ```
   cp config/config.example.json config/config.json
   # Edit config.json with your preferred settings
   ```

4. Run the service
   ```
   python -m src.infinite_memory_mcp.main
   ```

## Usage
InfiniteMemoryMCP integrates with Claude Desktop using the Model Context Protocol (MCP). When running, it will listen for MCP commands on stdin and respond on stdout.

## Development
See the [Project Plan](docs/project-plan.md) for implementation details and progress.

## License
[MIT License](LICENSE) 