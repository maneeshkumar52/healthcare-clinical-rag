"""Index clinical guidelines into Azure AI Search."""
import uuid
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_settings
from src.phi_detection import PHIDetector


def main():
    settings = get_settings()
    from openai import AzureOpenAI
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        SearchIndex,
        SimpleField,
        SearchableField,
        SearchField,
        SearchFieldDataType,
        VectorSearch,
        HnswAlgorithmConfiguration,
        VectorSearchProfile,
        SemanticConfiguration,
        SemanticSearch,
        SemanticPrioritizedFields,
        SemanticField,
    )
    from azure.core.credentials import AzureKeyCredential

    cred = AzureKeyCredential(settings.azure_search_api_key)
    idx_client = SearchIndexClient(endpoint=settings.azure_search_endpoint, credential=cred)
    search_client = SearchClient(
        endpoint=settings.azure_search_endpoint,
        index_name=settings.azure_search_index_name,
        credential=cred,
    )
    oai = AzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
    )
    phi = PHIDetector()

    # Create index schema
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="title", type=SearchFieldDataType.String),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SimpleField(name="category", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="guideline_version", type=SearchFieldDataType.String),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=3072,
            vector_search_profile_name="myHnsw",
        ),
    ]
    vs = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="myHnsw")],
        profiles=[VectorSearchProfile(name="myHnsw", algorithm_configuration_name="myHnsw")],
    )
    sc = SemanticConfiguration(
        name="default",
        prioritized_fields=SemanticPrioritizedFields(
            title_field=SemanticField(field_name="title"),
            content_fields=[SemanticField(field_name="content")],
        ),
    )
    idx_client.create_or_update_index(
        SearchIndex(
            name=settings.azure_search_index_name,
            fields=fields,
            vector_search=vs,
            semantic_search=SemanticSearch(configurations=[sc]),
        )
    )

    guidelines_dir = Path(__file__).parent / "guidelines"
    docs = []
    for f in guidelines_dir.glob("*.md"):
        text = f.read_text(encoding="utf-8")
        redacted, _ = phi.redact(text)  # PHI-redact before indexing
        category = f.stem.split("_")[0]
        title = f.stem.replace("_", " ").title()
        # Chunk into 800-char pieces with 200-char overlap
        chunks = [redacted[i : i + 800] for i in range(0, len(redacted), 600)]
        for j, chunk in enumerate(chunks):
            emb = (
                oai.embeddings.create(
                    input=chunk,
                    model=settings.azure_openai_embedding_deployment,
                )
                .data[0]
                .embedding
            )
            docs.append(
                {
                    "id": str(uuid.uuid4()),
                    "title": title,
                    "content": chunk,
                    "category": category,
                    "guideline_version": "2024",
                    "content_vector": emb,
                }
            )

    if docs:
        search_client.upload_documents(docs)
        print(f"Indexed {len(docs)} chunks from {guidelines_dir}")
    else:
        print("No guideline documents found to index.")


if __name__ == "__main__":
    main()
