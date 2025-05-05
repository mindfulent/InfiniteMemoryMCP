#!/usr/bin/env python
"""Setup script for InfiniteMemoryMCP."""

from setuptools import setup, find_packages

setup(
    name="infinite-memory-mcp",
    version="0.1.0",
    description="MongoDB-powered persistent memory system for Claude Desktop",
    author="",
    author_email="",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "pymongo>=4.4.0",
        "python-dotenv>=0.19.0",
        "pyyaml>=6.0",
        "sentence-transformers>=2.2.2",
        "numpy>=1.21.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black>=22.0.0",
            "isort>=5.10.1",
            "pylint>=2.12.0",
        ],
    },
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "infinite-memory-mcp=infinite_memory_mcp.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
) 