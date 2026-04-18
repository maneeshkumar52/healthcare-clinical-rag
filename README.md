# 🏥 Healthcare Clinical RAG

> **HIPAA-Compliant Clinical Guideline Q&A — PHI Detection ➜ Speciality RBAC ➜ Hybrid Retrieval ➜ GPT-4o Grounded Generation ➜ HIPAA Audit Trail**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Azure OpenAI](https://img.shields.io/badge/Azure_OpenAI-GPT--4o-0078D4?logo=microsoftazure&logoColor=white)](https://azure.microsoft.com/en-us/products/ai-services/openai-service)
[![Azure AI Search](https://img.shields.io/badge/Azure_AI_Search-Hybrid-0078D4?logo=microsoftazure&logoColor=white)](https://azure.microsoft.com/en-us/products/ai-services/ai-search)
[![Azure Text Analytics](https://img.shields.io/badge/Azure_Language-PHI_Detection-0078D4?logo=microsoftazure&logoColor=white)](https://azure.microsoft.com/en-us/products/ai-services/text-analytics)
[![Cosmos DB](https://img.shields.io/badge/Cosmos_DB-HIPAA_Audit-0078D4?logo=microsoftazure&logoColor=white)](https://azure.microsoft.com/en-us/products/cosmos-db)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An **enterprise-grade Retrieval-Augmented Generation system for healthcare professionals**. Clinicians ask natural-language questions about clinical guidelines; the system **detects and redacts PHI** (Protected Health Information) via Azure Text Analytics with regex fallback, applies **speciality-based RBAC filtering** (cardiologist sees cardiac guidelines, pharmacist sees formulary), retrieves relevant guideline chunks using **hybrid vector+keyword+semantic search**, generates **grounded answers with citations and mandatory medical disclaimers** via GPT-4o, and writes **every interaction to Cosmos DB** with 7-year HIPAA retention.

From **"Prompt to Production"** by Maneesh Kumar — Chapter 20, Project 5.

---

## Table of Contents

| # | Section | Description |
|---|---------|-------------|
| 1 | [Architecture](#architecture) | System design, RAG pipeline, RBAC model |
| 2 | [How It Works — Annotated Walkthrough](#how-it-works--annotated-walkthrough) | Step-by-step request flow with annotations |
| 3 | [Design Decisions](#design-decisions) | Why dual PHI detection, speciality RBAC, Cosmos audit |
| 4 | [Data Contracts](#data-contracts) | Every Pydantic model, search schema, audit record |
| 5 | [Features](#features) | Comprehensive feature matrix |
| 6 | [Prerequisites](#prerequisites) | Platform-specific setup (macOS / Windows / Linux) |
| 7 | [Quick Start](#quick-start) | Clone → install → index → run in 5 minutes |
| 8 | [Indexing Pipeline](#indexing-pipeline) | Offline guideline chunking, PHI scan, embedding |
| 9 | [Project Structure](#project-structure) | File tree with module responsibilities |
| 10 | [Configuration Reference](#configuration-reference) | Every environment variable explained |
| 11 | [API Reference](#api-reference) | Endpoints with request/response schemas |
| 12 | [RBAC & Authentication](#rbac--authentication) | Speciality access, JWT flow, mock clinicians |
| 13 | [PHI Detection](#phi-detection) | Azure Text Analytics + regex fallback |
| 14 | [Clinical Guidelines](#clinical-guidelines) | Included guideline documents |
| 15 | [Testing](#testing) | Unit tests, mocking strategy |
| 16 | [Deployment](#deployment) | Docker, Azure Container Apps |
| 17 | [Troubleshooting](#troubleshooting) | Common issues and solutions |
| 18 | [Azure Production Mapping](#azure-production-mapping) | Local → cloud service mapping |
| 19 | [Production Checklist](#production-checklist) | Go-live readiness assessment |

---

## Architecture

### System Overview

```
  ┌─────────────────────────────────────────────────────────────────────────────────┐
  │                        OFFLINE: GUIDELINE INDEXING PIPELINE                     │
  │                                                                                 │
  │   indexer/guidelines/                                                           │
  │   ├── antibiotic_prescribing.md    ┌──────────────┐   ┌──────────────────────┐ │
  │   ├── diabetes_management.md  ────►│ PHI Redaction │──►│ 800-char Chunking    │ │
  │   ├── hypertension_guidelines.md   │ (pre-index    │   │ (200-char overlap)   │ │
  │   └── mental_health_screening.md   │  safety scan) │   │ stride = 600 chars   │ │
  │                                    └──────────────┘   └─────────┬────────────┘ │
  │                                                                  │              │
  │                                                    ┌─────────────▼────────────┐ │
  │                                                    │  Azure OpenAI Embeddings │ │
  │                                                    │  text-embedding-3-large  │ │
  │                                                    │  (3072 dimensions)       │ │
  │                                                    └─────────────┬────────────┘ │
  │                                                                  │              │
  │                                                    ┌─────────────▼────────────┐ │
  │                                                    │  Azure AI Search Index   │ │
  │                                                    │  "clinical-guidelines"   │ │
  │                                                    │  ├─ title (searchable)   │ │
  │                                                    │  ├─ content (searchable) │ │
  │                                                    │  ├─ content_vector       │ │
  │                                                    │  │   (3072-dim HNSW)     │ │
  │                                                    │  ├─ category             │ │
  │                                                    │  │   (filterable — RBAC) │ │
  │                                                    │  └─ guideline_version    │ │
  │                                                    └──────────────────────────┘ │
  └─────────────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────────────────┐
  │                       RUNTIME: CLINICAL RAG QUERY PIPELINE                      │
  │                                                                                 │
  │   Clinician ─── POST /query ───► FastAPI (src/main.py)                         │
  │   {"question": "What is the first-line treatment for hypertension?"}           │
  │   Authorization: Bearer <JWT>                                                   │
  │                │                                                                │
  │                ▼                                                                │
  │   ┌──────────────────────────────────────────────────────────────────────────┐  │
  │   │  Step 1: AUTHENTICATE & AUTHORIZE                                       │  │
  │   │  validate_clinician() → ClinicianContext                                │  │
  │   │                                                                          │  │
  │   │  JWT: {"sub": "dr-002"}  →  ClinicianContext:                           │  │
  │   │                              clinician_id: "dr-002"                     │  │
  │   │                              name: "Dr Bob Jones"                       │  │
  │   │                              speciality: "cardiologist"                 │  │
  │   │                              department: "Cardiology"                   │  │
  │   │                              allowed_categories:                        │  │
  │   │                                ["cardiac","cardiology","general",       │  │
  │   │                                 "primary_care"]                         │  │
  │   └──────────────────────────────────┬───────────────────────────────────────┘  │
  │                                      │                                          │
  │   ┌──────────────────────────────────▼───────────────────────────────────────┐  │
  │   │  Step 2: PHI DETECTION & REDACTION                                      │  │
  │   │  PHIDetector.scan_query()                                               │  │
  │   │                                                                          │  │
  │   │  Input:  "Patient John Smith, SSN 123-45-6789, has hypertension"        │  │
  │   │  Output: "[NAME REDACTED], [SSN REDACTED], has hypertension"            │  │
  │   │  PHI detected: True                                                      │  │
  │   │                                                                          │  │
  │   │  ┌────────────────────────────────────────────────────────────────┐      │  │
  │   │  │  Primary: Azure Text Analytics PII Recognition                 │      │  │
  │   │  │  Fallback: 7 compiled regex patterns (SSN, NI, name, email,   │      │  │
  │   │  │           phone, patient ID, DOB)                              │      │  │
  │   │  └────────────────────────────────────────────────────────────────┘      │  │
  │   └──────────────────────────────────┬───────────────────────────────────────┘  │
  │                                      │                                          │
  │   ┌──────────────────────────────────▼───────────────────────────────────────┐  │
  │   │  Step 3: HYBRID RETRIEVAL with SPECIALITY RBAC                          │  │
  │   │  ClinicalRetriever.search()                                             │  │
  │   │                                                                          │  │
  │   │  1. Embed redacted query → text-embedding-3-large → 3072-dim vector    │  │
  │   │  2. RBAC OData filter:                                                   │  │
  │   │     "category eq 'cardiac' or category eq 'cardiology'                  │  │
  │   │      or category eq 'general' or category eq 'primary_care'"            │  │
  │   │  3. Hybrid search: vector KNN + BM25 keyword + semantic ranking         │  │
  │   │  4. Return top-5 ClinicalDocument results                               │  │
  │   └──────────────────────────────────┬───────────────────────────────────────┘  │
  │                                      │                                          │
  │   ┌──────────────────────────────────▼───────────────────────────────────────┐  │
  │   │  Step 4: GROUNDED CLINICAL GENERATION                                   │  │
  │   │  ClinicalGenerator.generate()                                           │  │
  │   │                                                                          │  │
  │   │  System Prompt:                                                          │  │
  │   │  "You are a clinical knowledge assistant for qualified healthcare        │  │
  │   │   professionals. Answer questions ONLY based on the provided clinical   │  │
  │   │   guidelines. Always cite the specific guideline and section.           │  │
  │   │   Flag when guidelines may be outdated. Never recommend specific        │  │
  │   │   dosages for individual patients — only reference guideline ranges."   │  │
  │   │                                                                          │  │
  │   │  → GPT-4o (temp=0.1, max_tokens=800)                                   │  │
  │   │  → Confidence: High/Medium/Low                                          │  │
  │   │  → Appends MANDATORY MEDICAL DISCLAIMER to every response               │  │
  │   └──────────────────────────────────┬───────────────────────────────────────┘  │
  │                                      │                                          │
  │   ┌──────────────────────────────────▼───────────────────────────────────────┐  │
  │   │  Step 5: HIPAA AUDIT LOGGING                                            │  │
  │   │  HIPAAAuditLogger.log() → Cosmos DB                                    │  │
  │   │                                                                          │  │
  │   │  HIPAA Audit Record:                                                     │  │
  │   │  {"clinician_id": "dr-002", "speciality": "cardiologist",              │  │
  │   │   "question_redacted": "[NAME REDACTED] has hypertension",             │  │
  │   │   "answer": "According to the Hypertension Guidelines..." (500 chars), │  │
  │   │   "sources": ["Hypertension Guidelines"],                              │  │
  │   │   "phi_detected": true, "confidence": "High",                         │  │
  │   │   "latency_ms": 2341.7,                                                │  │
  │   │   "_partitionKey": "dr-002", "ttl": 220752000}  ← 7-year retention    │  │
  │   └──────────────────────────────────┬───────────────────────────────────────┘  │
  │                                      │                                          │
  │                                      ▼                                          │
  │   Response: {"answer": "According to the Hypertension Guidelines...\n\n        │
  │              CLINICAL DISCLAIMER: This information is derived from clinical...",│
  │              "sources": ["Hypertension Guidelines"],                            │
  │              "confidence": "High", "phi_detected_in_query": true,              │
  │              "medical_disclaimer": "CLINICAL DISCLAIMER: ..."}                 │
  └─────────────────────────────────────────────────────────────────────────────────┘
```

### Speciality-Based RBAC Filtering

```
  ┌──────────────────────────────────────────────────────────────────────────┐
  │                 SPECIALITY → CATEGORY ACCESS MAP                        │
  │                                                                          │
  │  Speciality              Allowed Categories            OData Filter     │
  │  ──────────              ──────────────────            ────────────      │
  │  general_practitioner    general, primary_care,        category eq       │
  │                          preventive                    'general' or ...  │
  │                                                                          │
  │  cardiologist            cardiac, cardiology,          category eq       │
  │                          general, primary_care         'cardiac' or ...  │
  │                                                                          │
  │  psychiatrist            mental_health, psychiatry,    category eq       │
  │                          general                       'mental_health'.. │
  │                                                                          │
  │  pharmacist              formulary, prescribing,       category eq       │
  │                          pharmacy, general             'formulary' or .. │
  │                                                                          │
  │  physician               general, primary_care,        category eq       │
  │                          preventive, formulary         'general' or ...  │
  │                                                                          │
  │  nurse                   general, primary_care         category eq       │
  │                                                        'general' or ...  │
  │                                                                          │
  │  Filter is enforced SERVER-SIDE in Azure AI Search.                     │
  │  Clinicians cannot bypass it — unauthorized guidelines are NEVER        │
  │  returned from the search index, regardless of application logic.       │
  └──────────────────────────────────────────────────────────────────────────┘
```

---

## How It Works — Annotated Walkthrough

### Scenario 1: Cardiologist Asks About Hypertension Treatment

```
$ TOKEN=$(python -c "from src.auth import create_test_token; print(create_test_token('dr-002'))")

$ curl -s -X POST http://localhost:8000/query \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"question": "What is the first-line treatment for hypertension?"}' | python -m json.tool
```

```json
{
    "answer": "According to the Hypertension           // ← Grounded in retrieved guidelines
        Guidelines (NICE NG136), first-line            // ← Specific guideline citation
        treatment depends on age and ethnicity:        //
                                                       //
        **Step 1 — Under 55 / non-Black**:             // ← Evidence-based recommendations
        ACE inhibitor or ARB (e.g., ramipril,          //    from hypertension_guidelines.md
        losartan)                                      //
                                                       //
        **Step 1 — Over 55 or Black**:                 // ← Dual pathway per NICE
        Calcium channel blocker (e.g., amlodipine)     //
                                                       //
        **Target BP**: <140/90 mmHg (clinic),          // ← Monitoring targets
        <135/85 mmHg (ABPM/HBPM)                       //
                                                       //
        ⚠️ Always verify with current local            // ← Safety flagging
        formulary and check for contraindications.     //
                                                       //
        CLINICAL DISCLAIMER: This information is       // ← MANDATORY disclaimer
        derived from clinical guidelines and is        //    appended to EVERY response
        intended for qualified healthcare              //
        professionals only...",                         //
    "sources": [                                       // ← Retrieved guideline titles
        "Hypertension Guidelines"
    ],
    "confidence": "High",                              // ← ≥3 docs with score >0.8
    "medical_disclaimer": "CLINICAL DISCLAIMER: ...",
    "query_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "phi_detected_in_query": false                     // ← No PHI in this query
}
```

**What happened behind the scenes:**
1. JWT decoded → `dr-002` → cardiologist with `["cardiac", "cardiology", "general", "primary_care"]`
2. PHI scan: no PHI detected (clean clinical question)
3. Query embedded → 3072-dim vector
4. Azure AI Search hybrid query with RBAC filter: `category eq 'cardiac' or category eq 'cardiology' or category eq 'general' or category eq 'primary_care'`
5. Top-5 chunks from hypertension guidelines retrieved
6. GPT-4o (temp=0.1) generated grounded answer with NICE guideline citations
7. Medical disclaimer appended
8. HIPAA audit record → Cosmos DB (partitioned by `dr-002`, TTL=7 years)

### Scenario 2: Query Contains PHI

```
$ TOKEN_GP=$(python -c "from src.auth import create_test_token; print(create_test_token('dr-001'))")

$ curl -s -X POST http://localhost:8000/query \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_GP" \
    -d '{"question": "Patient John Smith, SSN 123-45-6789, has type 2 diabetes. What should I prescribe?"}' | python -m json.tool
```

```json
{
    "answer": "According to the Diabetes Management    // ← Answer based on redacted query
        Guidelines (NICE NG28), for a patient with     //    PHI was stripped before search
        Type 2 Diabetes:                               //
                                                       //
        **First-line**: Metformin 500mg once daily,    // ← Guideline dosage ranges (not
        titrate to 1g–2g daily as tolerated...         //    patient-specific dosing)
                                                       //
        CLINICAL DISCLAIMER: ...",
    "sources": ["Diabetes Management"],
    "confidence": "High",
    "medical_disclaimer": "CLINICAL DISCLAIMER: ...",
    "query_id": "...",
    "phi_detected_in_query": true                      // ← PHI WAS detected and redacted
}
```

**PHI redaction in action:**
- Input: `"Patient John Smith, SSN 123-45-6789, has type 2 diabetes..."`
- Redacted: `"Patient [NAME REDACTED], [SSN REDACTED], has type 2 diabetes..."`
- The redacted text is what gets sent to Azure AI Search and GPT-4o
- The audit record in Cosmos DB stores the **redacted** question, never the original PHI

### Scenario 3: Pharmacist Restricted by RBAC

```
$ TOKEN_PH=$(python -c "from src.auth import create_test_token; print(create_test_token('ph-001'))")

$ curl -s -X POST http://localhost:8000/query \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN_PH" \
    -d '{"question": "What is the mental health screening protocol?"}' | python -m json.tool
```

```json
{
    "answer": "Based on the available guidelines,      // ← Limited results because
        I was unable to find specific mental health     //    pharmacist RBAC filter excludes
        screening protocols within your authorized      //    mental_health category
        guideline categories...",
    "sources": [],
    "confidence": "Low",                               // ← No relevant docs found
    "medical_disclaimer": "CLINICAL DISCLAIMER: ...",
    "query_id": "...",
    "phi_detected_in_query": false
}
```

**Key insight**: The pharmacist's `allowed_categories` are `["formulary", "prescribing", "pharmacy", "general"]`. The mental health screening guidelines are categorized as `mental_health` — the Azure AI Search OData filter **excluded them server-side**.

### Scenario 4: Demo Script

```
$ python demo_e2e.py
```

```
=== Healthcare Clinical RAG — End-to-End Demo ===

Test 1: PHI Detection (local regex)
  ✅ Clean query: "What is the dosage for metformin?" → No PHI
  ✅ Clean query: "NICE guidelines for hypertension" → No PHI
  ✅ PHI detected: SSN 123-45-6789 → [SSN REDACTED]
  ✅ PHI detected: john.doe@nhs.net → [EMAIL REDACTED]

Test 2: Speciality RBAC Access Map
  general_practitioner → ['general', 'primary_care', 'preventive']
  cardiologist → ['cardiac', 'cardiology', 'general', 'primary_care']
  psychiatrist → ['mental_health', 'psychiatry', 'general']
  pharmacist → ['formulary', 'prescribing', 'pharmacy', 'general']

Test 3: Clinical Guidelines
  ✅ antibiotic_prescribing.md (4.2 KB)
  ✅ diabetes_management.md (3.8 KB)
  ✅ hypertension_guidelines.md (3.7 KB)
  ✅ mental_health_screening.md (5.1 KB)

Test 4: JWT Authentication
  ✅ Token created for dr-002
  ✅ Validated: Dr Bob Jones, cardiologist

Test 5: HIPAA Audit Logger → importable

Test 6: Clinical Generator → importable

=== All local component tests passed ===
```

---

## Design Decisions

### Why Dual PHI Detection (Azure Text Analytics + Local Regex)?

| Detection Method | Strengths | Weaknesses | When Used |
|-----------------|-----------|------------|-----------|
| **Azure Text Analytics PII** | ML-based, handles complex patterns, multi-language, entity categorization | Requires Azure connectivity, API cost, latency | Primary — when Azure Language service is available |
| **Local regex fallback** | Zero latency, zero cost, works offline | Limited patterns, no context awareness, false positives on names | Fallback — when Azure service is unavailable |
| **None** | — | PHI leaks to search index and LLM, HIPAA violation | ❌ Never acceptable |

**Architecture choice**: PHI detection runs **before** any external API call (search, LLM). Even if the query contains a patient's SSN, that SSN is redacted before it ever reaches Azure AI Search or GPT-4o.

### Why Speciality-Based RBAC (Not Role-Based Clearance Levels)?

| Approach | Model | Pros | Cons |
|----------|-------|------|------|
| **No access control** | Everyone sees everything | Simple | ❌ Clinical governance violation |
| **Clearance levels (1-2-3)** | Hierarchical | Simple to implement | Doesn't match medical domain — a pharmacist isn't "less" than a cardiologist, they have *different* scopes |
| **Speciality → category mapping** | Each speciality maps to relevant guideline categories | Matches clinical workflow; cardiologist sees cardiac, psychiatrist sees mental health | More complex mapping table |

**Selected: Speciality-based** because clinical access isn't hierarchical — it's **domain-scoped**. A nurse and a cardiologist don't differ by "level"; they need access to *different categories* of guidelines.

### Why Temperature 0.1 (Not 0.0 or 0.7)?

| Temperature | Behavior | Use Case |
|:-----------:|----------|----------|
| 0.0 | Fully deterministic, repetitive | Exact extraction tasks |
| **0.1 (selected)** | Near-deterministic with slight variation | Clinical Q&A — factual but not robotic |
| 0.3 | Moderate variation | General Q&A |
| 0.7+ | Creative, diverse | Creative writing (never for clinical) |

**Key insight**: Clinical information must be **factual and reproducible**. Temperature 0.1 prevents hallucination while allowing natural language variation in phrasing.

### Why 800-char Chunks (Not 1000 or 500)?

| Chunk Size | Context Quality | Index Size | Retrieval Precision |
|:----------:|:--------------:|:----------:|:-------------------:|
| 500 chars | Fragmented — splits mid-protocol | Large (many chunks) | ✅ High precision |
| **800 chars** | Balanced — captures complete clinical sections | Moderate | ✅ Good precision |
| 1000 chars | Complete sections but may mix topics | Small (fewer chunks) | ❌ Lower precision |

Clinical guidelines have structured sections (dosing protocols, criteria lists). 800 chars typically captures a complete subsection without mixing unrelated content.

---

## Data Contracts

### Pydantic Models

```python
class ClinicalQuery(BaseModel):
    """API input — what the clinician submits."""
    question: str = Field(..., min_length=5)                    # Clinical question
    session_id: Optional[str] = Field(default_factory=uuid4)    # Session tracking

class ClinicalDocument(BaseModel):
    """Retrieved guideline chunk from Azure AI Search."""
    title: str                          # e.g., "Hypertension Guidelines"
    content_snippet: str                # First 400 chars of chunk
    relevance_score: float              # Azure AI Search score
    guideline_version: Optional[str]    # e.g., "2024"

class ClinicalResponse(BaseModel):
    """API output — grounded clinical answer with disclaimer."""
    answer: str                         # GPT-4o generated answer + disclaimer
    sources: List[str]                  # Guideline titles cited
    confidence: str                     # "High" | "Medium" | "Low"
    medical_disclaimer: str             # Mandatory clinical disclaimer
    query_id: str                       # Unique query identifier
    phi_detected_in_query: bool         # Whether PHI was found in input

class ClinicianContext(BaseModel):
    """Authenticated clinician identity and speciality permissions."""
    clinician_id: str                   # e.g., "dr-002"
    name: str                           # e.g., "Dr Bob Jones"
    speciality: str                     # e.g., "cardiologist"
    department: str                     # e.g., "Cardiology"
    allowed_categories: List[str]       # ["cardiac", "cardiology", "general", ...]

class HIPAAAuditRecord(BaseModel):
    """Immutable HIPAA compliance record written to Cosmos DB."""
    id: str                             # UUID
    timestamp: datetime                 # UTC ISO format
    clinician_id: str                   # Who queried
    speciality: str                     # What speciality
    question_redacted: str              # PHI-redacted query text (NEVER original)
    answer: str                         # Generated answer (truncated to 500 chars)
    sources: List[str]                  # Cited guideline titles
    phi_detected: bool                  # Whether PHI was detected
    confidence: str                     # Answer confidence level
    latency_ms: float                   # End-to-end latency
```

### Azure AI Search Index Schema

```python
# Index: "clinical-guidelines" (created by indexer/index_guidelines.py)
search_document = {
    "id": str,                          # UUID
    "title": str,                       # Guideline document title
    "content": str,                     # Chunk text (800 chars max)
    "category": str,                    # e.g., "general", "cardiac", "mental_health"
    "guideline_version": str,           # "2024"
    "content_vector": List[float],      # 3072-dim embedding (HNSW index)
}

# Cosmos DB HIPAA audit document (written by HIPAAAuditLogger)
cosmos_document = {
    **hipaa_audit_record_fields,        # All HIPAAAuditRecord fields
    "_partitionKey": str,               # clinician_id for partitioning
    "ttl": 220752000,                   # 7 years in seconds (HIPAA requirement)
}
```

### Confidence Scoring Logic

```python
# ClinicalGenerator._confidence()
if no_docs_retrieved:
    confidence = "Low"
elif docs_with_score_above_0_8 >= 3:
    confidence = "High"
elif docs_retrieved >= 1:
    confidence = "Medium"
else:
    confidence = "Low"
```

---

## Features

| # | Feature | Description | Module |
|---|---------|-------------|--------|
| 1 | **Dual PHI Detection** | Azure Text Analytics PII + 7 regex fallback patterns | `src/phi_detection.py` |
| 2 | **SSN/NI Redaction** | US Social Security and UK National Insurance detection | `PHIDetector` |
| 3 | **Email/Phone Redaction** | Email and phone number pattern matching | `PHIDetector` |
| 4 | **Patient ID Redaction** | Patient ID and DOB pattern detection | `PHIDetector` |
| 5 | **Name Redaction** | Capitalized two-word name pattern detection | `PHIDetector` |
| 6 | **Graceful PHI Fallback** | Azure → regex fallback without service interruption | `PHIDetector` |
| 7 | **Speciality-Based RBAC** | 6 specialities mapped to guideline category access | `src/auth.py` |
| 8 | **Server-Side RBAC Filter** | OData filter on Azure AI Search prevents unauthorized access | `ClinicalRetriever` |
| 9 | **Hybrid Vector+Keyword Search** | Semantic similarity + BM25 keyword matching | `src/retriever.py` |
| 10 | **Semantic Ranking** | Azure AI Search transformer-based reranking | `ClinicalRetriever` |
| 11 | **3072-dim Embeddings** | `text-embedding-3-large` for clinical text fidelity | `ClinicalRetriever` |
| 12 | **Grounded Clinical Generation** | GPT-4o answers strictly from retrieved guidelines | `src/generator.py` |
| 13 | **Guideline Citations** | Every answer references specific guideline and section | `ClinicalGenerator` |
| 14 | **Anti-Hallucination Prompt** | "Never recommend specific dosages for individuals" | `ClinicalGenerator` |
| 15 | **Mandatory Medical Disclaimer** | Appended to every single response | `ClinicalGenerator` |
| 16 | **Outdated Guideline Flagging** | System prompt instructs flagging when guidelines may be stale | `ClinicalGenerator` |
| 17 | **Confidence Scoring** | High/Medium/Low based on retrieval quality | `ClinicalGenerator` |
| 18 | **Temperature 0.1** | Near-deterministic for factual clinical accuracy | `ClinicalGenerator` |
| 19 | **JWT Authentication** | HS256 JWT token validation with clinician lookup | `src/auth.py` |
| 20 | **4 Mock Clinicians** | GP, cardiologist, psychiatrist, pharmacist for dev | `src/auth.py` |
| 21 | **Dev Mode Fallback** | No auth header → GP dev clinician (with warning log) | `src/auth.py` |
| 22 | **HIPAA Audit Trail** | Immutable audit records for every query | `src/audit.py` |
| 23 | **7-Year HIPAA Retention** | TTL-based automatic deletion after 7 years | `HIPAAAuditLogger` |
| 24 | **Clinician-Partitioned Audit** | `_partitionKey = clinician_id` for efficient queries | `HIPAAAuditLogger` |
| 25 | **Answer Truncation in Audit** | Answers truncated to 500 chars in audit records | `src/main.py` |
| 26 | **Non-Blocking Audit** | Audit failures logged but don't crash query pipeline | `HIPAAAuditLogger` |
| 27 | **Latency Tracking** | Millisecond-precision timing for every query | `src/main.py` |
| 28 | **Pre-Index PHI Scan** | Guidelines are PHI-redacted before indexing | `indexer/index_guidelines.py` |
| 29 | **800-char Clinical Chunking** | 800-char chunks with 200-char overlap (stride 600) | `indexer/index_guidelines.py` |
| 30 | **Category Auto-Detection** | Category extracted from filename stem | `indexer/index_guidelines.py` |
| 31 | **4 Clinical Guidelines** | Antibiotics, diabetes, hypertension, mental health | `indexer/guidelines/` |
| 32 | **Pydantic Validation** | Input validation with min_length constraints | `src/models.py` |
| 33 | **Pydantic Settings** | Environment-based config with `.env` support | `src/config.py` |
| 34 | **LRU-Cached Settings** | Singleton settings via `@lru_cache` | `src/config.py` |
| 35 | **Structured JSON Logging** | structlog with ISO timestamps and JSON output | `src/main.py` |
| 36 | **FastAPI Lifespan** | Async context manager for component initialization | `src/main.py` |
| 37 | **Health Endpoint** | `GET /health` with service name and version | `src/main.py` |
| 38 | **Docker Support** | Python 3.11 slim container image | `infra/Dockerfile` |
| 39 | **Azure Deploy Script** | ACR + Container Apps with auto-scaling | `infra/azure-deploy.sh` |
| 40 | **OpenAI Retry Logic** | `max_retries=3` on AsyncAzureOpenAI client | `ClinicalGenerator` |
| 41 | **Graceful Generation Fallback** | Failure → "Consult your clinical colleagues" | `ClinicalGenerator` |
| 42 | **Embedding Failure Graceful** | Embed failure → empty vector → keyword-only search | `ClinicalRetriever` |

---

## Prerequisites

<details>
<summary><strong>macOS</strong></summary>

```bash
# Python 3.11+
brew install python@3.11

# Verify
python3 --version    # Python 3.11.x

# Optional: Azure CLI (for deployment)
brew install azure-cli

# Optional: Docker (for containerized deployment)
brew install --cask docker
```
</details>

<details>
<summary><strong>Windows</strong></summary>

```powershell
# Python 3.11+ from python.org or winget
winget install Python.Python.3.11

# Verify
python --version    # Python 3.11.x

# Optional: Azure CLI
winget install Microsoft.AzureCLI

# Optional: Docker Desktop
winget install Docker.DockerDesktop
```
</details>

<details>
<summary><strong>Linux (Ubuntu/Debian)</strong></summary>

```bash
# Python 3.11+
sudo apt update && sudo apt install python3.11 python3.11-venv python3-pip

# Verify
python3.11 --version    # Python 3.11.x

# Optional: Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Optional: Docker
sudo apt install docker.io docker-compose
```
</details>

### Azure Services Required

| Service | Purpose | Required for Local Dev? |
|---------|---------|------------------------|
| Azure OpenAI (GPT-4o) | Clinical answer generation | ✅ Yes (for /query) |
| Azure OpenAI (text-embedding-3-large) | Vector embeddings | ✅ Yes (for indexing + search) |
| Azure AI Search | Hybrid guideline retrieval | ✅ Yes (for /query) |
| Azure AI Language (Text Analytics) | PHI/PII detection | ❌ No (regex fallback) |
| Azure Cosmos DB | HIPAA audit logging | ❌ No (logs warning on failure) |
| Azure Container Apps | Production hosting | ❌ No (FastAPI local) |

---

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/maneeshkumar52/healthcare-clinical-rag.git
cd healthcare-clinical-rag

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate    # macOS/Linux
# .venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your Azure credentials:

```bash
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_API_KEY=your-search-key
AZURE_LANGUAGE_ENDPOINT=https://your-language.cognitiveservices.azure.com/
AZURE_LANGUAGE_KEY=your-language-key
JWT_SECRET=change-me-in-production
```

### 3. Index Clinical Guidelines

```bash
python -m indexer.index_guidelines
```

Expected output:
```
Index 'clinical-guidelines' created/updated.
Indexed 35 chunks from 4 guideline documents.
```

### 4. Run the Server

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Query Clinical Guidelines

```bash
# Create a test token for a GP
TOKEN=$(python -c "from src.auth import create_test_token; print(create_test_token('dr-001'))")

# Ask a clinical question
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"question": "What are the first-line antibiotics for UTI?"}'
```

### 6. Run the Demo Script

```bash
python demo_e2e.py
```

---

## Indexing Pipeline

### How Guidelines Are Indexed

```
  indexer/guidelines/*.md
         │
         ▼
  ┌──────────────────┐
  │ PHI Redaction     │     Ensures no patient data
  │ (pre-index scan)  │     leaks into search index
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │ Category Extract  │     From filename stem:
  │                    │     "antibiotic_prescribing.md"
  │                    │     → category: "antibiotic"
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │ Text Chunking     │     Parameters:
  │                    │     • chunk_size: 800 chars
  │                    │     • chunk_overlap: 200 chars
  │                    │     • stride: 600 chars
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │ AzureOpenAI      │     text-embedding-3-large
  │ Embeddings       │     → 3072-dimensional vectors
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │ Azure AI Search  │     Index: "clinical-guidelines"
  │ Upload           │     HNSW vector config + semantic config
  │                  │     guideline_version: "2024"
  └──────────────────┘
```

### Azure AI Search Index Schema

| Field | Type | Searchable | Filterable | Vector |
|-------|------|:----------:|:----------:|:------:|
| `id` | String (key) | ❌ | ❌ | ❌ |
| `title` | String | ✅ | ❌ | ❌ |
| `content` | String | ✅ | ❌ | ❌ |
| `category` | String | ❌ | ✅ | ❌ |
| `guideline_version` | String | ❌ | ❌ | ❌ |
| `content_vector` | Collection(Single) | ✅ | ❌ | ✅ (3072-dim HNSW) |

---

## Project Structure

```
healthcare-clinical-rag/
├── demo_e2e.py                          # End-to-end demo (PHI, RBAC, JWT)
├── requirements.txt                     # Python dependencies (15 packages)
├── .env.example                         # Environment variable template
├── src/                                 # Core application
│   ├── __init__.py
│   ├── config.py                        # Pydantic Settings — 16 env vars
│   ├── models.py                        # 5 Pydantic models + 1 Settings
│   ├── phi_detection.py                 # PHI detector (Azure + regex fallback)
│   ├── retriever.py                     # Hybrid clinical retriever with RBAC
│   ├── generator.py                     # GPT-4o clinical response generator
│   ├── auth.py                          # JWT validation + speciality RBAC
│   ├── audit.py                         # HIPAA Cosmos DB audit logger
│   └── main.py                          # FastAPI app, endpoints, pipeline
├── indexer/                             # Offline guideline processing
│   ├── index_guidelines.py              # PHI-scan + chunk + embed + upload
│   └── guidelines/                      # Clinical guideline source documents
│       ├── antibiotic_prescribing.md    # NICE antimicrobial guidelines
│       ├── diabetes_management.md       # NICE NG28 / ADA diabetes
│       ├── hypertension_guidelines.md   # NICE NG136 hypertension
│       └── mental_health_screening.md   # PHQ-9, GAD-7, AUDIT-C
├── tests/                               # Test suite
│   ├── __init__.py
│   ├── test_phi_detection.py            # 5 PHI detection tests
│   └── test_retriever.py               # 5 retriever + auth tests
└── infra/                               # Deployment
    ├── Dockerfile                       # Python 3.11 slim image
    └── azure-deploy.sh                  # ACR + Container Apps script
```

### Module Responsibility Matrix

| Module | Responsibility | Dependencies | Lines |
|--------|---------------|-------------|:-----:|
| `src/main.py` | FastAPI app, `/query` pipeline, structured logging | All src modules | 110 |
| `src/config.py` | Environment config via Pydantic Settings | `pydantic_settings` | 31 |
| `src/models.py` | 5 Pydantic models — all data contracts | `pydantic` | 46 |
| `src/phi_detection.py` | Dual PHI detection (Azure Text Analytics + regex) | `azure-ai-textanalytics` | 97 |
| `src/retriever.py` | Hybrid vector+keyword search with RBAC filter | `openai`, `azure-search` | 85 |
| `src/generator.py` | GPT-4o clinical generation with disclaimer | `openai`, `models` | 78 |
| `src/auth.py` | JWT decode, speciality→category mapping | `python-jose` | 83 |
| `src/audit.py` | HIPAA Cosmos DB audit logging (7-year TTL) | `azure-cosmos` | 31 |
| `indexer/index_guidelines.py` | PHI-scan, chunk, embed, upload guidelines | `openai`, `azure-search` | 119 |
| `demo_e2e.py` | End-to-end local demo of all components | `src/*`, `indexer/*` | 62 |

---

## Configuration Reference

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `AZURE_OPENAI_ENDPOINT` | `https://your-openai.openai.azure.com/` | ✅ | Azure OpenAI service endpoint |
| `AZURE_OPENAI_API_KEY` | `your-key` | ✅ | Azure OpenAI API key |
| `AZURE_OPENAI_API_VERSION` | `2024-02-01` | ❌ | OpenAI API version |
| `AZURE_OPENAI_DEPLOYMENT` | `gpt-4o` | ❌ | Chat completion model deployment |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | `text-embedding-3-large` | ❌ | Embedding model deployment |
| `AZURE_SEARCH_ENDPOINT` | `https://your-search.search.windows.net` | ✅ | Azure AI Search endpoint |
| `AZURE_SEARCH_API_KEY` | `your-search-key` | ✅ | Azure AI Search admin key |
| `AZURE_SEARCH_INDEX_NAME` | `clinical-guidelines` | ❌ | Search index name |
| `AZURE_LANGUAGE_ENDPOINT` | `https://your-language.cognitiveservices.azure.com/` | ❌ | Azure Language endpoint (PHI) |
| `AZURE_LANGUAGE_KEY` | `your-language-key` | ❌ | Azure Language API key |
| `COSMOS_ENDPOINT` | `https://your-cosmos.documents.azure.com:443/` | ❌ | Cosmos DB endpoint |
| `COSMOS_KEY` | `your-cosmos-key` | ❌ | Cosmos DB key |
| `COSMOS_DATABASE` | `clinical-rag` | ❌ | Cosmos DB database name |
| `COSMOS_AUDIT_CONTAINER` | `hipaa-audit` | ❌ | Cosmos DB audit container name |
| `JWT_SECRET` | `dev-secret-change-in-production` | ✅ Prod | JWT signing secret |
| `LOG_LEVEL` | `INFO` | ❌ | Logging level |

---

## API Reference

### `GET /health`

Health check endpoint for container orchestrators.

**Response** `200 OK`:
```json
{"status": "healthy", "service": "healthcare-clinical-rag", "version": "1.0.0"}
```

### `POST /query`

Submit a clinical guideline question. Requires JWT Bearer token (optional in dev mode).

**Headers**:
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

**Request Body**:
```json
{
    "question": "What are the first-line antibiotics for UTI?",  // Required, min 5 chars
    "session_id": "optional-session-uuid"                         // Optional, auto-generated
}
```

**Response** `200 OK`:
```json
{
    "answer": "According to the Antibiotic Prescribing Guidelines...\n\nCLINICAL DISCLAIMER: ...",
    "sources": ["Antibiotic Prescribing Guidelines"],
    "confidence": "High",
    "medical_disclaimer": "CLINICAL DISCLAIMER: This information is derived from clinical guidelines...",
    "query_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "phi_detected_in_query": false
}
```

**Error Responses**:
| Code | Cause |
|------|-------|
| `401` | Invalid or expired JWT token |
| `422` | Question shorter than 5 characters |
| `500` | Internal processing error |

---

## RBAC & Authentication

### Speciality Access Map

| Speciality | Allowed Categories | Example Guidelines Accessible |
|------------|-------------------|------------------------------|
| `general_practitioner` | general, primary_care, preventive | Diabetes, Hypertension, general protocols |
| `cardiologist` | cardiac, cardiology, general, primary_care | Cardiac guidelines + general |
| `psychiatrist` | mental_health, psychiatry, general | Mental Health Screening + general |
| `pharmacist` | formulary, prescribing, pharmacy, general | Antibiotic Prescribing + general |
| `physician` | general, primary_care, preventive, formulary | Broad access |
| `nurse` | general, primary_care | General protocols only |

### JWT Token Flow

```
  1. Clinician receives JWT:
     {"sub": "dr-002"}
     Signed with HS256 + JWT_SECRET

  2. Clinician sends:
     Authorization: Bearer eyJhbGciOiJIUzI1NiI...

  3. validate_clinician() decodes:
     ├─ Verify HS256 signature
     ├─ Extract sub → clinician_id
     ├─ Lookup in MOCK_CLINICIANS (if exists)
     ├─ Map speciality → SPECIALITY_ACCESS
     └─ Return ClinicianContext with allowed_categories

  4. ClinicianContext used for:
     ├─ RBAC OData filter on Azure AI Search
     ├─ HIPAA audit record: clinician_id, speciality
     └─ Logging: clinician identification
```

### Mock Clinicians (Development)

| ID | Name | Speciality | Department |
|----|------|-----------|------------|
| `dr-001` | Dr Alice Smith | general_practitioner | Primary Care |
| `dr-002` | Dr Bob Jones | cardiologist | Cardiology |
| `dr-003` | Dr Carol Lee | psychiatrist | Mental Health |
| `ph-001` | Pharmacist Dave Brown | pharmacist | Pharmacy |

### Creating Test Tokens

```python
from src.auth import create_test_token

# GP token
token = create_test_token("dr-001")

# Cardiologist token
token = create_test_token("dr-002")

# Psychiatrist token
token = create_test_token("dr-003")

# Pharmacist token
token = create_test_token("ph-001")
```

---

## PHI Detection

### Detection Pipeline

```
  Query Input
       │
       ▼
  ┌──────────────────────────┐
  │ Try Azure Text Analytics │
  │ recognize_pii_entities() │
  │                          │
  │ Categories scanned:      │
  │ Person, PhoneNumber,     │
  │ Email, Address,          │
  │ USSocialSecurityNumber,  │
  │ UKNationalInsurance,     │
  │ MedicalLicense,          │
  │ PatientID, Age, Date     │
  └──────────┬───────────────┘
             │
    Azure available?
    ┌────────┴────────┐
    │ YES             │ NO (fallback)
    ▼                 ▼
  Azure PII      ┌──────────────────────┐
  redacted_text  │ Local Regex Patterns  │
                 │                        │
                 │ 1. SSN: \d{3}-\d{2}-\d{4}     → [SSN REDACTED]      │
                 │ 2. NI: NI [A-Z]{2}\d{6}[A-Z]  → [NI REDACTED]      │
                 │ 3. Name: [A-Z][a-z]+ [A-Z]... → [NAME REDACTED]    │
                 │ 4. Email: [\w.-]+@[\w.-]+      → [EMAIL REDACTED]   │
                 │ 5. Phone: (?:\+44|0)\d{10}     → [PHONE REDACTED]   │
                 │ 6. Patient ID: Patient ID:...  → [PATIENT_ID ...]   │
                 │ 7. DOB: DOB:\d{1,2}/\d{1,2}/.. → [DOB REDACTED]    │
                 └──────────────────────┘
             │
             ▼
  (redacted_text, phi_detected: bool)
```

### PHI Detection Test Examples

| Input | PHI Detected | Redacted Output |
|-------|:------------:|----------------|
| `"What is the dosage for metformin?"` | ❌ No | Unchanged |
| `"Patient John Smith has diabetes"` | ✅ Yes | `"Patient [NAME REDACTED] has diabetes"` |
| `"SSN 123-45-6789 needs referral"` | ✅ Yes | `"[SSN REDACTED] needs referral"` |
| `"Contact john.doe@nhs.net"` | ✅ Yes | `"Contact [EMAIL REDACTED]"` |
| `"Ramipril 5mg, NICE NG136"` | ❌ No | Unchanged (drug names are NOT PHI) |

---

## Clinical Guidelines

### Included Guidelines (4 documents, 703 lines)

| Document | Lines | Source | Key Topics |
|----------|:-----:|--------|------------|
| `antibiotic_prescribing.md` | 177 | NICE / PHE START SMART | UTI treatment, URTI (FeverPAIN/Centor), CAP (CURB-65), skin/soft tissue, allergy documentation |
| `diabetes_management.md` | 160 | NICE NG28 / ADA | Diagnosis criteria (HbA1c, FPG), Metformin first-line, SGLT2i, GLP-1 RA, monitoring, sick day rules |
| `hypertension_guidelines.md` | 159 | NICE NG136 | Step-wise treatment, ACE/ARB vs CCB by age/ethnicity, BP targets, resistant hypertension |
| `mental_health_screening.md` | 207 | NICE / WHO | PHQ-9, GAD-7, AUDIT-C scoring, risk assessment, referral criteria, safeguarding |

---

## Testing

### Run Tests

```bash
pytest tests/ -v
```

### Test Coverage

| Test File | Tests | What It Verifies |
|-----------|:-----:|-----------------|
| `test_phi_detection.py` | 5 | Clean queries unchanged, SSN/email/patient ID redacted, clinical drug names preserved |
| `test_retriever.py` | 5 | Retriever initialization, embedding failure graceful handling, JWT validation for GP/cardiologist/pharmacist |

### Mocking Strategy

```python
# External services are mocked at the boundary:
# PHI detection: _client = None forces local regex fallback
detector._client = None  # Skip Azure Text Analytics

# Retriever: AsyncMock for Azure OpenAI + SearchClient
with patch("src.retriever.AsyncAzureOpenAI"),
     patch("src.retriever.SearchClient"):

# All 10 tests run offline without Azure connectivity
```

---

## Deployment

### Docker

```bash
cd infra
docker build -t healthcare-clinical-rag .
docker run -p 8000:8000 --env-file ../.env healthcare-clinical-rag
```

### Azure Container Apps

```bash
chmod +x infra/azure-deploy.sh
./infra/azure-deploy.sh
```

The script:
1. Creates resource group `rg-clinical-rag` in `uksouth`
2. Creates Azure Container Registry (Basic SKU, admin enabled)
3. Builds and pushes Docker image via `az acr build`
4. Creates Container Apps environment
5. Deploys with external ingress, port 8000, 1-5 replicas auto-scaling
6. Configures secrets: OpenAI, Search, Cosmos, JWT credentials

---

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| `401 Invalid or expired token` | JWT signature mismatch | Ensure `JWT_SECRET` matches between token creation and validation |
| `422 Unprocessable Entity` | Question < 5 characters | Provide at least 5 characters in question |
| Empty sources in response | Azure AI Search not indexed | Run `python -m indexer.index_guidelines` first |
| "Consult your clinical colleagues" fallback | Azure OpenAI API failure | Check `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_API_KEY` |
| Confidence always "Low" | No relevant guidelines found | Re-index guidelines, verify category matches speciality |
| `phi_detection_azure_failed` in logs | Azure Language not configured | Expected — system falls back to regex (non-blocking) |
| `audit_write_failed` in logs | Cosmos DB not configured | Set `COSMOS_ENDPOINT` and `COSMOS_KEY` (non-blocking) |
| Pharmacist can't see mental health docs | RBAC working correctly | Pharmacist access: `formulary`, `prescribing`, `pharmacy`, `general` only |
| `embedding_failed` in logs | Wrong embedding deployment | Verify `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` matches Azure portal |
| PHI false positive on drug names | Regex name pattern too broad | Expected — regex fallback may flag capitalized drug names; Azure primary detection is more accurate |
| `no_auth_header_dev_mode` warning | No Authorization header | Expected in dev; use JWT in production |

---

## Azure Production Mapping

| Local Component | Azure Production Service | Purpose |
|----------------|-------------------------|---------|
| `uvicorn src.main:app` | Azure Container Apps | Serverless container hosting (1-5 replicas) |
| `AsyncAzureOpenAI` (chat) | Azure OpenAI Service (GPT-4o) | Clinical answer generation |
| `AsyncAzureOpenAI` (embed) | Azure OpenAI (text-embedding-3-large) | 3072-dim vector embeddings |
| `SearchClient` | Azure AI Search (semantic) | Hybrid retrieval + RBAC filtering |
| `TextAnalyticsClient` | Azure AI Language | PHI/PII entity detection |
| `CosmosClient` | Azure Cosmos DB (NoSQL) | HIPAA audit trail (7-year TTL) |
| `JWT_SECRET` env var | Azure Key Vault | Secrets management |
| `structlog` JSON output | Application Insights + Log Analytics | Observability |
| `Dockerfile` | Azure Container Registry | Image storage |
| `azure-deploy.sh` | Azure CLI | Infrastructure provisioning |
| — | Azure Monitor Alerts | SLA monitoring |
| — | Azure AD (Entra ID) | Production JWT issuer (replaces mock clinicians) |

---

## Production Checklist

### Security & HIPAA Compliance

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | Replace `JWT_SECRET` with Key Vault reference | ⬜ | `@Microsoft.KeyVault(SecretUri=...)` |
| 2 | Replace API keys with Managed Identity | ⬜ | `DefaultAzureCredential` for all Azure services |
| 3 | Remove `allow_origins=["*"]` CORS | ⬜ | Restrict to known clinical frontends |
| 4 | Replace mock clinicians with Azure AD/Entra ID | ⬜ | Real JWT issuer with clinical credentials |
| 5 | Enable Azure Text Analytics for production PHI | ⬜ | Don't rely on regex in production |
| 6 | Encrypt data at rest (Cosmos DB + AI Search) | ⬜ | Customer-managed keys for HIPAA |
| 7 | Enable VNet integration for all Azure services | ⬜ | No public endpoints for PHI data |
| 8 | Add rate limiting on `/query` | ⬜ | Azure API Management or WAF |
| 9 | Add prompt injection detection | ⬜ | Input sanitization before LLM |
| 10 | Validate original PHI is never stored | ⬜ | Only redacted queries in Cosmos DB |

### Reliability

| # | Item | Status | Notes |
|---|------|--------|-------|
| 11 | Add circuit breaker for Azure OpenAI | ⬜ | `tenacity` with exponential backoff |
| 12 | Set embedding timeout | ⬜ | 30s timeout for embeddings |
| 13 | Health checks for Azure AI Search on startup | ⬜ | Verify index exists |
| 14 | Retry Cosmos DB audit writes | ⬜ | Currently fire-and-forget |
| 15 | Container Apps auto-scaling: 1-5 replicas | ✅ | Set in `azure-deploy.sh` |

### Observability

| # | Item | Status | Notes |
|---|------|--------|-------|
| 16 | Dashboard: query volume, latency, confidence | ⬜ | Azure Monitor Workbook |
| 17 | Alert: PHI detection rate spikes | ⬜ | May indicate data entry issues |
| 18 | Alert: confidence "Low" rate > 30% | ⬜ | Indicates retrieval quality issues |
| 19 | Alert: latency P95 > 5s | ⬜ | OpenAI or Search degradation |
| 20 | HIPAA audit log review scheduled | ⬜ | Quarterly compliance review |

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| **Runtime** | Python | 3.11+ |
| **Web Framework** | FastAPI | 0.111.0 |
| **ASGI Server** | Uvicorn | 0.30.0 |
| **LLM** | Azure OpenAI (GPT-4o) | API 2024-02-01 |
| **Embeddings** | Azure OpenAI (text-embedding-3-large) | 3072 dims |
| **Search** | Azure AI Search | 11.4.0 |
| **PHI Detection** | Azure AI Language (Text Analytics) | 5.3.0 |
| **Audit Store** | Azure Cosmos DB | 4.7.0 |
| **Identity** | Azure Identity | 1.16.0 |
| **Auth** | python-jose (JWT) | 3.3.0 |
| **Validation** | Pydantic | 2.7.0 |
| **Configuration** | pydantic-settings | 2.3.0 |
| **Logging** | structlog | 24.2.0 |
| **HTTP Client** | httpx | 0.27.0 |
| **Testing** | pytest + pytest-asyncio | 8.2.0 / 0.23.0 |
| **Container** | Docker (Python 3.11 slim) | — |
| **Hosting** | Azure Container Apps | — |

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built by [Maneesh Kumar](https://github.com/maneeshkumar52)**

*Prompt to Production — Chapter 20, Project 5*

*HIPAA-compliant clinical guideline Q&A with PHI detection, speciality RBAC, grounded generation, and compliance-grade audit logging.*

</div>