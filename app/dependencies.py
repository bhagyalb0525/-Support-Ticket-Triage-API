from app.services.config_service import ConfigService
from app.services.gemini_service import GeminiService
from app.services.rule_engine import RuleEngine

# Singletons for service sharing
_config_service = ConfigService()
_gemini_service = GeminiService()
_rule_engine = RuleEngine()

def get_config_service() -> ConfigService:
    return _config_service

def get_gemini_service() -> GeminiService:
    return _gemini_service

def get_rule_engine() -> RuleEngine:
    return _rule_engine
