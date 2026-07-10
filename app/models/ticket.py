from pydantic import BaseModel, Field, field_validator
from typing import List, Literal

class TicketAnalyzeRequest(BaseModel):
    client_id: str = Field(..., min_length=1, description="Client ID associated with the configuration")
    ticket_text: str = Field(..., min_length=1, description="Raw support ticket text to analyze")

    @field_validator('client_id', 'ticket_text')
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field cannot be empty or only whitespace.")
        return v.strip()

class TicketExtraction(BaseModel):
    primary_topic: str = Field(..., description="The main subject or issue discussed in the ticket")
    sentiment: Literal["positive", "neutral", "negative"] = Field(
        ..., 
        description="The emotional tone of the ticket"
    )
    detected_keywords: List[str] = Field(
        ..., 
        description="Key terms extracted from the ticket relevant for triage"
    )
    suggested_department: str = Field(
        ..., 
        description="The department suggested for this ticket based on categories provided"
    )

class TicketAnalyzeResponse(BaseModel):
    client_id: str = Field(..., description="The client ID")
    primary_topic: str = Field(..., description="The main topic extracted from the ticket")
    sentiment: Literal["positive", "neutral", "negative"] = Field(..., description="Sentiment of the ticket")
    detected_keywords: List[str] = Field(..., description="Keywords detected by the extraction layer")
    suggested_department: str = Field(..., description="The category/department suggested by the LLM")
    
    final_department: str = Field(..., description="The final department matched against allowed categories")
    escalate: bool = Field(..., description="Whether this ticket has been escalated based on keywords")
    urgency: Literal["low", "medium", "high", "critical"] = Field(
        ..., 
        description="The computed urgency based on escalation and sentiment"
    )
    complexity_estimate: Literal["simple", "moderate", "complex"] = Field(
        ..., 
        description="Complexity estimate derived from length and keyword rules"
    )
    sla_hours: int = Field(..., description="The response SLA in hours corresponding to the urgency level")
    reasoning: str = Field(..., description="Auditable reasoning behind the triage and escalation decisions")
