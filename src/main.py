"""FastAPI entry point for Healthcare Clinical RAG."""
import time
import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import structlog

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger(__name__)

from src.models import ClinicalQuery, ClinicalResponse, HIPAAAuditRecord, ClinicianContext
from src.auth import validate_clinician
from src.phi_detection import PHIDetector
from src.retriever import ClinicalRetriever
from src.generator import ClinicalGenerator, MEDICAL_DISCLAIMER
from src.audit import HIPAAAuditLogger

phi_detector: PHIDetector = None
retriever: ClinicalRetriever = None
generator: ClinicalGenerator = None
auditor: HIPAAAuditLogger = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global phi_detector, retriever, generator, auditor
    phi_detector = PHIDetector()
    retriever = ClinicalRetriever()
    generator = ClinicalGenerator()
    auditor = HIPAAAuditLogger()
    logger.info("healthcare_clinical_rag_starting")
    yield
    logger.info("healthcare_clinical_rag_stopping")


app = FastAPI(
    title="Healthcare Clinical RAG",
    description="HIPAA-compliant clinical guideline Q&A — Project 5, Chapter 20, Prompt to Production",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "healthcare-clinical-rag", "version": "1.0.0"}


@app.post("/query", response_model=ClinicalResponse)
async def query_guidelines(
    request: ClinicalQuery,
    clinician: ClinicianContext = Depends(validate_clinician),
) -> ClinicalResponse:
    """Query clinical guidelines. PHI is redacted before processing."""
    start = time.time()
    redacted_query, has_phi = phi_detector.scan_query(request.question)
    if has_phi:
        logger.warning("phi_detected_in_query", clinician=clinician.clinician_id)

    docs = await retriever.search(redacted_query, clinician)
    answer, confidence = await generator.generate(redacted_query, docs, clinician)

    latency = (time.time() - start) * 1000
    sources = [d.title for d in docs]

    response = ClinicalResponse(
        answer=answer,
        sources=sources,
        confidence=confidence,
        medical_disclaimer=MEDICAL_DISCLAIMER,
        phi_detected_in_query=has_phi,
    )

    await auditor.log(
        HIPAAAuditRecord(
            clinician_id=clinician.clinician_id,
            speciality=clinician.speciality,
            question_redacted=redacted_query,
            answer=answer[:500],
            sources=sources,
            phi_detected=has_phi,
            confidence=confidence,
            latency_ms=round(latency, 2),
        )
    )

    logger.info(
        "clinical_query_processed",
        clinician=clinician.clinician_id,
        confidence=confidence,
        phi=has_phi,
    )
    return response
