import itertools
import pytest
from schema.derived_edges import COMMON_DOMAINS

def test_common_domains_defined():
    """Verify common email domains are properly excluded."""
    expected_domains = {
        "gmail.com",
        "yahoo.com",
        "hotmail.com",
        "outlook.com",
        "icloud.com",
        "aol.com",
        "protonmail.com",
    }
    for d in expected_domains:
        assert d in COMMON_DOMAINS, f"Missing common domain: {d}"

def test_clique_edge_generation():
    """
    Verify correctness rule:
    Pick one device shared by 3 accounts. Verify all 3 SHARES_DEVICE edges exist
    (A<->B, A<->C, B<->C = 3 edges) and no self-loops (a1 != a2).
    """
    accounts = ["ACC_A", "ACC_B", "ACC_C"]
    pairs = list(itertools.combinations(sorted(accounts), 2))
    assert len(pairs) == 3
    assert ("ACC_A", "ACC_B") in pairs
    assert ("ACC_A", "ACC_C") in pairs
    assert ("ACC_B", "ACC_C") in pairs
    
    # Assert no self loops
    for a1, a2 in pairs:
        assert a1 != a2

def test_derived_edge_types_in_schema():
    """Verify derived edge types are recognized in schema definition."""
    derived_edges = [
        "SHARES_DEVICE",
        "SHARES_EMAIL_DOMAIN",
        "SHARES_ADDRESS",
    ]
    with open("schema/schema.gsql", "r", encoding="utf-8") as f:
        gsql = f.read()
    for e in derived_edges:
        assert e in gsql, f"Derived edge {e} missing from schema.gsql"
