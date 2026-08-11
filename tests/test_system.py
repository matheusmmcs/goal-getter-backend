from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_versionsys_endpoint():
    response = client.get("/api/versionsys")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert data["version"] == "1.0.0"

def test_environment_endpoint():
    response = client.get("/api/environment")
    assert response.status_code == 200
    data = response.json()
    assert "nodeEnv" in data
