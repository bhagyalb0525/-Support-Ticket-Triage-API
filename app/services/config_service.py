import os
import json
from pathlib import Path
from app.models.client import ClientConfig

class ClientNotFoundError(Exception):
    """Exception raised when a requested client configuration does not exist."""
    pass

class ConfigService:
    def __init__(self, configs_dir: str = None):
        if configs_dir:
            self.configs_dir = Path(configs_dir)
        else:
            # Locate configs/ relative to project root
            self.configs_dir = Path(__file__).resolve().parent.parent.parent / "configs"
        
        # Ensure the directory exists
        self.configs_dir.mkdir(parents=True, exist_ok=True)

    def load_config(self, client_id: str) -> ClientConfig:
        """
        Loads client config from a JSON file.
        Raises ClientNotFoundError if the client config doesn't exist.
        Raises ValueError if the JSON is malformed or invalid.
        """
        # Ensure client_id is a secure filename
        safe_client_id = "".join(c for c in client_id if c.isalnum() or c in ("-", "_")).strip()
        if not safe_client_id:
            raise ClientNotFoundError("Invalid client_id characters provided.")
            
        file_path = self.configs_dir / f"{safe_client_id}.json"
        
        if not file_path.exists():
            raise ClientNotFoundError(f"Client config '{safe_client_id}' not found.")
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Enforce that client_id in file matches requested ID
            data["client_id"] = safe_client_id
            return ClientConfig(**data)
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Malformed JSON configuration for client '{safe_client_id}': {str(e)}")
        except Exception as e:
            raise ValueError(f"Error parsing client configuration '{safe_client_id}': {str(e)}")

    def save_config(self, client_id: str, config: ClientConfig) -> ClientConfig:
        """
        Saves or updates client configuration file.
        """
        safe_client_id = "".join(c for c in client_id if c.isalnum() or c in ("-", "_")).strip()
        if not safe_client_id:
            raise ValueError("Invalid client_id characters.")
            
        file_path = self.configs_dir / f"{safe_client_id}.json"
        
        # Keep client_id consistent with path
        if config.client_id != safe_client_id:
            config = config.model_copy(update={"client_id": safe_client_id})
            
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(config.model_dump(), f, indent=2)
            return config
        except Exception as e:
            raise ValueError(f"Failed to save configuration for client '{safe_client_id}': {str(e)}")
