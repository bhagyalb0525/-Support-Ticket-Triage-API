# Support Ticket Triage API

An AI-powered support ticket triage system for enterprise customer support teams, built using **FastAPI (Python)** and the **Gemini API**. It reads a raw support ticket (text) and returns structured triage insights (department classification, urgency level, estimated resolution complexity, and an escalation flag) driven by per-client rules configured via JSON files.

---

## Architecture Overview

This project adheres to a clean **3-layer architecture**:

```
 ┌────────────────────────────────────────────────────────┐
 │                   API Router Layer                     │
 │          (POST /tickets/analyze, GET/POST configs)      │
 └───────────────────────────┬────────────────────────────┘
                             │
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │                 1. AI Extraction Layer                 │
 │       Extracts topics, sentiment, and keywords         │
 └───────────────────────────┬────────────────────────────┘
                             │
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │                  2. Rule Engine Layer                  │
 │      Applies client rules, resolves SLA and urgency    │
 └───────────────────────────┬────────────────────────────┘
                             │
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │                  3. Response Layer                     │
 │      Assembles combined structured JSON response       │
 └────────────────────────────────────────────────────────┘
```

1. **AI Extraction Layer** (`app/services/gemini_service.py`):
   Sends the raw ticket text and client category list to the Gemini API (`gemini-1.5-flash`) using strict JSON schemas. It extracts primary topic, sentiment, keywords, and a suggested department. If no API key is set, it falls back to a regex-based heuristic extractor for offline/demo capabilities.
2. **Rule Engine Layer** (`app/services/rule_engine.py`):
   A deterministic Python layer (no machine learning) that checks the extracted metadata against the client's configuration file to validate departments, identify escalation matches, determine urgency/SLA targets, and compute a resolution complexity heuristic.
3. **Response Layer** (`app/routes/tickets.py`):
   Combines AI insights and rule engine decisions into a single response payload complete with an audit trail explaining how triage conclusions were reached.

---

## Why Separate AI Extraction and Rule Engines?

Using a hybrid design provides substantial benefits over using a raw LLM to make all decisions:

- **Determinism & Auditability**: Corporate SLAs and escalation flags must adhere to strict, predictable business logic (e.g. *"If keyword X is found, escalate immediately"*). Large Language Models are probabilistic and prone to hallucination; dividing these guarantees business rule compliance.
- **Explainability**: The rule engine maintains a step-by-step reasoning log for why a ticket was routed or escalated, which is vital for auditing.
- **Maintainability**: If client SLA targets, allowed categories, or escalation keywords change, they can be updated instantly in a config file without requiring retraining or modifying LLM prompts.

---

## Project Structure

```
/supportapi
├── /app
│   ├── /models             # Pydantic schema declarations (Strict Typing)
│   │   ├── client.py
│   │   └── ticket.py
│   ├── /routes             # FastAPI thin controllers/routers
│   │   ├── clients.py
│   │   ├── health.py
│   │   └── tickets.py
│   ├── /services           # Service layers
│   │   ├── config_service.py
│   │   ├── gemini_service.py
│   │   └── rule_engine.py
│   ├── dependencies.py     # FastAPI dependency injections (supports mocks)
│   └── main.py             # App configuration and exception formatting
├── /configs                # Configs directory (JSON configurations)
│   ├── bank_x.json
│   ├── telecom_y.json
│   └── ecommerce_z.json
├── /tests                  # Pytest unit and integration tests
├── demo_script.py          # 6-ticket automated verification script
├── requirements.txt        # Package dependencies
└── README.md               # Documentation
```

---

## Setup & Running Instructions

### 1. Prerequisites
Ensure you have **Python 3.9+** installed.

### 2. Install Dependencies
Run the following command in the project root:
```bash
pip install -r requirements.txt
```

### 3. Set Gemini API Key (Optional)
This project runs out-of-the-box in **offline mode** using rule-based fallback heuristics. To activate real AI extraction, set your Gemini API key:

**On Windows (PowerShell):**
```powershell
$env:GEMINI_API_KEY="your-api-key-here"
```

**On Linux / macOS:**
```bash
export GEMINI_API_KEY="your-api-key-here"
```

### 4. Run the Dev Server
Start the FastAPI server:
```bash
uvicorn app.main:app --reload
```
The API documentation will be available locally at: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### 5. Run the Automated Tests
Run the test suite using `pytest`:
```bash
pytest -v
```

### 6. Run the Verification/Demo Script
To execute the triage flow on 6 diverse tickets:

*   **Offline Mode (using FastAPI TestClient):**
    ```bash
    python demo_script.py
    ```
*   **Targeting Running Server (via HTTP requests):**
    ```bash
    python demo_script.py --http
    ```

---

## How to Add a New Client Configuration

To configure a new client, add a JSON file matching their `client_id` under the `/configs` folder. For example, to add `retail_chain_w`, create `/configs/retail_chain_w.json`:

```json
{
  "client_id": "retail_chain_w",
  "domain": "retail",
  "categories": ["billing", "order_status", "returns", "rewards_program"],
  "escalation_keywords": ["double charge", "stolen points", "payment failed"],
  "sla_hours": {
    "critical": 1,
    "high": 3,
    "medium": 12,
    "low": 48
  }
}
```

The config loader will automatically detect and load it on subsequent `/tickets/analyze` requests. Alternatively, you can use the `POST /clients/{client_id}/config` endpoint to create or update configs dynamically.

---

## Example API Endpoint Usage

### 1. GET /health
Basic system health check.

**Request:**
```bash
curl -X GET http://127.0.0.1:8000/health
```

**Response:**
```json
{
  "status": "healthy"
}
```

### 2. POST /tickets/analyze
Analyzes a support ticket.

**Request:**
```bash
curl -X POST http://127.0.0.1:8000/tickets/analyze \
     -H "Content-Type: application/json" \
     -d '{
       "client_id": "bank_x",
       "ticket_text": "Help! I noticed an unauthorized transaction on my credit card! I think someone hacked my card and this is fraud. Please lock my account."
     }'
```

**Response:**
```json
{
  "client_id": "bank_x",
  "primary_topic": "ALERT: I noticed an unauthorized...",
  "sentiment": "negative",
  "detected_keywords": [
    "alert",
    "noticed",
    "unauthorized",
    "transaction"
  ],
  "suggested_department": "account_security",
  "final_department": "account_security",
  "escalate": true,
  "urgency": "critical",
  "complexity_estimate": "moderate",
  "sla_hours": 1,
  "reasoning": "Suggested department '\''account_security'\'' was validated directly against client allowed categories. | Ticket escalated because it contains escalation keywords: ['\''fraud'\'', '\''unauthorized transaction'\'']. | Urgency set to '\''critical'\'' based on combination of escalation=True and sentiment='\''negative'\''. | Resolution complexity is '\''moderate'\'' (character count: 149, keyword count: 4). | SLA resolved to 1 hours according to urgency level '\''critical'\''."
}
```

### 3. GET /clients/{client_id}/config
Retrieve client configuration.

**Request:**
```bash
curl -X GET http://127.0.0.1:8000/clients/bank_x/config
```

**Response:**
```json
{
  "client_id": "bank_x",
  "domain": "banking",
  "categories": [
    "billing",
    "network",
    "account_security",
    "app_bugs"
  ],
  "escalation_keywords": [
    "unauthorized transaction",
    "fraud",
    "account locked",
    "compromised"
  ],
  "sla_hours": {
    "critical": 1,
    "high": 4,
    "medium": 24,
    "low": 72
  }
}
```

### 4. POST /clients/{client_id}/config
Create or update client configuration.

**Request:**
```bash
curl -X POST http://127.0.0.1:8000/clients/bank_x/config \
     -H "Content-Type: application/json" \
     -d '{
       "client_id": "bank_x",
       "domain": "banking",
       "categories": ["billing", "account_security", "app_bugs"],
       "escalation_keywords": ["fraud", "hacked"],
       "sla_hours": {"critical": 1, "high": 4, "medium": 12, "low": 48}
     }'
```

**Response:**
```json
{
  "client_id": "bank_x",
  "domain": "banking",
  "categories": [
    "billing",
    "account_security",
    "app_bugs"
  ],
  "escalation_keywords": [
    "fraud",
    "hacked"
  ],
  "sla_hours": {
    "critical": 1,
    "high": 4,
    "medium": 12,
    "low": 48
  }
}
```
