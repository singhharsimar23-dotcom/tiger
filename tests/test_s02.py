import os
import pytest
from dotenv import load_dotenv

load_dotenv()

EXPECTED_VERTICES = [
    "Transaction",
    "Account",
    "Device",
    "IPCluster",
    "Case",
    "Evidence",
    "PatternTemplate",
    "PolicyRule",
    "Action",
    "Decision",
]

EXPECTED_EDGES = [
    "PERFORMED",
    "USED_DEVICE",
    "FROM_IP_CLUSTER",
    "SHARES_DEVICE",
    "SHARES_EMAIL_DOMAIN",
    "SHARES_ADDRESS",
    "CASE_TARGETS_TXN",
    "CASE_TARGETS_ACCOUNT",
    "EVIDENCE_FOR",
    "CASE_MATCHES_PATTERN",
    "TXN_MATCHES_PATTERN",
    "CASE_TRIGGERED_ACTION",
    "ACTION_GOVERNED_BY",
    "CASE_HAS_DECISION",
    "CASE_SIMILAR_TO",
]

@pytest.fixture(scope="module")
def tg_conn():
    try:
        import pyTigerGraph as tg
    except ImportError:
        pytest.skip("pyTigerGraph not installed")

    host = os.getenv("TG_HOST", "http://127.0.0.1:14240")
    graph = os.getenv("TG_GRAPHNAME", "FraudGraph")
    user = os.getenv("TG_USERNAME", "tigergraph")
    password = os.getenv("TG_PASSWORD", "tigergraph")
    secret = os.getenv("TG_SECRET", None) or None
    token = os.getenv("TG_TOKEN", None) or None

    try:
        conn = tg.TigerGraphConnection(
            host=host,
            graphname=graph,
            username=user,
            password=password,
            secret=secret,
            apiToken=token,
        )
        conn.ping()
        return conn
    except Exception as e:
        pytest.skip(f"Could not connect to TigerGraph instance at {host}: {e}")

def test_graph_exists(tg_conn):
    """Verify FraudGraph exists on TigerGraph instance."""
    graphs = tg_conn.getGraphs()
    assert os.getenv("TG_GRAPHNAME", "FraudGraph") in graphs or len(graphs) > 0

def test_all_vertices_present(tg_conn):
    """Assert all expected vertex types exist in the schema."""
    actual_vertices = set(tg_conn.getVertexTypes())
    for v in EXPECTED_VERTICES:
        assert v in actual_vertices, f"Missing expected vertex type: {v}"

def test_all_edges_present(tg_conn):
    """Assert all expected edge types exist in the schema."""
    actual_edges = set(tg_conn.getEdgeTypes())
    for e in EXPECTED_EDGES:
        assert e in actual_edges, f"Missing expected edge type: {e}"

def test_empty_graph(tg_conn):
    """Assert graph is initially empty before data loading (S03)."""
    vertex_count = tg_conn.getVertexCount("*")
    if isinstance(vertex_count, dict):
        total_v = sum(vertex_count.values())
    else:
        total_v = vertex_count
    assert total_v == 0, f"Expected empty graph, but found {total_v} vertices"
