from fastapi import APIRouter, Depends, HTTPException, status
from app.models.client import ClientConfig
from app.services.config_service import ConfigService, ClientNotFoundError
from app.dependencies import get_config_service

router = APIRouter(prefix="/clients", tags=["Client Configs"])

@router.get("/{client_id}/config", response_model=ClientConfig)
def get_client_config(
    client_id: str, 
    config_service: ConfigService = Depends(get_config_service)
):
    """
    Retrieve the configuration for a specific client.
    """
    try:
        return config_service.load_config(client_id)
    except ClientNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=str(e)
        )

@router.post("/{client_id}/config", response_model=ClientConfig, status_code=status.HTTP_200_OK)
def create_or_update_client_config(
    client_id: str, 
    config: ClientConfig, 
    config_service: ConfigService = Depends(get_config_service)
):
    """
    Create or update the configuration for a specific client.
    Ensures that the client_id in the URL matches the client_id in the request body.
    """
    if config.client_id != client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mismatch between path client_id '{client_id}' and body client_id '{config.client_id}'."
        )
    try:
        return config_service.save_config(client_id, config)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=str(e)
        )
