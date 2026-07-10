from pydantic import BaseModel, Field, field_validator
from typing import List, Dict

class ClientConfig(BaseModel):
    client_id: str = Field(
        ..., 
        description="Unique identifier for the client", 
        min_length=1, 
        pattern="^[a-zA-Z0-9_-]+$"
    )
    domain: str = Field(..., description="Domain of the client (e.g., banking, telecom)", min_length=1)
    categories: List[str] = Field(..., description="Allowed ticket categories / departments")
    escalation_keywords: List[str] = Field(..., description="Keywords that trigger automated escalation")
    sla_hours: Dict[str, int] = Field(
        ..., 
        description="SLA hours for each urgency level (critical, high, medium, low)"
    )

    @field_validator('categories')
    @classmethod
    def validate_categories(cls, v: List[str]) -> List[str]:
        cleaned = [cat.strip().lower() for cat in v if cat.strip()]
        if not cleaned:
            raise ValueError("Categories list must contain at least one non-empty string.")
        return cleaned

    @field_validator('escalation_keywords')
    @classmethod
    def validate_escalation_keywords(cls, v: List[str]) -> List[str]:
        return [kw.strip().lower() for kw in v if kw.strip()]

    @field_validator('sla_hours')
    @classmethod
    def validate_sla_hours(cls, v: Dict[str, int]) -> Dict[str, int]:
        required_levels = {"critical", "high", "medium", "low"}
        # Check that we have exactly the required levels
        missing = required_levels - set(v.keys())
        if missing:
            raise ValueError(f"Missing SLA definition for urgency levels: {missing}")
        
        for level, hours in v.items():
            if hours < 0:
                raise ValueError(f"SLA hours for level '{level}' cannot be negative.")
        return v
