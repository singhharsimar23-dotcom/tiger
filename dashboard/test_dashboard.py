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

    print("\n==========================================")
    print("ALL DASHBOARD ROUTES VERIFIED SUCCESSFULLY")
    print("==========================================")

if __name__ == "__main__":
    test_dashboard()
