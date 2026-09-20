from pathlib import Path
import pytest
from queries.install_all import extract_query_names

QUERIES_DIR = Path(__file__).resolve().parent.parent / "queries"

EXPECTED_QUERIES = [
    "get_txn_neighborhood",
    "get_shared_identifiers",
    "get_money_flow",
    "get_policy_rules",
    "create_or_get_case",
    "update_case_status",
    "close_case",
    "get_open_cases",
    "graph_stats",
]

def test_query_files_exist():
    """Verify all expected query files exist in queries directory."""
    expected_files = [
        "get_txn_neighborhood.gsql",
        "get_shared_identifiers.gsql",
        "get_money_flow.gsql",
        "get_policy_rules.gsql",
        "case_crud.gsql",
        "graph_stats.gsql",
    ]
    for f in expected_files:
        p = QUERIES_DIR / f
        assert p.is_file(), f"Missing query file: {f}"

def test_all_query_names_extracted():
    """Verify install_all extracts all 8 required query names."""
    found_names = set()
    for gsql_file in QUERIES_DIR.glob("*.gsql"):
        content = gsql_file.read_text(encoding="utf-8")
        names = extract_query_names(content)
        found_names.update(names)

    for q in EXPECTED_QUERIES:
        assert q in found_names, f"Expected query '{q}' not found in .gsql definitions"

def test_query_headers_and_graph_binding():
    """Verify each query contains the required timeout header and target graph."""
    for gsql_file in QUERIES_DIR.glob("*.gsql"):
        content = gsql_file.read_text(encoding="utf-8")
        assert "FOR GRAPH FraudGraph" in content, f"Missing 'FOR GRAPH FraudGraph' in {gsql_file.name}"
        assert "@timeout" in content, f"Missing timeout header in {gsql_file.name}"
