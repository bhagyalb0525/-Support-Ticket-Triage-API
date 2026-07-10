import sys
import json
from fastapi.testclient import TestClient

# Import app to allow offline demo running via TestClient
try:
    from app.main import app
    from app.services.config_service import ConfigService
    HAS_APP = True
except ImportError:
    HAS_APP = False

# Sample tickets to analyze
SAMPLE_TICKETS = [
    {
        "client_id": "bank_x",
        "ticket_text": "I was charged twice for my subscription this month. Please refund the duplicate transaction.",
        "description": "Banking - Billing issue (Negative sentiment, not escalated)"
    },
    {
        "client_id": "bank_x",
        "ticket_text": "ALERT: I noticed an unauthorized transaction on my credit card! I think someone hacked my card and this is fraud. Please lock my account immediately.",
        "description": "Banking - Account Security (Negative sentiment, Escalated by multiple keywords)"
    },
    {
        "client_id": "telecom_y",
        "ticket_text": "There is a complete network outage in my neighborhood since this morning. No service is available on my phone and I cannot make calls. I need this fixed immediately.",
        "description": "Telecom - Network (Negative sentiment, Escalated by outage/no service)"
    },
    {
        "client_id": "telecom_y",
        "ticket_text": "Hello, I want to inquire about broadband plans for my new apartment. Do you have any promotional rates for first-time customers? Thanks!",
        "description": "Telecom - Broadband Inquiry (Positive sentiment, not escalated)"
    },
    {
        "client_id": "ecommerce_z",
        "ticket_text": "The sweater I ordered arrived yesterday but it is the wrong size. I requested a medium and received an extra large. How do I request a product return and replacement?",
        "description": "E-commerce - Product Return (Negative sentiment, not escalated)"
    },
    {
        "client_id": "ecommerce_z",
        "ticket_text": "You charged me twice for order #5830! Refund the double charge immediately or I will initiate a chargeback with my bank!",
        "description": "E-commerce - Fraud/Billing Dispute (Negative sentiment, Escalated by double charge/chargeback)"
    }
]

def run_local_client(client, ticket):
    """Sends analysis request to FastAPI TestClient directly (offline mode)."""
    payload = {
        "client_id": ticket["client_id"],
        "ticket_text": ticket["ticket_text"]
    }
    response = client.post("/tickets/analyze", json=payload)
    return response.status_code, response.json()

def run_remote_http(ticket):
    """Sends analysis request to a running local uvicorn server via httpx."""
    import httpx
    payload = {
        "client_id": ticket["client_id"],
        "ticket_text": ticket["ticket_text"]
    }
    try:
        response = httpx.post("http://127.0.0.1:8000/tickets/analyze", json=payload, timeout=5.0)
        return response.status_code, response.json()
    except Exception as e:
        return None, str(e)

def main():
    print("=" * 80)
    print("                SUPPORT TICKET TRIAGE API - VERIFICATION SCRIPT")
    print("=" * 80)
    
    # Check if we should try to hit the live HTTP server first
    use_http = False
    if len(sys.argv) > 1 and sys.argv[1] == "--http":
        use_http = True
        print("[Mode] Targeting live running server at http://127.0.0.1:8000")
    else:
        print("[Mode] Running offline using FastAPI TestClient (no server needed to run).")
        print("       (To target a running server, run: python demo_script.py --http)")
    
    client = None
    if not use_http:
        if not HAS_APP:
            print("[Error] app module not found in path. Cannot run offline TestClient.")
            sys.exit(1)
        client = TestClient(app)
        
    print("\nStarting analysis of 6 sample tickets...\n")
    
    for i, ticket in enumerate(SAMPLE_TICKETS, 1):
        print("-" * 80)
        print(f"Ticket #{i}: {ticket['description']}")
        print(f"Client: {ticket['client_id']}")
        print(f"Text: \"{ticket['ticket_text']}\"")
        print("-" * 80)
        
        if use_http:
            status_code, result = run_remote_http(ticket)
            if status_code is None:
                print(f"[Error] Could not connect to running server. Is it running on port 8000? Details: {result}")
                print("Falling back to running offline via TestClient...\n")
                if HAS_APP:
                    client = TestClient(app)
                    status_code, result = run_local_client(client, ticket)
                else:
                    continue
        else:
            status_code, result = run_local_client(client, ticket)
            
        if status_code == 200:
            print(f"[SUCCESS] Status: 200")
            print(f"  Topic:        {result.get('primary_topic')}")
            print(f"  Sentiment:    {result.get('sentiment')}")
            print(f"  Keywords:     {result.get('detected_keywords')}")
            print(f"  Suggested:    {result.get('suggested_department')}")
            print(f"  Final Dept:   {result.get('final_department')}")
            print(f"  Escalated:    {result.get('escalate')}")
            print(f"  Urgency:      {result.get('urgency')}")
            print(f"  Complexity:   {result.get('complexity_estimate')}")
            print(f"  SLA Hours:    {result.get('sla_hours')} hrs")
            print(f"  Reasoning:    {result.get('reasoning')}")
        else:
            print(f"[FAILED] Status: {status_code}")
            print(f"  Error details: {json.dumps(result, indent=2)}")
        print()

    print("=" * 80)
    print("Verification completed.")
    print("=" * 80)

if __name__ == "__main__":
    main()
