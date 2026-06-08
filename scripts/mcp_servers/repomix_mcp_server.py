#!/usr/bin/env python3
"""
Repomix MCP Server

Provides tools for:
- Packing codebases into compressed XML/Markdown format
- Searching packed repomix output
- Managing workspace configurations

Run with: python3 scripts/mcp_servers/repomix_mcp_server.py
"""

import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Optional

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("ERROR: Missing MCP SDK. Install with: pip install mcp", file=sys.stderr)
    sys.exit(1)

# Constants
WORKSPACE_CONFIG_PATH = Path.home() / ".repomix" / "workspaces.json"
DEFAULT_OUTPUT_DIR = Path.home() / ".repomix" / "output"
DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Default workspace configuration
DEFAULT_WORKSPACES = {
    "news_intelligence": {
        "path": str(Path.home() / "Documents/projects/News Intelligence"),
        "name": "News Intelligence",
        "config": "repomix.config.json"
    }
}


def load_workspaces() -> dict:
    """Load workspace configurations."""
    if WORKSPACE_CONFIG_PATH.exists():
        try:
            with open(WORKSPACE_CONFIG_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return DEFAULT_WORKSPACES


def get_workspace_path(workspace_key: str) -> Optional[Path]:
    """Get the path for a workspace by key."""
    workspaces = load_workspaces()
    workspace = workspaces.get(workspace_key)
    if workspace:
        return Path(workspace.get("path", workspace_key))
    return None


def run_repomix_pack(directory: str, compress: bool = True, 
                     output_format: str = "xml") -> dict:
    """
    Pack a codebase using repomix.
    
    Args:
        directory: Path to the directory to pack
        compress: Whether to compress output (gzipped)
        output_format: Output format - 'xml' or 'markdown'
    
    Returns:
        dict with result status, output path, and statistics
    """
    dir_path = Path(directory)
    
    if not dir_path.exists():
        return {
            "success": False,
            "error": f"Directory not found: {directory}"
        }
    
    # Check for repomix config
    repomix_config = dir_path / "repomix.config.json"
    config_flag = f"--config={repomix_config}" if repomix_config.exists() else ""
    
    # Determine output path
    timestamp = subprocess.run(
        ["date", "+%Y%m%d_%H%M%S"],
        capture_output=True, text=True
    ).stdout.strip()
    
    workspace_name = dir_path.name.replace(" ", "_").lower()
    ext = ".xml.gz" if compress and output_format == "xml" else ".xml"
    ext = ".md.gz" if compress and output_format == "markdown" else ".md"
    ext = ext.replace(".", f".{timestamp}.")
    
    output_file = DEFAULT_OUTPUT_DIR / f"repomix_{workspace_name}{ext}"
    
    # Build command
    cmd = [
        "repomix",
        str(dir_path),
        f"--output={output_file}",
        f"--style={output_format}",
        config_flag
    ]
    
    if compress:
        cmd.append("--compress")
    
    # Execute repomix
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Repomix failed: {result.stderr}"
            }
        
        # Parse output for statistics
        output_text = result.stdout + result.stderr
        file_count = 0
        total_size = 0
        
        # Try to extract stats from output
        file_match = re.search(r"(\d+)\s+files?", output_text)
        if file_match:
            file_count = int(file_match.group(1))
        
        # Get actual file size
        if output_file.exists():
            total_size = output_file.stat().st_size
        
        return {
            "success": True,
            "output_path": str(output_file),
            "directory": str(dir_path),
            "format": output_format,
            "compressed": compress,
            "file_count": file_count,
            "output_size_bytes": total_size
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Repomix timed out after 5 minutes"
        }
    except FileNotFoundError:
        return {
            "success": False,
            "error": "Repomix not found. Please install with: npm install -g repomix"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def grep_repomix_output(query: str, workspace_key: str = "news_intelligence",
                        context_lines: int = 3, max_results: int = 50) -> dict:
    """
    Search a repomix packed output file.
    
    Args:
        query: Search query (supports basic regex)
        workspace_key: Workspace identifier
        context_lines: Number of context lines to show
        max_results: Maximum results to return
    
    Returns:
        dict with matches and metadata
    """
    workspace_path = get_workspace_path(workspace_key)
    if not workspace_path:
        return {
            "success": False,
            "error": f"Workspace not found: {workspace_key}"
        }
    
    # Find the latest repomix output for this workspace
    workspace_name = workspace_path.name.replace(" ", "_").lower()
    output_files = sorted(
        DEFAULT_OUTPUT_DIR.glob(f"repomix_{workspace_name}*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    
    if not output_files:
        return {
            "success": False,
            "error": f"No repomix output found for workspace: {workspace_key}. Run pack_codebase first."
        }
    
    output_file = output_files[0]
    
    try:
        # Read the file (handle gzip)
        if str(output_file).endswith('.gz'):
            import gzip
            with gzip.open(output_file, 'rt', encoding='utf-8') as f:
                content = f.read()
        else:
            with open(output_file, 'r', encoding='utf-8') as f:
                content = f.read()
        
        # Search for matches
        try:
            pattern = re.compile(query, re.IGNORECASE)
        except re.error:
            pattern = re.compile(re.escape(query), re.IGNORECASE)
        
        lines = content.split('\n')
        matches = []
        
        for i, line in enumerate(lines):
            if pattern.search(line):
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                
                context = '\n'.join(lines[start:end])
                
                matches.append({
                    "line_number": i + 1,
                    "matching_line": line[:200] + "..." if len(line) > 200 else line,
                    "context": context,
                    "file_hint": extract_file_hint(lines, i, context_lines)
                })
                
                if len(matches) >= max_results:
                    break
        
        # Count total potential matches
        total_matches = len(list(pattern.finditer(content)))
        
        return {
            "success": True,
            "query": query,
            "workspace": workspace_key,
            "output_file": str(output_file),
            "matches": matches,
            "match_count": len(matches),
            "total_occurrences": total_matches
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Search failed: {str(e)}"
        }


def extract_file_hint(lines: list, match_idx: int, context: int) -> Optional[str]:
    """Try to extract which file a match came from."""
    # Look for file markers in context
    search_start = max(0, match_idx - 20)
    search_end = min(len(lines), match_idx + 1)
    
    for i in range(search_start, search_end):
        line = lines[i]
        # XML format: <file path="...">
        file_match = re.search(r'<file\s+path="([^"]+)"', line)
        if file_match:
            return file_match.group(1)
        # Markdown format: ## File: path
        md_match = re.search(r'##\s*File:\s*(.+)', line)
        if md_match:
            return md_match.group(1)
    
    return None


def list_workspace_files(workspace_key: str = "news_intelligence",
                        file_pattern: str = "*", max_files: int = 200) -> dict:
    """
    List files in a workspace that would be included in repomix pack.
    
    Args:
        workspace_key: Workspace identifier
        file_pattern: Glob pattern to filter files
        max_files: Maximum files to return
    
    Returns:
        dict with file list and metadata
    """
    workspace_path = get_workspace_path(workspace_key)
    if not workspace_path:
        return {
            "success": False,
            "error": f"Workspace not found: {workspace_key}"
        }
    
    try:
        # Get include patterns from repomix config if exists
        config_path = workspace_path / "repomix.config.json"
        include_patterns = ["**/*"]
        
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
                if "include" in config:
                    include_patterns = config["include"]
        
        # Collect files
        files = []
        for pattern in include_patterns:
            for file_path in workspace_path.glob(pattern):
                if file_path.is_file():
                    rel_path = str(file_path.relative_to(workspace_path))
                    files.append({
                        "path": rel_path,
                        "size": file_path.stat().st_size,
                        "modified": file_path.stat().st_mtime
                    })
        
        # Sort by path and limit
        files.sort(key=lambda f: f["path"])
        files = files[:max_files]
        
        return {
            "success": True,
            "workspace": workspace_key,
            "workspace_path": str(workspace_path),
            "files": files,
            "file_count": len(files)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def get_workspace_info(workspace_key: Optional[str] = None) -> dict:
    """
    Get information about configured workspaces.
    
    Args:
        workspace_key: Optional specific workspace to get info for
    
    Returns:
        dict with workspace information
    """
    workspaces = load_workspaces()
    
    if workspace_key:
        if workspace_key in workspaces:
            ws = workspaces[workspace_key]
            path = Path(ws.get("path", workspace_key))
            return {
                "success": True,
                "workspace": {
                    "key": workspace_key,
                    "name": ws.get("name", workspace_key),
                    "path": ws.get("path", workspace_key),
                    "exists": path.exists(),
                    "has_repomix_config": (path / "repomix.config.json").exists() if path.exists() else False
                }
            }
        return {
            "success": False,
            "error": f"Workspace not found: {workspace_key}"
        }
    
    # Return all workspaces
    workspace_list = []
    for key, ws in workspaces.items():
        path = Path(ws.get("path", key))
        workspace_list.append({
            "key": key,
            "name": ws.get("name", key),
            "path": ws.get("path", key),
            "exists": path.exists()
        })
    
    return {
        "success": True,
        "workspaces": workspace_list,
        "workspace_count": len(workspace_list)
    }


# MCP Server Setup
server = Server("repomix-mcp")

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available repomix tools."""
    return [
        Tool(
            name="pack_codebase",
            description="Pack a codebase into compressed XML/Markdown format using repomix. Creates a snapshot of the entire codebase that can be searched later.",
            inputSchema={
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Path to the directory to pack (e.g., '/home/user/project' or workspace key like 'news_intelligence')"
                    },
                    "compress": {
                        "type": "boolean",
                        "description": "Whether to compress output with gzip (default: true)",
                        "default": True
                    },
                    "format": {
                        "type": "string",
                        "enum": ["xml", "markdown"],
                        "description": "Output format - xml (structured) or markdown (human-readable)",
                        "default": "xml"
                    }
                },
                "required": ["directory"]
            }
        ),
        Tool(
            name="grep_repomix_output",
            description="Search through a packed repomix output file. Useful for finding code patterns, function definitions, imports, or any text across the entire packed codebase.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (supports basic regex patterns)"
                    },
                    "workspace": {
                        "type": "string",
                        "description": "Workspace key to search in (default: 'news_intelligence')",
                        "default": "news_intelligence"
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "Number of context lines before/after each match (default: 3)",
                        "default": 3
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 50)",
                        "default": 50
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="list_workspace_files",
            description="List files in a workspace that would be included in a repomix pack. Useful for understanding what files are in scope.",
            inputSchema={
                "type": "object",
                "properties": {
                    "workspace": {
                        "type": "string",
                        "description": "Workspace key (default: 'news_intelligence')",
                        "default": "news_intelligence"
                    },
                    "max_files": {
                        "type": "integer",
                        "description": "Maximum files to list (default: 200)",
                        "default": 200
                    }
                }
            }
        ),
        Tool(
            name="get_workspace_info",
            description="Get information about configured workspaces or a specific workspace.",
            inputSchema={
                "type": "object",
                "properties": {
                    "workspace": {
                        "type": "string",
                        "description": "Optional workspace key to get info for. If omitted, returns all workspaces."
                    }
                }
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "pack_codebase":
            directory = arguments.get("directory", "news_intelligence")
            compress = arguments.get("compress", True)
            output_format = arguments.get("format", "xml")
            
            # Resolve workspace key to path if needed
            if not os.path.isabs(directory):
                workspace_path = get_workspace_path(directory)
                if workspace_path:
                    directory = str(workspace_path)
            
            result = run_repomix_pack(directory, compress, output_format)
            
        elif name == "grep_repomix_output":
            query = arguments.get("query", "")
            workspace = arguments.get("workspace", "news_intelligence")
            context_lines = arguments.get("context_lines", 3)
            max_results = arguments.get("max_results", 50)
            
            result = grep_repomix_output(query, workspace, context_lines, max_results)
            
        elif name == "list_workspace_files":
            workspace = arguments.get("workspace", "news_intelligence")
            max_files = arguments.get("max_files", 200)
            
            result = list_workspace_files(workspace, "*", max_files)
            
        elif name == "get_workspace_info":
            workspace = arguments.get("workspace")
            
            result = get_workspace_info(workspace)
            
        else:
            result = {
                "success": False,
                "error": f"Unknown tool: {name}"
            }
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
        
    except Exception as e:
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": False,
                "error": f"Tool execution failed: {str(e)}"
            }, indent=2)
        )]


async def main():
    """Run the MCP server."""
    print("Repomix MCP Server starting...", file=sys.stderr)
    print(f"Default output directory: {DEFAULT_OUTPUT_DIR}", file=sys.stderr)
    
    # Verify repomix is installed
    try:
        subprocess.run(["which", "repomix"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("WARNING: repomix not found in PATH. Install with: npm install -g repomix", file=sys.stderr)
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())