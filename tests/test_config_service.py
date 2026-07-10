import pytest
from app.services.config_service import ConfigService, ClientNotFoundError
from app.models.client import ClientConfig

def test_config_service_non_existent(tmp_path):
    """
    Verifies that loading a non-existent client configuration raises ClientNotFoundError.
    """
    configs_dir = tmp_path / "configs"
    service = ConfigService(configs_dir=str(configs_dir))
    
    with pytest.raises(ClientNotFoundError):
        service.load_config("missing_client")

def test_config_service_save_and_load(tmp_path):
    """
    Verifies that we can save a client configuration and load it back correctly.
    """
    configs_dir = tmp_path / "configs"
    service = ConfigService(configs_dir=str(configs_dir))
    
    client_data = {
        "client_id": "test_bank",
        "domain": "banking",
        "categories": ["billing", "account_security"],
        "escalation_keywords": ["unauthorized", "fraud"],
        "sla_hours": {"critical": 1, "high": 4, "medium": 24, "low": 72}
    }
    
    config = ClientConfig(**client_data)
    
    # Save config
    saved_config = service.save_config("test_bank", config)
    assert saved_config.client_id == "test_bank"
    assert saved_config.domain == "banking"
    
    # Verify file was written
    assert (configs_dir / "test_bank.json").exists()
    
    # Load config and verify fields
    loaded_config = service.load_config("test_bank")
    assert loaded_config.client_id == "test_bank"
    assert loaded_config.domain == "banking"
    assert loaded_config.categories == ["billing", "account_security"]
    assert loaded_config.escalation_keywords == ["unauthorized", "fraud"]
    assert loaded_config.sla_hours == {"critical": 1, "high": 4, "medium": 24, "low": 72}

def test_config_service_invalid_json(tmp_path):
    """
    Verifies that loading a malformed/invalid JSON configuration file raises ValueError.
    """
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir(parents=True, exist_ok=True)
    
    # Write invalid JSON content
    bad_file = configs_dir / "corrupted_client.json"
    with open(bad_file, "w", encoding="utf-8") as f:
        f.write("{invalid_json_here")
        
    service = ConfigService(configs_dir=str(configs_dir))
    
    with pytest.raises(ValueError) as excinfo:
        service.load_config("corrupted_client")
    assert "Malformed JSON" in str(excinfo.value)
