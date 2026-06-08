#!/usr/bin/env python3
"""
Repomix MCP Server for Cline

Provides codebase packing and search capabilities via the Model Context Protocol.
"""

import argparse
import json
import os
import sys
import subprocess
from pathlib import Path
from typing import Any

# Add the api directory to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "api"))

from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("repomix")

# Default config path
DEFAULT_REPOMIX_CONFIG = PROJECT_ROOT / "repomix.config.json"

def get_default_config():
    """Load default Repomix configuration."""
    try:
        with open(DEFAULT_REPOMIX_CONFIG, 'r') as f:
            return json.load(f)
    except Exception as e:
        return {
            "includePatterns": ["**/*.py", "**/*.yaml", "**/*.yml", "docker-compose*.yml"],
            "ignorePatterns": ["**/__pycache__/**", ".git/**"],
            "compress": True
        }

@mcp.tool()
def pack_codebase(
    directory: str | None = None,
    compress: bool = True,
    output_format: str | None = None,
    include_patterns: list[str] | None = None,
    ignore_patterns: list[str] | None = None,
    max_file_size: int = 1000000,
    max_context_window: int = 45000
) -> str:
    """
    Pack a codebase into a condensed format for context-aware analysis.
    
    Args:
        directory: Directory to pack (default: current working directory)
        compress: Whether to compress the output
        output_format: Output format ('text', 'xml', 'md') - auto-detects if not specified
        include_patterns: File patterns to include (default from config)
        ignore_patterns: File patterns to ignore (default from config)
        max_file_size: Maximum file size in bytes to include (default: 1MB)
        max_context_window: Max tokens for context window estimation (default: 45000)
    
    Returns:
        The packed codebase content
    """
    # Use default directory if not specified
    if directory is None:
        directory = str(PROJECT_ROOT)
    
    dir_path = Path(directory)
    if not dir_path.exists():
        return f"Error: Directory does not exist: {directory}"
    
    # Get config defaults
    config = get_default_config()
    
    # Merge config with provided arguments
    include = include_patterns or config.get("includePatterns", ["**/*.py", "**/*.yaml", "**/*.yml"])
    ignore = ignore_patterns or config.get("ignorePatterns", ["**/__pycache__/**", ".git/**"])
    
    try:
        # Build repomix command
        cmd = [
            "repomix",
            directory,
            "--includePatterns=" + ",".join(include),
            f"--ignorePatterns={','.join(ignore)}",
            f"--maxFileSize={max_file_size}",
            "--outputFormat=text" if not compress else "--outputFormat=md",
        ]
        
        # Execute repomix
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=dir_path.parent
        )
        
        if result.returncode != 0:
            return f"Error running repomix: {result.stderr}"
        
        # Try to read the output file
        output_file = dir_path / ".repomix" / "repomix-output.md" if compress else dir_path / ".repomix" / "repomix-output.txt"
        
        if output_file.exists():
            with open(output_file, 'r') as f:
                content = f.read()
            return content[:max_context_window * 4]  # Rough character limit
        else:
            # Return summary from stdout
            return result.stdout[:max_context_window * 4]
            
    except subprocess.TimeoutExpired:
        return "Error: Repomix timed out after 60 seconds"
    except Exception as e:
        return f"Error packing codebase: {str(e)}"

@mcp.tool()
def grep_repomix_output(
    search_pattern: str,
    output_file: str | None = None,
    max_results: int = 20,
    context_lines: int = 3
) -> str:
    """
    Search the repomix output for a specific pattern.
    
    Args:
        search_pattern: Pattern to search for (regex or plain text)
        output_file: Path to repomix output file (default: auto-detect)
        max_results: Maximum results to return (default: 20)
        context_lines: Number of context lines before/after each match (default: 3)
    
    Returns:
        Search results with context
    """
    # Auto-detect output file
    if output_file is None:
        output_file = str(PROJECT_ROOT / "repomix-output.md")
    
    file_path = Path(output_file)
    if not file_path.exists():
        return f"Error: Output file does not exist: {output_file}"
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            lines = content.split('\n')
        
        results = []
        import re
        
        # Try regex first, fall back to plain text
        try:
            pattern = re.compile(search_pattern, re.IGNORECASE)
        except re.error:
            pattern = re.compile(re.escape(search_pattern), re.IGNORECASE)
        
        for i, line in enumerate(lines):
            if pattern.search(line):
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                context = '\n'.join(lines[start:end])
                results.append({
                    "line": i + 1,
                    "match": line.strip(),
                    "context": context
                })
                
                if len(results) >= max_results:
                    break
        
        if not results:
            return f"No matches found for pattern: {search_pattern}"
        
        # Format results
        output_lines = [f"Found {len(results)} match(es) for pattern: {search_pattern}\n"]
        output_lines.append("=" * 80 + "\n")
        
        for r in results:
            output_lines.append(f"Line {r['line']}: {r['match']}\n")
            output_lines.append(f"Context:\n{r['context']}\n")
            output_lines.append("-" * 40 + "\n")
        
        return '\n'.join(output_lines)
        
    except Exception as e:
        return f"Error searching output: {str(e)}"

@mcp.tool()
def read_repomix_file(
    file_path: str,
    start_line: int | None = None,
    end_line: int | None = None,
    max_lines: int = 1000
) -> str:
    """
    Read a specific file from the repomix output.
    
    Args:
        file_path: Path to the file to read from repomix output
        start_line: Starting line number (1-based, default: 1)
        end_line: Ending line number (default: start_line + 1000)
        max_lines: Maximum lines to return (default: 1000)
    
    Returns:
        The file content from repomix output
    """
    # Auto-detect output file
    output_file = PROJECT_ROOT / "repomix-output.md"
    
    if not output_file.exists():
        return f"Error: Repomix output file does not exist. Run pack_codebase first."
    
    try:
        with open(output_file, 'r') as f:
            content = f.read()
        
        # Find the file section in repomix output
        import re
        pattern = rf'## File: {re.escape(file_path)}\s*\n(.*?)(?=\n## File:|\Z)'
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            return f"File not found in repomix output: {file_path}"
        
        file_content = match.group(1)
        lines = file_content.split('\n')
        
        # Apply line range
        if start_line is None:
            start_line = 1
        if end_line is None:
            end_line = start_line + max_lines
        
        start_idx = max(0, start_line - 1)
        end_idx = min(len(lines), end_line)
        
        selected_lines = lines[start_idx:end_idx]
        
        return f"Content of {file_path} (lines {start_line}-{end_idx}):\n\n" + '\n'.join(selected_lines)
        
    except Exception as e:
        return f"Error reading file from repomix output: {str(e)}"

@mcp.tool()
def get_repomix_stats() -> str:
    """
    Get statistics about the repomix output.
    
    Returns:
        Statistics including file count, total size, etc.
    """
    output_file = PROJECT_ROOT / "repomix-output.md"
    
    if not output_file.exists():
        return "Repomix output file does not exist. Run pack_codebase first."
    
    try:
        with open(output_file, 'r') as f:
            content = f.read()
        
        # Parse stats
        file_count = content.count("## File: ")
        char_count = len(content)
        line_count = content.count('\n') + 1
        
        return f"""Repomix Output Statistics:
- Total files: {file_count}
- Total characters: {char_count:,}
- Total lines: {line_count:,}
- Estimated size: {char_count / 1024 / 1024:.2f} MB
- Estimated tokens: ~{char_count // 4:,} (rough estimate)"""
        
    except Exception as e:
        return f"Error getting stats: {str(e)}"

@mcp.resource("repomix://config")
def get_config_resource() -> str:
    """Get the repomix configuration as a resource."""
    config = get_default_config()
    return json.dumps(config, indent=2)

def main():
    """Main entry point for the MCP server."""
    parser = argparse.ArgumentParser(description="Repomix MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio", help="Transport type")
    parser.add_argument("--host", default="127.0.0.1", help="Host for SSE transport")
    parser.add_argument("--port", type=int, default=8765, help="Port for SSE transport")
    args = parser.parse_args()
    
    if args.transport == "sse":
        mcp.run(host=args.host, port=args.port)
    else:
        mcp.run()

if __name__ == "__main__":
    main()