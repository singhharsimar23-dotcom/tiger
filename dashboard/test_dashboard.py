import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from dashboard.app import app

def test_dashboard():
    client = TestClient(app)

    res = client.get('/')
    assert res.status_code == 200, f"GET / failed: {res.status_code}"
    assert "FraudSight" in res.text
    print("GET / OK")

    res = client.get('/case/case_01')
    assert res.status_code == 200, f"GET /case/case_01 failed: {res.status_code}"
    assert "case_01" in res.text
    print("GET /case/case_01 OK")

    res = client.get('/analytics')
    assert res.status_code == 200, f"GET /analytics failed: {res.status_code}"
    assert "TigerGraph" in res.text
    print("GET /analytics OK")

    res = client.get('/about')
    assert res.status_code == 200, f"GET /about failed: {res.status_code}"
    print("GET /about OK")

    res = client.get('/api/stats')
    assert res.status_code == 200, f"GET /api/stats failed: {res.status_code}"
    print("GET /api/stats OK ->", res.json())

    res = client.get('/api/cases')
    assert res.status_code == 200, f"GET /api/cases failed: {res.status_code}"
    cases = res.json()
    assert len(cases) > 0
    print(f"GET /api/cases OK -> {len(cases)} cases retrieved")

    res = client.get('/api/case/case_01')
    assert res.status_code == 200, f"GET /api/case/case_01 failed: {res.status_code}"
    print("GET /api/case/case_01 OK")

    res = client.get('/api/case/case_01/graph')
    assert res.status_code == 200, f"GET /api/case/case_01/graph failed: {res.status_code}"
    data = res.json()
    assert "elements" in data
    print(f"GET /api/case/case_01/graph OK -> {len(data['elements'])} elements")

    res = client.post('/case/case_01/investigate')
    assert res.status_code == 202, f"POST /case/case_01/investigate failed: {res.status_code}"
    print("POST /case/case_01/investigate OK ->", res.json())

    res = client.get('/case/case_01/sar')
    assert res.status_code in (200, 404), f"GET /case/case_01/sar unexpected: {res.status_code}"
    print(f"GET /case/case_01/sar OK (status {res.status_code})")

    res = client.get('/cases')
    assert res.status_code == 200, f"GET /cases failed: {res.status_code}"
    print("GET /cases OK")

    res = client.get('/cockpit')
    assert res.status_code == 200, f"GET /cockpit failed: {res.status_code}"
    print("GET /cockpit OK")

    res = client.get('/api/graph/sample')
    assert res.status_code == 200, f"GET /api/graph/sample failed: {res.status_code}"
    sample_data = res.json()
    assert "elements" in sample_data and len(sample_data["elements"]) > 0
    print(f"GET /api/graph/sample OK -> {len(sample_data['elements'])} elements")

    res = client.post('/api/ask_agent', json={"query": "Explain the device collusion loop", "case_id": "case_01"})
    assert res.status_code == 200, f"POST /api/ask_agent failed: {res.status_code}"
    ans_data = res.json()
    assert "answer" in ans_data and len(ans_data["answer"]) > 10
    print("POST /api/ask_agent OK ->", ans_data["answer"][:60], "...")

    res = client.get('/api/cluster/status')
    assert res.status_code == 200, f"GET /api/cluster/status failed: {res.status_code}"
    print("GET /api/cluster/status OK ->", res.json().get("status"))

    res = client.post('/api/cluster/ping')
    assert res.status_code == 200, f"POST /api/cluster/ping failed: {res.status_code}"
    print("POST /api/cluster/ping OK ->", res.json().get("status"))

    res = client.get('/api/case/HHG-014/bundle')
    assert res.status_code == 200, f"GET /api/case/HHG-014/bundle failed: {res.status_code}"
    print("GET /api/case/HHG-014/bundle OK -> Content length:", len(res.content))

    # Ground-truth checks on benchmark cases
    res14 = client.get('/api/case/HHG-014')
    assert res14.status_code == 200
    d14 = res14.json()
    assert d14["amount"] == 74.96, f"Expected 74.96, got {d14['amount']}"
    assert d14["verdict"] == "fraud"
    print("GET /api/case/HHG-014 verified: exposure $74.96, verdict fraud")

    res2 = client.get('/api/case/HHG-002')
    assert res2.status_code == 200
    d2 = res2.json()
    assert d2["amount"] == 292.36, f"Expected 292.36, got {d2['amount']}"
    assert d2["verdict"] == "fraud"
    print("GET /api/case/HHG-002 verified: exposure $292.36, verdict fraud")

    res7 = client.get('/api/case/HHG-007')
    assert res7.status_code == 200
    d7 = res7.json()
    assert d7["amount"] == 111.92, f"Expected 111.92, got {d7['amount']}"
    assert d7["verdict"] == "fraud"
    print("GET /api/case/HHG-007 verified: exposure $111.92, verdict fraud")

    res1 = client.get('/api/case/HHG-001')
    assert res1.status_code == 200
    d1 = res1.json()
    assert d1["amount"] == 0.0, f"Expected 0.0, got {d1['amount']}"
    assert d1["verdict"] in ["uncertain", "legitimate"]
    print(f"GET /api/case/HHG-001 verified: exposure $0.00, verdict {d1['verdict']}")

    g14 = client.get('/api/case/HHG-014/graph')
    assert g14.status_code == 200
    g14_data = g14.json()
    g14_node_ids = [n["id"] for n in g14_data.get("nodes", [])]
    assert "C13487" in g14_node_ids, "Real customer C13487 must be in HHG-014 graph"
    assert "C13487-K1" in g14_node_ids, "Real card C13487-K1 must be in HHG-014 graph"
    assert "T3478561" in g14_node_ids, "Real transaction T3478561 must be in HHG-014 graph"
    print("GET /api/case/HHG-014/graph verified: real customer, card, and transaction present")

    res_static = client.get('/data/HHG-014.json')
    assert res_static.status_code == 200
    print("GET /data/HHG-014.json verified: static offline file served successfully")

    print("\n==========================================")
    print("ALL DASHBOARD ROUTES & GROUND TRUTH VERIFIED")
    print("==========================================")

if __name__ == "__main__":
    test_dashboard()
