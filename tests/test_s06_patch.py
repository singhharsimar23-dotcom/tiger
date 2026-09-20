import re
from pathlib import Path
import pytest

CONTRACT_PATH = Path("tools/MCP_TOOL_CONTRACT.md")
TG_TOOLS_PATH = Path("tools/tg_tools.py")


def test_mcp_tool_contract_exists_and_non_empty():
    """Assert tools/MCP_TOOL_CONTRACT.md exists and is non-empty."""
    assert CONTRACT_PATH.exists(), "tools/MCP_TOOL_CONTRACT.md does not exist"
    assert CONTRACT_PATH.stat().st_size > 0, "tools/MCP_TOOL_CONTRACT.md is empty"


def test_every_mcp_function_called_in_tg_tools_appears_in_contract():
    """
    Assert every function/tool name called inside tg_tools.py appears as a
    literal string in tools/MCP_TOOL_CONTRACT.md (grep-based check).
    """
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")
    tg_tools_text = TG_TOOLS_PATH.read_text(encoding="utf-8")

    # Extract all literal tigergraph__* tool name references in tg_tools.py
    mcp_tools_in_code = set(re.findall(r"tigergraph__[a-zA-Z0-9_]+", tg_tools_text))
    
    assert len(mcp_tools_in_code) >= 3, (
        f"Expected at least 3 MCP tool references in tg_tools.py, found {len(mcp_tools_in_code)}: {mcp_tools_in_code}"
    )

    for tool_name in mcp_tools_in_code:
        assert tool_name in contract_text, (
            f"Tool '{tool_name}' called inside tg_tools.py not found as a literal string in tools/MCP_TOOL_CONTRACT.md"
        )


def test_mandatory_tool_names_in_contract():
    """Assert verbatim presence of query-execution and vector-search tool names."""
    contract_text = CONTRACT_PATH.read_text(encoding="utf-8")
    mandatory = [
        "tigergraph__run_installed_query",
        "tigergraph__search_top_k_similarity",
        "tigergraph__upsert_vectors",
    ]
    for tool_name in mandatory:
        assert tool_name in contract_text, (
            f"Mandatory tool '{tool_name}' not found in tools/MCP_TOOL_CONTRACT.md"
        )
