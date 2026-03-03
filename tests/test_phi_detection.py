"""Tests for PHI detection and redaction."""
import pytest
from src.phi_detection import PHIDetector


def test_no_phi_in_clinical_query():
    detector = PHIDetector()
    detector._client = None  # Force local check
    query = "What is the first-line treatment for Type 2 diabetes?"
    redacted, has_phi = detector.scan_query(query)
    assert has_phi is False
    assert redacted == query


def test_ssn_redacted():
    detector = PHIDetector()
    detector._client = None
    text = "Patient SSN 123-45-6789 has diabetes"
    redacted, _ = detector.redact(text)
    assert "123-45-6789" not in redacted
    assert "REDACTED" in redacted


def test_email_redacted():
    detector = PHIDetector()
    detector._client = None
    text = "Contact patient at john.doe@nhs.net for follow-up"
    redacted, categories = detector.redact(text)
    assert "john.doe@nhs.net" not in redacted


def test_patient_id_redacted():
    detector = PHIDetector()
    detector._client = None
    text = "Patient ID: NHS-12345678 needs medication review"
    redacted, categories = detector.redact(text)
    assert "NHS-12345678" not in redacted


def test_clean_clinical_text_unchanged():
    detector = PHIDetector()
    detector._client = None
    text = "Metformin 500mg twice daily for Type 2 diabetes management per NICE guidelines NG28"
    redacted, categories = detector.redact(text)
    assert "Metformin" in redacted
    assert "NICE" in redacted
