"""
Tests for version endpoint
"""
import pytest
from fastapi import status
from app.core.constants import SYSTEM_CREDIT


def test_version_endpoint_returns_credit_and_version(client):
    """Test that version endpoint returns credit and version information"""
    response = client.get("/api/v1/version")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    assert data["service"] == "acs-hrms-backend"
    assert "version" in data
    assert data["env"] in ["local", "staging", "prod"]
    assert data["credit"] == SYSTEM_CREDIT


def test_version_endpoint_accessible_without_auth(client):
    """Test that version endpoint is accessible without authentication"""
    response = client.get("/api/v1/version")
    
    assert response.status_code == status.HTTP_200_OK
