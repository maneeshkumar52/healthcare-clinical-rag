"""Tests for clinical retriever and auth module."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.models import ClinicianContext


@pytest.fixture
def gp_clinician():
    return ClinicianContext(
        clinician_id="dr-001",
        name="Dr Test",
        speciality="general_practitioner",
        department="Primary Care",
        allowed_categories=["general", "primary_care", "preventive"],
    )


@pytest.mark.asyncio
async def test_retriever_initialises(gp_clinician):
    with patch("src.retriever.AsyncAzureOpenAI"), patch("src.retriever.SearchClient"):
        from src.retriever import ClinicalRetriever
        r = ClinicalRetriever()
        assert r is not None


@pytest.mark.asyncio
async def test_embedding_failure_returns_empty_list(gp_clinician):
    with patch("src.retriever.AsyncAzureOpenAI") as mock_oai, patch("src.retriever.SearchClient"):
        mock_oai.return_value.embeddings.create = AsyncMock(side_effect=Exception("Embedding failed"))
        from src.retriever import ClinicalRetriever
        r = ClinicalRetriever()
        r.openai_client = mock_oai.return_value
        result = await r._embed("test query")
        assert result == []


def test_auth_clinician_token():
    from src.auth import create_test_token, validate_clinician
    token = create_test_token("dr-001")
    clinician = validate_clinician(f"Bearer {token}")
    assert clinician.clinician_id == "dr-001"
    assert "general" in clinician.allowed_categories


def test_auth_cardiologist_access():
    from src.auth import create_test_token, validate_clinician
    token = create_test_token("dr-002")
    clinician = validate_clinician(f"Bearer {token}")
    assert "cardiac" in clinician.allowed_categories


def test_auth_pharmacist_access():
    from src.auth import create_test_token, validate_clinician
    token = create_test_token("ph-001")
    clinician = validate_clinician(f"Bearer {token}")
    assert "formulary" in clinician.allowed_categories
    assert "prescribing" in clinician.allowed_categories
