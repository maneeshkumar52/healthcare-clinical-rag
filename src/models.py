from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
import uuid


class ClinicalQuery(BaseModel):
    question: str = Field(..., min_length=5)
    session_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))


class ClinicalDocument(BaseModel):
    title: str
    content_snippet: str
    relevance_score: float
    guideline_version: Optional[str] = None


class ClinicalResponse(BaseModel):
    answer: str
    sources: List[str]
    confidence: str
    medical_disclaimer: str
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    phi_detected_in_query: bool = False


class ClinicianContext(BaseModel):
    clinician_id: str
    name: str
    speciality: str
    department: str
    allowed_categories: List[str] = Field(default_factory=list)


class HIPAAAuditRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    clinician_id: str
    speciality: str
    question_redacted: str
    answer: str
    sources: List[str]
    phi_detected: bool
    confidence: str
    latency_ms: float
