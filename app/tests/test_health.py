"""
Tests for health endpoint
"""
from app.core.constants import SYSTEM_CREDIT


def test_health_endpoint(client):
    """Test health endpoint returns correct response"""
    response = client.get("/api/v1/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "ok"
    assert data["service"] == "acs-hrms-backend"
    assert data["credit"] == SYSTEM_CREDIT
