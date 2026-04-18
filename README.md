# Healthcare Clinical RAG

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

Clinical RAG system for grounded healthcare Q&A with PHI detection, HIPAA audit logging, clinician authentication, and compliant knowledge retrieval — powered by Azure OpenAI, Azure AI Search, and Azure Text Analytics.

## Architecture

```
Clinical Guidelines
        │
        ▼
┌──────────────────────────┐
│  Indexer Pipeline        │
│  index_guidelines.py     │──► Azure AI Search (vector index)
└──────────────────────────┘

Clinician Query
        │
        ▼
┌───────────────────────────────────────┐
│  FastAPI Service (:8000)              │
│                                       │
│  Auth ──► validate_clinician()        │──► JWT + role verification
│       │                               │
│  PHIDetector ──► Azure Text Analytics │──► PII/PHI entity detection
│       │                               │
│  ClinicalRetriever ──► AI Search     │──► Guideline retrieval
│       │                               │
│  ClinicalGenerator ──► GPT-4o        │──► Grounded answer + disclaimer
│       │                               │
│  HIPAAAuditLogger ──► Cosmos DB      │──► HIPAA-compliant audit trail
└───────────────────────────────────────┘
```

## Key Features

- **PHI Detection** — Azure Text Analytics scans queries for Protected Health Information before processing
- **HIPAA Audit Logging** — Every interaction logged to Cosmos DB with clinician context, timestamps, and PHI flags
- **Clinician Authentication** — JWT-based auth with role validation (physician, nurse, pharmacist)
- **Medical Disclaimer** — All responses include configurable medical disclaimers
- **Grounded Answers** — RAG pipeline ensures responses cite specific clinical guidelines
- **Clinical Guideline Indexing** — Structured ingestion of medical guidelines with semantic chunking

## Step-by-Step Flow

### Step 1: Guideline Ingestion
Run `indexer/index_guidelines.py` to process clinical guidelines from `indexer/guidelines/`, embed them, and index in Azure AI Search.

### Step 2: Clinician Authentication
Clinician authenticates via JWT. `validate_clinician()` verifies role and credentials.

### Step 3: PHI Screening
`PHIDetector` scans the incoming query using Azure Text Analytics to detect any PHI/PII entities. Flagged queries are logged but still processed.

### Step 4: Guideline Retrieval
`ClinicalRetriever` performs hybrid search against indexed clinical guidelines, returning relevant chunks with confidence scores.

### Step 5: Answer Generation
`ClinicalGenerator` sends retrieved context to GPT-4o with a medical system prompt. Response includes grounded citations and a medical disclaimer.

### Step 6: HIPAA Audit
`HIPAAAuditLogger` writes a `HIPAAAuditRecord` to Cosmos DB containing query, clinician context, PHI detection results, retrieved guidelines, and generated answer.

## Repository Structure

```
healthcare-clinical-rag/
├── src/
│   ├── main.py              # FastAPI app with lifespan management
│   ├── retriever.py          # ClinicalRetriever — guideline search
│   ├── generator.py          # ClinicalGenerator — grounded answer generation
│   ├── phi_detection.py      # PHIDetector — Azure Text Analytics PII/PHI scan
│   ├── auth.py               # Clinician JWT authentication
│   ├── audit.py              # HIPAAAuditLogger — Cosmos DB audit trail
│   ├── models.py             # ClinicalQuery, ClinicalResponse, HIPAAAuditRecord
│   └── config.py             # Environment settings
├── indexer/
│   ├── index_guidelines.py   # Clinical guideline indexing pipeline
│   └── guidelines/           # Sample clinical guidelines
├── tests/
│   ├── test_phi_detection.py
│   └── test_retriever.py
├── infra/
│   ├── Dockerfile
│   └── azure-deploy.sh
├── demo_e2e.py
├── requirements.txt
└── .env.example
```

## Quick Start

```bash
git clone https://github.com/maneeshkumar52/healthcare-clinical-rag.git
cd healthcare-clinical-rag
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Configure Azure credentials
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

## Configuration

| Variable | Description |
|----------|-------------|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint |
| `AZURE_OPENAI_DEPLOYMENT` | Model deployment (gpt-4o) |
| `AZURE_SEARCH_ENDPOINT` | Azure AI Search endpoint |
| `AZURE_SEARCH_INDEX_NAME` | Index (clinical-guidelines) |
| `AZURE_LANGUAGE_ENDPOINT` | Azure Text Analytics for PHI detection |
| `COSMOS_ENDPOINT` | Cosmos DB for HIPAA audit logs |
| `COSMOS_AUDIT_CONTAINER` | Audit container (hipaa-audit) |
| `JWT_SECRET` | JWT signing secret |

## Testing

```bash
pytest -q
python demo_e2e.py
```

## License

MIT
