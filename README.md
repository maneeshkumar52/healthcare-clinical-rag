# Healthcare Clinical RAG System
**Project 5, Chapter 20 — Prompt to Production by Maneesh Kumar**

A HIPAA-compliant Retrieval-Augmented Generation (RAG) system for clinical guideline Q&A, built with Azure OpenAI, Azure AI Search, Azure AI Language, and Azure Cosmos DB. Designed for qualified healthcare professionals only.

---

## Overview

This system enables clinicians to query authoritative clinical guidelines using natural language. Every query is:
1. **Scanned for PHI** (Protected Health Information) and redacted before processing
2. **Filtered by speciality RBAC** — each clinician only accesses guidelines relevant to their role
3. **Grounded in indexed guidelines** via Azure AI Search hybrid (semantic + vector) retrieval
4. **Answered with mandatory disclaimer** — all responses include a clinical disclaimer
5. **Fully audit-logged** to Azure Cosmos DB with a 7-year immutable TTL (HIPAA requirement)

---

## Architecture

```
Clinician Request
       |
       v
  [FastAPI /query]
       |
       +---> PHI Detection (Azure AI Language or local regex fallback)
       |           |
       |      [Redacted Query]
       |           |
       +---> Speciality RBAC (JWT validation -> allowed_categories filter)
       |           |
       +---> Azure AI Search (hybrid: semantic + vector embeddings)
       |           |
       |      [Top-K Clinical Documents]
       |           |
       +---> Azure OpenAI GPT-4o (grounded generation with citations)
       |           |
       |      [Grounded Answer + Disclaimer]
       |           |
       +---> HIPAA Audit Log (Cosmos DB, 7-year TTL)
       |
       v
  Clinical Response (JSON)
```

---

## HIPAA Compliance Controls

| Control | Implementation |
|---------|---------------|
| PHI Detection | Azure AI Language PII recognition + local regex fallback |
| PHI Redaction | All queries redacted before LLM processing; redacted form stored in audit log |
| Access Control | JWT-based authentication; speciality-based RBAC on guideline categories |
| Audit Logging | Every query logged to Cosmos DB with clinician ID, speciality, redacted question, answer excerpt, PHI flag, confidence, and latency |
| Data Retention | 7-year TTL on audit records (HIPAA minimum) |
| Encryption | Azure services provide encryption at rest and in transit (TLS 1.2+) |
| Minimum Necessary | Clinicians only retrieve guidelines matching their allowed speciality categories |
| Disclaimer | Mandatory clinical disclaimer appended to every response |

---

## Speciality-Based RBAC

| Role | Allowed Guideline Categories |
|------|------------------------------|
| general_practitioner | general, primary_care, preventive |
| cardiologist | cardiac, cardiology, general, primary_care |
| psychiatrist | mental_health, psychiatry, general |
| pharmacist | formulary, prescribing, pharmacy, general |
| physician | general, primary_care, preventive, formulary |
| nurse | general, primary_care |

JWT tokens encode the clinician's speciality. Azure AI Search filters results by `category` field at query time, ensuring strict data access boundaries.

---

## Project Structure

```
healthcare-clinical-rag/
├── src/
│   ├── __init__.py          # Package init
│   ├── main.py              # FastAPI app, /health and /query endpoints
│   ├── phi_detection.py     # Azure AI Language PHI detection + regex fallback
│   ├── retriever.py         # Azure AI Search hybrid retrieval with RBAC filter
│   ├── generator.py         # Azure OpenAI GPT-4o grounded generation
│   ├── auth.py              # JWT validation, speciality RBAC
│   ├── audit.py             # HIPAA audit logging to Cosmos DB
│   ├── config.py            # Pydantic settings from environment variables
│   └── models.py            # Pydantic data models
├── indexer/
│   ├── index_guidelines.py  # Index clinical guidelines into Azure AI Search
│   └── guidelines/          # Source clinical guideline markdown files
│       ├── diabetes_management.md
│       ├── hypertension_guidelines.md
│       ├── antibiotic_prescribing.md
│       └── mental_health_screening.md
├── tests/
│   ├── __init__.py
│   ├── test_phi_detection.py
│   └── test_retriever.py
├── infra/
│   ├── Dockerfile
│   └── azure-deploy.sh
├── .env.example
├── requirements.txt
└── README.md
```

---

## Prerequisites

- Python 3.11+
- Azure OpenAI resource with GPT-4o and text-embedding-3-large deployments
- Azure AI Search resource (Standard tier for semantic search)
- Azure AI Language resource (for PII detection)
- Azure Cosmos DB account (with SQL API)

---

## Setup

### 1. Clone and install dependencies

```bash
git clone <repo-url>
cd healthcare-clinical-rag
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env with your Azure resource credentials
```

### 3. Index clinical guidelines

```bash
python indexer/index_guidelines.py
```

This will:
- Create the Azure AI Search index with semantic + vector search configuration
- PHI-scan and chunk each guideline markdown file
- Generate embeddings with text-embedding-3-large
- Upload all chunks to the search index

### 4. Run the API server

```bash
uvicorn src.main:app --reload --port 8000
```

API documentation available at: `http://localhost:8000/docs`

---

## API Usage

### Health Check

```bash
curl http://localhost:8000/health
```

```json
{"status": "healthy", "service": "healthcare-clinical-rag", "version": "1.0.0"}
```

### Query Clinical Guidelines

**Generate a test JWT token (development only):**

```python
from src.auth import create_test_token
token = create_test_token("dr-001")  # General practitioner
print(token)
```

**Query the API:**

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-jwt-token>" \
  -d '{"question": "What is the first-line treatment for Type 2 diabetes in a patient with CKD?"}'
```

**Example response:**

```json
{
  "answer": "According to NICE NG28, first-line treatment for Type 2 diabetes is Metformin 500mg once daily, titrated to 1g BD. However, in patients with CKD (eGFR 30-44 mL/min/1.73m2), Metformin should be reduced to a maximum of 500mg BD, and is contraindicated if eGFR <30 mL/min/1.73m2. SGLT2 inhibitors lose glucose-lowering efficacy at eGFR <45 mL/min/1.73m2...\n\nCLINICAL DISCLAIMER: ...",
  "sources": ["Diabetes Management", "Hypertension Guidelines"],
  "confidence": "High",
  "medical_disclaimer": "CLINICAL DISCLAIMER: ...",
  "query_id": "abc-123-...",
  "phi_detected_in_query": false
}
```

### Test Different Clinician Roles

```python
from src.auth import create_test_token

# Cardiologist — access to cardiac, cardiology, general, primary_care categories
token = create_test_token("dr-002")

# Psychiatrist — access to mental_health, psychiatry, general categories
token = create_test_token("dr-003")

# Pharmacist — access to formulary, prescribing, pharmacy, general categories
token = create_test_token("ph-001")
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## PHI Detection

The `PHIDetector` class in `src/phi_detection.py` uses a two-tier approach:

1. **Azure AI Language (primary):** Microsoft's enterprise-grade PII recognition service, detecting entities including names, SSNs, NI numbers, phone numbers, email addresses, dates of birth, patient IDs, and medical licence numbers.

2. **Local regex heuristics (fallback):** If Azure AI Language is unavailable or returns an error, local regex patterns provide coverage for common PHI patterns including SSNs, NI numbers, names, email addresses, UK phone numbers, patient IDs, and dates of birth.

All PHI is redacted with category-specific placeholders (e.g., `[SSN REDACTED]`, `[EMAIL REDACTED]`) before any LLM processing. Only the redacted form is stored in audit logs.

---

## Deployment to Azure Container Apps

```bash
# Ensure az CLI is authenticated
az login

# Set secrets in Azure Container Apps before deploying
chmod +x infra/azure-deploy.sh
./infra/azure-deploy.sh
```

---

## Security Considerations

- **Never commit `.env` to version control** — use Azure Key Vault in production
- **JWT secret** must be a cryptographically strong random string in production (minimum 32 characters)
- **TLS termination** is handled by Azure Container Apps ingress
- **Network isolation:** Deploy within a VNet for enhanced security in regulated environments
- **Audit log access:** Restrict Cosmos DB access to audit role only; implement row-level security

---

## Book Reference

This project is **Project 5** from **Chapter 20** of:

> **"Prompt to Production: Building Production AI Agents and Agentic Systems"**
> by Maneesh Kumar

The chapter covers HIPAA-compliant RAG architectures, PHI detection patterns, speciality-based access control, and responsible AI deployment in regulated healthcare environments.
