import os
import sys
import asyncio
from pathlib import Path
from dotenv import dotenv_values

_tools = None  # cached tool list
_session = None  # cached session
_client = None

def get_env() -> dict:
    """Load environment variables for TigerGraph MCP server."""
    env_path = Path(".env").expanduser().resolve()
    if not env_path.is_file():
        env_path = Path(".env.example").expanduser().resolve()
    
    vals = dotenv_values(dotenv_path=env_path)
    # Merge with os.environ
    merged = {**os.environ}
    for k, v in vals.items():
        if v is not None:
            merged[str(k)] = str(v)
    return merged

async def get_mcp_tools():
    """
    Return cached MCP tools. Hold session open for entire investigation run.
    Never call get_tools() inside a loop — it opens/closes sessions per call (4x slower).
    """
    global _tools, _session, _client
    if _tools is not None:
        return _tools

    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
        from langchain_mcp_adapters.tools import load_mcp_tools
    except ImportError:
        # Graceful fallback when package not yet installed in local python
        print("[WARNING] langchain_mcp_adapters not installed. Running in direct TigerGraph mode.", file=sys.stderr)
        _tools = []
        return _tools

    try:
        env_vars = get_env()
        if _client is None:
            _client = MultiServerMCPClient({
                "tigergraph-mcp-server": {
                    "transport": "stdio",
                    "command": "tigergraph-mcp",
                    "args": ["-v"],
                    "env": env_vars,
                }
            })

        if _session is None:
            # Enter async context and retain session across the entire lifetime
            _session = _client.session("tigergraph-mcp-server")
            session_ctx = await _session.__aenter__()
            _tools = await load_mcp_tools(session_ctx)
            print(f"[MCP] Loaded {len(_tools)} tools from TigerGraph MCP server.")
            
        return _tools
    except Exception as e:
        print(f"[ERROR] Could not start TigerGraph MCP server session: {e}", file=sys.stderr)
        _tools = []
        return _tools

async def close_mcp_session():
    """Gracefully close the cached MCP session at the end of the investigation run."""
    global _session, _tools
    if _session is not None:
        try:
            await _session.__aexit__(None, None, None)
        except Exception as e:
            print(f"[WARNING] Error closing MCP session: {e}", file=sys.stderr)
        _session = None
        _tools = None
