# InfiniteMemoryMCP User Guide

## Introduction
InfiniteMemoryMCP is a MongoDB-powered persistent memory system for Claude Desktop. It enables Claude to maintain context and recall information across conversations through a local-first architecture, ensuring privacy while providing "infinite" memory capabilities.

This guide will help you install, configure, and use InfiniteMemoryMCP with Claude Desktop.

## Installation

### Prerequisites
- Python 3.8 or higher
- MongoDB 4.4+ (6.0+ recommended for vector search capabilities)
- Claude Desktop application

### Installation Steps

1. **Install MongoDB** (if not already installed)
   - [Download MongoDB Community Edition](https://www.mongodb.com/try/download/community)
   - Follow the installation instructions for your operating system
   - Ensure MongoDB service is running

2. **Install InfiniteMemoryMCP**
   ```bash
   git clone <repository-url>
   cd InfiniteMemoryMCP
   pip install -r requirements.txt
   ```

3. **Configure InfiniteMemoryMCP**
   ```bash
   cp config/config.example.json config/config.json
   ```
   
   Then edit `config.json` with your preferred settings (see Configuration section below)

## Configuration
The configuration file is located at `config/config.json` and contains the following settings:

### MongoDB Configuration
- `mongodb.mode`: Either "embedded" or "external"
- `mongodb.uri`: MongoDB connection URI (for external mode)
- `mongodb.database`: Name of the database to use
- `mongodb.embedded_path`: Path to store embedded MongoDB data files

### Memory Settings
- `memory.default_scope`: Default scope for storing memories
- `memory.max_memory_items`: Maximum number of memory items to store (soft limit)
- `memory.max_memory_size_mb`: Maximum size of the memory database in MB (soft limit)

### Embedding Model Settings
- `embedding.model_name`: Name of the embedding model to use
- `embedding.model_path`: Path to the embedding model
- `embedding.dimension`: Dimension of the embeddings
- `embedding.use_gpu`: Whether to use GPU for embedding (if available)

### Backup Settings
- `backup.schedule`: Backup schedule (daily, weekly, etc.)
- `backup.retention`: Number of backups to retain
- `backup.path`: Path to store backups
- `backup.encrypt`: Whether to encrypt backups

## Starting the Service
Start the InfiniteMemoryMCP service:

```bash
python -m src.infinite_memory_mcp.main
```

This will start the service and listen for MCP commands from Claude Desktop.

## Memory Commands
Claude can use the following memory-related commands:

### Storing Memories
Simply tell Claude to remember information:
- "Claude, remember that my favorite color is blue."
- "Please remember this meeting is scheduled for May 15th at 2pm."

### Retrieving Memories
Ask Claude about previously stored information:
- "What is my favorite color?"
- "When is our meeting scheduled?"
- "What do you know about my project timelines?"

### Using Memory Scopes
You can organize information in different contexts:
- "In the context of work, remember that my team meeting is on Thursdays."
- "For my fitness goals, remember that I want to run a 5K by December."
- "When thinking about work, when is my team meeting?"

### Using Memory Tags
Tag specific memories for easier retrieval:
- "Remember this as #project-alpha: The deadline is June 30th."
- "What do you remember about #project-alpha?"

### Time-Based Recall
Ask about conversations from specific times:
- "What did we discuss yesterday?"
- "What did I tell you last week about the project?"

### Forgetting Information
Request Claude to forget specific information:
- "Please forget what I told you about my travel plans."
- "Forget everything about the project we discussed."

## Troubleshooting

### Common Issues

#### Connection to MongoDB Failed
- Ensure MongoDB is running
- Check the connection URI in your config file
- Verify network settings if using a remote MongoDB instance

#### Claude Doesn't Remember Something
- Verify the information was explicitly asked to be remembered
- Check if you're asking within the same scope/context
- Try using more specific phrasing

#### Service Won't Start
- Check for error messages in the console
- Verify all dependencies are installed
- Ensure the configuration file is valid JSON

### Getting Support
If you encounter issues not covered in this guide, please:
1. Check the [GitHub Issues](https://github.com/yourusername/InfiniteMemoryMCP/issues)
2. Review the detailed technical documentation
3. Report new issues with detailed steps to reproduce

## Privacy and Security
InfiniteMemoryMCP is designed with privacy as a core principle:
- All data is stored locally on your machine
- No information is sent to external servers
- MongoDB is configured to only accept local connections
- Optional backup encryption for sensitive data

## Maintenance

### Backup and Restore
To manually backup your memory database:
```bash
python scripts/backup.py
```

To restore from a backup:
```bash
python scripts/restore.py --backup_file path/to/backup_file
```

### Database Optimization
After long-term use, you may want to optimize the database:
```bash
python scripts/optimize_db.py
```

This will:
- Compact the database
- Rebuild indexes
- Remove any corrupted data

## Advanced Usage

### Custom Embedding Models
Advanced users can configure custom embedding models:
1. Place your model in the specified model directory
2. Update the `embedding.model_name` and `embedding.model_path` in the config
3. Restart the service

### Development and Extension
For information on extending InfiniteMemoryMCP, please refer to the [Developer Guide](developer_guide.md). 