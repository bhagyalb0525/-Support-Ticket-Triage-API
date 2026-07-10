import pytest
from fastapi.testclient import TestClient
from fastapi import status
from app.main import app
from app.dependencies import get_config_service
from app.services.config_service import ConfigService
from app.models.client import ClientConfig

# We override the ConfigService dependency to use a clean temporary directory for each test run
@pytest.fixture
def api_client(tmp_path):
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    
    # Pre-populate bank_x configuration for ticket analysis tests
    bank_x_data = {
        "client_id": "bank_x",
        "domain": "banking",
        "categories": ["billing", "network", "account_security", "app_bugs"],
        "escalation_keywords": ["unauthorized transaction", "fraud", "account locked"],
        "sla_hours": {"critical": 1, "high": 4, "medium": 24, "low": 72}
    }
    import json
    with open(configs_dir / "bank_x.json", "w", encoding="utf-8") as f:
        json.dump(bank_x_data, f)
        
    test_config_service = ConfigService(configs_dir=str(configs_dir))
    
    # Apply FastAPI dependency override
    app.dependency_overrides[get_config_service] = lambda: test_config_service
    
    client = TestClient(app)
    yield client
    
    # Clean up overrides after test
    app.dependency_overrides.clear()

def test_health_endpoint(api_client):
    """
    Verifies that the GET /health endpoint returns a 200 status and healthy status message.
    """
    response = api_client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "healthy"}

def test_get_config_success(api_client):
    """
    Verifies that GET /clients/{client_id}/config successfully retrieves an existing client config.
    """
    response = api_client.get("/clients/bank_x/config")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["client_id"] == "bank_x"
    assert data["domain"] == "banking"
    assert "account_security" in data["categories"]

def test_get_config_not_found(api_client):
    """
    Verifies that GET /clients/{client_id}/config returns a 404 error when client is unknown.
    """
    response = api_client.get("/clients/unknown_client/config")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["message"]

def test_create_config_success(api_client):
    """
    Verifies that POST /clients/{client_id}/config creates/updates configuration files.
    """
    new_client_id = "telecom_z"
    payload = {
        "client_id": new_client_id,
        "domain": "telecom",
        "categories": ["billing", "broadband"],
        "escalation_keywords": ["outage", "stolen"],
        "sla_hours": {"critical": 2, "high": 6, "medium": 12, "low": 48}
    }
    response = api_client.post(f"/clients/{new_client_id}/config", json=payload)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["client_id"] == new_client_id
    assert data["domain"] == "telecom"
    
    # Double check that we can now fetch it
    fetch_resp = api_client.get(f"/clients/{new_client_id}/config")
    assert fetch_resp.status_code == status.HTTP_200_OK
    assert fetch_resp.json()["domain"] == "telecom"

def test_create_config_mismatch(api_client):
    """
    Verifies that POST /clients/{client_id}/config rejects request if path ID and body ID mismatch.
    """
    payload = {
        "client_id": "different_id",
        "domain": "telecom",
        "categories": ["billing"],
        "escalation_keywords": [],
        "sla_hours": {"critical": 2, "high": 6, "medium": 12, "low": 48}
    }
    response = api_client.post("/clients/telecom_z/config", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Mismatch between path" in response.json()["message"]

def test_analyze_ticket_success(api_client):
    """
    Verifies that POST /tickets/analyze successfully triages a ticket using existing client configs.
    """
    payload = {
        "client_id": "bank_x",
        "ticket_text": "I see an unauthorized transaction of $500 on my credit card! This is fraud!"
    }
    response = api_client.post("/tickets/analyze", json=payload)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    assert data["client_id"] == "bank_x"
    assert data["escalate"] is True
    assert data["urgency"] == "critical" # Negative sentiment (fraud signal) + Escalated
    assert data["final_department"] in ["billing", "account_security"] # Validated category
    assert data["sla_hours"] == 1
    assert "reasoning" in data

def test_analyze_ticket_unknown_client(api_client):
    """
    Verifies that POST /tickets/analyze returns a 404 error if client configuration is missing.
    """
    payload = {
        "client_id": "unknown_bank",
        "ticket_text": "I can't log in."
    }
    response = api_client.post("/tickets/analyze", json=payload)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "Unknown client_id" in response.json()["message"]

def test_analyze_ticket_validation_error(api_client):
    """
    Verifies that POST /tickets/analyze returns a 422 error on empty inputs.
    """
    payload = {
        "client_id": "",
        "ticket_text": "   "
    }
    response = api_client.post("/tickets/analyze", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()
    assert data["error"] == "Validation Error"
    assert len(data["details"]) > 0
