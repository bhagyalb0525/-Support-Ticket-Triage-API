from fastapi import APIRouter, Depends, HTTPException, status
from app.models.ticket import TicketAnalyzeRequest, TicketAnalyzeResponse
from app.services.config_service import ConfigService, ClientNotFoundError
from app.services.gemini_service import GeminiService
from app.services.rule_engine import RuleEngine
from app.dependencies import get_config_service, get_gemini_service, get_rule_engine

router = APIRouter(prefix="/tickets", tags=["Tickets Analysis"])

@router.post("/analyze", response_model=TicketAnalyzeResponse, status_code=status.HTTP_200_OK)
def analyze_ticket(
    request: TicketAnalyzeRequest,
    config_service: ConfigService = Depends(get_config_service),
    gemini_service: GeminiService = Depends(get_gemini_service),
    rule_engine: RuleEngine = Depends(get_rule_engine)
):
    """
    Analyzes a raw support ticket text and triages it according to the client rules.
    1. Reads raw ticket text
    2. Uses Gemini API (or fallback heuristics) to extract structured features
    3. Runs a deterministic rule engine to classify final department, escalation flag, urgency, and complexity
    4. Combines results into a single structured response with clear auditing reasoning
    """
    # 1. Fetch Client Config
    try:
        config = config_service.load_config(request.client_id)
    except ClientNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown client_id: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid client configuration file: {str(e)}"
        )

    # 2. Extract Features using LLM (Gemini Layer)
    try:
        extracted_info = gemini_service.extract_ticket_info(
            ticket_text=request.ticket_text,
            categories=config.categories
        )
    except Exception as e:
        # Fallback should prevent this, but let's be extremely safe
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction layer failed: {str(e)}"
        )

    # 3. Apply Deterministic Rule Engine Layer & Build Response
    try:
        response = rule_engine.evaluate(
            extracted=extracted_info,
            config=config,
            ticket_text=request.ticket_text
        )
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rule evaluation failed: {str(e)}"
        )
