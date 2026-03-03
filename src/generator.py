"""Clinical response generation with mandatory medical disclaimer."""
import time
import structlog
from typing import List, Tuple
from openai import AsyncAzureOpenAI
from src.config import get_settings
from src.models import ClinicalDocument, ClinicianContext

logger = structlog.get_logger(__name__)

MEDICAL_DISCLAIMER = (
    "CLINICAL DISCLAIMER: This information is derived from clinical guidelines and is intended "
    "for qualified healthcare professionals only. It should not replace professional clinical judgment, "
    "local protocol review, or patient-specific assessment. Always verify with current local guidelines "
    "and consult specialist colleagues when appropriate."
)

SYSTEM_PROMPT = """You are a clinical knowledge assistant for qualified healthcare professionals.
Answer questions ONLY based on the provided clinical guidelines.
Always cite the specific guideline and section you are referencing.
Flag when guidelines may be outdated or when clinical judgment is particularly important.
Never recommend specific dosages for individual patients — only reference guideline ranges.
If the information is not in the provided guidelines, say so clearly."""


class ClinicalGenerator:
    """Generates grounded clinical responses with mandatory disclaimers."""

    def __init__(self) -> None:
        s = get_settings()
        self.client = AsyncAzureOpenAI(
            azure_endpoint=s.azure_openai_endpoint,
            api_key=s.azure_openai_api_key,
            api_version=s.azure_openai_api_version,
            max_retries=3,
        )
        self.settings = s

    def _confidence(self, docs: List[ClinicalDocument]) -> str:
        if not docs:
            return "Low"
        high = [d for d in docs if d.relevance_score > 0.8]
        return "High" if len(high) >= 3 else "Medium" if docs else "Low"

    async def generate(
        self,
        question: str,
        docs: List[ClinicalDocument],
        clinician: ClinicianContext,
    ) -> Tuple[str, str]:
        """Generate grounded clinical answer with disclaimer."""
        context = (
            "\n".join(f"[{d.title}]\n{d.content_snippet}" for i, d in enumerate(docs, 1))
            or "No relevant guidelines found."
        )
        user_msg = (
            f"Clinical Question: {question}\n\n"
            f"Available Guidelines:\n{context}\n\n"
            f"Provide a grounded clinical response with source citations."
        )
        try:
            resp = await self.client.chat.completions.create(
                model=self.settings.azure_openai_deployment,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.1,
                max_tokens=800,
            )
            answer = resp.choices[0].message.content or ""
            return answer + f"\n\n{MEDICAL_DISCLAIMER}", self._confidence(docs)
        except Exception as exc:
            logger.error("clinical_gen_failed", error=str(exc))
            return (
                f"Unable to retrieve clinical information. Please consult clinical resources directly.\n\n{MEDICAL_DISCLAIMER}",
                "Low",
            )
