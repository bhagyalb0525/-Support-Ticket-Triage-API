import pytest
from app.models.client import ClientConfig
from app.models.ticket import TicketExtraction
from app.services.rule_engine import RuleEngine

@pytest.fixture
def sample_config():
    return ClientConfig(
        client_id="test_client",
        domain="finance",
        categories=["billing", "network", "account_security"],
        escalation_keywords=["fraud", "compromised", "account locked"],
        sla_hours={"critical": 1, "high": 4, "medium": 12, "low": 24}
    )

@pytest.fixture
def engine():
    return RuleEngine()

def test_rule_engine_department_exact_match(engine, sample_config):
    """
    Test that department resolves directly when matching case-insensitively.
    """
    extracted = TicketExtraction(
        primary_topic="Payment issue",
        sentiment="neutral",
        detected_keywords=["payment"],
        suggested_department="Billing" # Mixed case
    )
    res = engine.evaluate(extracted, sample_config, "I have a billing issue.")
    assert res.final_department == "billing" # Matches original casing in config

def test_rule_engine_department_closest_match(engine, sample_config):
    """
    Test that department resolves using closest/substring matching if possible.
    """
    extracted = TicketExtraction(
        primary_topic="Cannot connect",
        sentiment="neutral",
        detected_keywords=["wifi"],
        suggested_department="home_network_connection" # Substring contains 'network'
    )
    res = engine.evaluate(extracted, sample_config, "Wi-Fi is down.")
    assert res.final_department == "network"

def test_rule_engine_department_fallback(engine, sample_config):
    """
    Test that department falls back to first allowed category when suggested department is totally unrelated.
    """
    extracted = TicketExtraction(
        primary_topic="Unknown bug",
        sentiment="neutral",
        detected_keywords=["bug"],
        suggested_department="unknown_marketing_dept"
    )
    res = engine.evaluate(extracted, sample_config, "Random text here.")
    assert res.final_department == "billing" # Index 0 category
    assert "Fell back to default category" in res.reasoning

def test_rule_engine_escalate_and_urgency(engine, sample_config):
    """
    Test combinations of escalation keywords and sentiment for urgency mappings.
    """
    # 1. Escalated + Negative Sentiment -> Critical
    extracted = TicketExtraction(
        primary_topic="Locked out",
        sentiment="negative",
        detected_keywords=["account locked"],
        suggested_department="account_security"
    )
    res = engine.evaluate(extracted, sample_config, "My account locked and I am furious.")
    assert res.escalate is True
    assert res.urgency == "critical"
    assert res.sla_hours == 1

    # 2. Escalated + Positive Sentiment -> High
    extracted2 = TicketExtraction(
        primary_topic="Locked out but thanks",
        sentiment="positive",
        detected_keywords=["account locked"],
        suggested_department="account_security"
    )
    res2 = engine.evaluate(extracted2, sample_config, "Thanks for locking my account.")
    assert res2.escalate is True
    assert res2.urgency == "high"
    assert res2.sla_hours == 4

    # 3. Not Escalated + Negative Sentiment -> Medium
    extracted3 = TicketExtraction(
        primary_topic="Slow network",
        sentiment="negative",
        detected_keywords=["slow"],
        suggested_department="network"
    )
    res3 = engine.evaluate(extracted3, sample_config, "This network is very slow.")
    assert res3.escalate is False
    assert res3.urgency == "medium"
    assert res3.sla_hours == 12

    # 4. Not Escalated + Neutral Sentiment -> Low
    extracted4 = TicketExtraction(
        primary_topic="Inquiry",
        sentiment="neutral",
        detected_keywords=["question"],
        suggested_department="billing"
    )
    res4 = engine.evaluate(extracted4, sample_config, "Just a routine question about billing.")
    assert res4.escalate is False
    assert res4.urgency == "low"
    assert res4.sla_hours == 24

def test_rule_engine_complexity_estimate(engine, sample_config):
    """
    Test complexity estimate thresholds.
    """
    extracted = TicketExtraction(
        primary_topic="Short",
        sentiment="neutral",
        detected_keywords=["one", "two"],
        suggested_department="billing"
    )
    
    # 1. Simple: < 150 chars AND <= 2 keywords
    res = engine.evaluate(extracted, sample_config, "Very short ticket.")
    assert res.complexity_estimate == "simple"

    # 2. Complex: >= 500 chars OR >= 5 keywords
    extracted_complex = TicketExtraction(
        primary_topic="Many issues",
        sentiment="negative",
        detected_keywords=["one", "two", "three", "four", "five"],
        suggested_department="billing"
    )
    res_complex = engine.evaluate(extracted_complex, sample_config, "Short text but too many keywords.")
    assert res_complex.complexity_estimate == "complex"

    # Long text
    long_text = "This is a very long support ticket text. " * 20 # 800 chars
    res_long = engine.evaluate(extracted, sample_config, long_text)
    assert res_long.complexity_estimate == "complex"

    # 3. Moderate: anything else
    extracted_moderate = TicketExtraction(
        primary_topic="Normal",
        sentiment="neutral",
        detected_keywords=["one", "two", "three"],
        suggested_department="billing"
    )
    res_mod = engine.evaluate(extracted_moderate, sample_config, "Medium length ticket text that is neither too short nor too long.")
    assert res_mod.complexity_estimate == "moderate"
