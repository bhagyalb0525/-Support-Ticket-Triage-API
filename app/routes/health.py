from fastapi import APIRouter

router = APIRouter()

@router.get("/health", tags=["System"])
def health_check():
    """
    Basic health check endpoint to verify that the service is running.
    """
    return {"status": "healthy"}
