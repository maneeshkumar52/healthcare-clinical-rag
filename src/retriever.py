"""Clinical guideline retrieval with speciality-based RBAC."""
import structlog
from typing import List
from openai import AsyncAzureOpenAI
from azure.search.documents.aio import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential
from src.config import get_settings
from src.models import ClinicalDocument, ClinicianContext

logger = structlog.get_logger(__name__)


class ClinicalRetriever:
    """Retrieves clinical guidelines filtered by clinician's allowed speciality categories."""

    def __init__(self) -> None:
        s = get_settings()
        self.settings = s
        self.openai_client = AsyncAzureOpenAI(
            azure_endpoint=s.azure_openai_endpoint,
            api_key=s.azure_openai_api_key,
            api_version=s.azure_openai_api_version,
        )
        self.search_client = SearchClient(
            endpoint=s.azure_search_endpoint,
            index_name=s.azure_search_index_name,
            credential=AzureKeyCredential(s.azure_search_api_key),
        )

    async def _embed(self, text: str) -> List[float]:
        try:
            resp = await self.openai_client.embeddings.create(
                input=text,
                model=self.settings.azure_openai_embedding_deployment,
            )
            return resp.data[0].embedding
        except Exception as exc:
            logger.error("embed_failed", error=str(exc))
            return []

    async def search(self, query: str, clinician: ClinicianContext, top_k: int = 5) -> List[ClinicalDocument]:
        """Retrieve guidelines filtered by clinician's allowed categories."""
        logger.info("clinical_search", speciality=clinician.speciality, query_len=len(query))
        try:
            embedding = await self._embed(query)
            category_filter = (
                " or ".join(f"category eq '{c}'" for c in clinician.allowed_categories)
                if clinician.allowed_categories
                else None
            )
            kwargs = {
                "search_text": query,
                "top": top_k,
                "select": ["title", "content", "category", "guideline_version"],
                "query_type": "semantic",
                "semantic_configuration_name": "default",
            }
            if category_filter:
                kwargs["filter"] = category_filter
            if embedding:
                kwargs["vector_queries"] = [
                    VectorizedQuery(
                        vector=embedding,
                        k_nearest_neighbors=top_k,
                        fields="content_vector",
                    )
                ]

            results = []
            async with self.search_client as client:
                async for doc in await client.search(**kwargs):
                    results.append(
                        ClinicalDocument(
                            title=doc.get("title", "Clinical Guideline"),
                            content_snippet=doc.get("content", "")[:400],
                            relevance_score=doc.get("@search.score", 0.0),
                            guideline_version=doc.get("guideline_version"),
                        )
                    )
            logger.info("clinical_search_done", results=len(results))
            return results
        except Exception as exc:
            logger.error("clinical_search_failed", error=str(exc))
            return []
