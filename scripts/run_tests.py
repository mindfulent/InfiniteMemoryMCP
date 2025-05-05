#!/usr/bin/env python3
"""
Improved test runner for InfiniteMemoryMCP.

This script adds the project root to the Python path before running tests.
"""

import os
import subprocess
import sys

# Add the project root to the Python path
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.append(project_root)

def main():
    """Run the test suite."""
    # Construct the pytest command
    pytest_cmd = [
        'pytest',
        '-v',
        os.path.join(project_root, 'tests')
    ]
    
    print("Running tests...")
    print(f"Command: {' '.join(pytest_cmd)}")
    print(f"Python path includes: {project_root}")
    
    # Run pytest with environment variable to set Python path
    env = os.environ.copy()
    env['PYTHONPATH'] = project_root + os.pathsep + env.get('PYTHONPATH', '')
    
    # Run pytest
    result = subprocess.run(pytest_cmd, cwd=project_root, env=env)
    
    # Return the exit code from pytest
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())