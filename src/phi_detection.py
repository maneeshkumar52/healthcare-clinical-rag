"""Azure AI Language PHI detection and redaction."""
import re
import structlog
from typing import Tuple, List
from src.config import get_settings

logger = structlog.get_logger(__name__)

PHI_CATEGORIES = [
    "Person", "PhoneNumber", "Email", "Address",
    "USSocialSecurityNumber", "UKNationalInsuranceNumber",
    "MedicalLicense", "PatientID", "Age", "Date",
]

# Heuristic PHI patterns for local detection
PHI_PATTERNS = [
    (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), "[SSN REDACTED]"),
    (re.compile(r'\bNI\s*[A-Z]{2}\s*\d{6}\s*[A-Z]\b', re.IGNORECASE), "[NI REDACTED]"),
    (re.compile(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b'), "[NAME REDACTED]"),
    (re.compile(r'\b[\w.-]+@[\w.-]+\.\w+\b'), "[EMAIL REDACTED]"),
    (re.compile(r'\b(?:\+44|0)\d{10}\b'), "[PHONE REDACTED]"),
    (re.compile(r'\bPatient ID[:\s]+[\w-]+\b', re.IGNORECASE), "[PATIENT_ID REDACTED]"),
    (re.compile(r'\bDOB[:\s]+\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', re.IGNORECASE), "[DOB REDACTED]"),
]


class PHIDetector:
    """Detects and redacts PHI using Azure AI Language and local heuristics."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from azure.ai.textanalytics import TextAnalyticsClient
                from azure.core.credentials import AzureKeyCredential
                self._client = TextAnalyticsClient(
                    endpoint=self.settings.azure_language_endpoint,
                    credential=AzureKeyCredential(self.settings.azure_language_key),
                )
            except Exception:
                self._client = None
        return self._client

    def _local_redact(self, text: str) -> Tuple[str, List[str]]:
        """Apply local regex-based PHI redaction."""
        redacted = text
        found_categories = []
        for pattern, replacement in PHI_PATTERNS:
            if pattern.search(redacted):
                found_categories.append(replacement.strip("[]").split()[0])
                redacted = pattern.sub(replacement, redacted)
        return redacted, found_categories

    def redact(self, text: str) -> Tuple[str, List[str]]:
        """
        Redact PHI from text using Azure AI Language or local heuristics.

        Args:
            text: Text that may contain PHI.

        Returns:
            Tuple of (redacted_text, list_of_categories_found).
        """
        client = self._get_client()
        if client:
            try:
                result = client.recognize_pii_entities([text])[0]
                if not result.is_error:
                    redacted = result.redacted_text
                    categories = [e.category for e in result.entities]
                    if categories:
                        logger.warning("phi_detected_azure", categories=categories)
                    return redacted, categories
            except Exception as exc:
                logger.error("azure_language_pii_failed", error=str(exc))

        # Fallback to local heuristics
        redacted, categories = self._local_redact(text)
        if categories:
            logger.warning("phi_detected_local", categories=categories)
        return redacted, categories

    def scan_query(self, query: str) -> Tuple[str, bool]:
        """
        Scan and redact a clinical query.

        Returns:
            Tuple of (redacted_query, has_phi).
        """
        redacted, categories = self.redact(query)
        has_phi = len(categories) > 0
        if has_phi:
            logger.warning("phi_in_query_redacted", categories=categories, original_length=len(query))
        return redacted, has_phi
