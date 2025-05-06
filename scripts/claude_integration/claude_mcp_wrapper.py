#!/usr/bin/env python3
"""
Wrapper script for launching InfiniteMemoryMCP MCP server from Claude Desktop.

This script ensures the proper Python path is set so Claude Desktop 
can find the required modules.
"""

import os
import sys
import traceback
import subprocess

# Print some diagnostic information to help with troubleshooting
print(f"Starting InfiniteMemoryMCP wrapper script from {os.getcwd()}", file=sys.stderr)
print(f"Python executable: {sys.executable}", file=sys.stderr)
print(f"Command line arguments: {sys.argv}", file=sys.stderr)

# Add the project root directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))  # scripts/claude_integration/
project_root = os.path.abspath(os.path.join(current_dir, "../.."))  # Go up two levels to project root
sys.path.insert(0, project_root)
print(f"Added to PYTHONPATH: {project_root}", file=sys.stderr)
print(f"Full PYTHONPATH: {sys.path}", file=sys.stderr)

# Import and run the main module
try:
    from src.infinite_memory_mcp.main import main
    print("Successfully imported main module, running main()", file=sys.stderr)
    main()
except ImportError as e:
    print(f"Failed to import main module: {e}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    print("Falling back to subprocess method.", file=sys.stderr)
    
    # If import fails, try running as a subprocess with PYTHONPATH set
    env = os.environ.copy()
    env["PYTHONPATH"] = project_root
    
    # Build command arguments from sys.argv, skipping the script name
    args = [sys.executable, "-m", "src.infinite_memory_mcp.main"]
    if len(sys.argv) > 1:
        args.extend(sys.argv[1:])
    
    # Print the command we're about to run for debugging
    print(f"Running: {' '.join(args)} with PYTHONPATH={project_root}", file=sys.stderr)
    
    # Execute the process
    try:
        subprocess.run(args, env=env, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Subprocess failed with exit code {e.returncode}", file=sys.stderr)
    except Exception as e:
        print(f"Error running subprocess: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr) 