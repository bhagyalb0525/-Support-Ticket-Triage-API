import os
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

from app.routes import health, clients, tickets

# Initialize FastAPI App
app = FastAPI(
    title="Support Ticket Triage API",
    description=(
        "An AI-powered support ticket triage API designed for IT and customer support. "
        "Leverages Gemini API (with heuristic offline fallback) for extraction and "
        "runs custom deterministic rules on client-specific config files."
    ),
    version="1.0.0",
)

# Register Router Components
app.include_router(health.router)
app.include_router(clients.router)
app.include_router(tickets.router)

# Custom Error Handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Formats Pydantic and request validation errors into a clean, structured JSON format.
    """
    formatted_errors = []
    for error in exc.errors():
        # Clean path formatting
        field_path = " -> ".join(str(loc) for loc in error.get("loc", []))
        formatted_errors.append({
            "field": field_path,
            "error_type": error.get("type"),
            "message": error.get("msg")
        })
        
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "message": "The request payload failed input schema validation.",
            "details": formatted_errors
        }
    )

from fastapi import HTTPException

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Ensures that HTTPExceptions (like 404 Not Found, 400 Bad Request) are returned
    with a structured JSON schema containing the 'message' key.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP Error",
            "message": exc.detail
        }
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """
    Prevents leaking internal stack traces to users on unhandled server exceptions.
    """

        
    # Standard fallback for actual internal errors
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please contact the administrator.",
            "details": str(exc)
        }
    )

if __name__ == "__main__":
    import uvicorn
    # Allow running directly via python app/main.py
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
