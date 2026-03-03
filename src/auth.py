"""Clinician authentication and speciality-based RBAC."""
from typing import Optional
import structlog
from fastapi import HTTPException, Header
from jose import jwt, JWTError
from src.models import ClinicianContext
from src.config import get_settings

logger = structlog.get_logger(__name__)

SPECIALITY_ACCESS = {
    "general_practitioner": ["general", "primary_care", "preventive"],
    "cardiologist": ["cardiac", "cardiology", "general", "primary_care"],
    "psychiatrist": ["mental_health", "psychiatry", "general"],
    "pharmacist": ["formulary", "prescribing", "pharmacy", "general"],
    "physician": ["general", "primary_care", "preventive", "formulary"],
    "nurse": ["general", "primary_care"],
}

MOCK_CLINICIANS = {
    "dr-001": ClinicianContext(
        clinician_id="dr-001",
        name="Dr Alice Smith",
        speciality="general_practitioner",
        department="Primary Care",
        allowed_categories=SPECIALITY_ACCESS["general_practitioner"],
    ),
    "dr-002": ClinicianContext(
        clinician_id="dr-002",
        name="Dr Bob Jones",
        speciality="cardiologist",
        department="Cardiology",
        allowed_categories=SPECIALITY_ACCESS["cardiologist"],
    ),
    "dr-003": ClinicianContext(
        clinician_id="dr-003",
        name="Dr Carol Lee",
        speciality="psychiatrist",
        department="Mental Health",
        allowed_categories=SPECIALITY_ACCESS["psychiatrist"],
    ),
    "ph-001": ClinicianContext(
        clinician_id="ph-001",
        name="Pharmacist Dave Brown",
        speciality="pharmacist",
        department="Pharmacy",
        allowed_categories=SPECIALITY_ACCESS["pharmacist"],
    ),
}


def create_test_token(clinician_id: str) -> str:
    settings = get_settings()
    return jwt.encode({"sub": clinician_id}, settings.jwt_secret, algorithm="HS256")


def validate_clinician(authorization: Optional[str] = Header(None)) -> ClinicianContext:
    """Validate JWT and return clinician context with allowed guideline categories."""
    settings = get_settings()
    if not authorization:
        logger.warning("no_auth_header_dev_fallback")
        return MOCK_CLINICIANS["dr-001"]
    try:
        scheme, token = authorization.split(" ", 1)
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid auth scheme")
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        clinician_id = payload.get("sub")
        clinician = MOCK_CLINICIANS.get(clinician_id)
        if not clinician:
            speciality = payload.get("speciality", "general_practitioner")
            clinician = ClinicianContext(
                clinician_id=clinician_id,
                name=payload.get("name", "Unknown Clinician"),
                speciality=speciality,
                department=payload.get("department", "General"),
                allowed_categories=SPECIALITY_ACCESS.get(speciality, ["general"]),
            )
        logger.info("clinician_authenticated", id=clinician.clinician_id, speciality=clinician.speciality)
        return clinician
    except JWTError as exc:
        logger.error("jwt_error", error=str(exc))
        raise HTTPException(status_code=401, detail="Invalid token")
