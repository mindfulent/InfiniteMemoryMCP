#!/usr/bin/env python3
"""
Run the InfiniteMemoryMCP test suite.

This script runs the test suite for InfiniteMemoryMCP using pytest.
"""

import os
import subprocess
import sys


def main():
    """Run the test suite."""
    # Get the project root directory
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    # Construct the pytest command
    pytest_cmd = [
        sys.executable, '-m', 'pytest',
        '-v',
        os.path.join(project_root, 'tests')
    ]
    
    print("Running tests...")
    print(f"Command: {' '.join(pytest_cmd)}")
    
    # Run pytest
    result = subprocess.run(pytest_cmd, cwd=project_root)
    
    # Return the exit code from pytest
    return result.returncode


if __name__ == "__main__":
    sys.exit(main()) 