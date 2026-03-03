"""HIPAA-compliant audit logging to Cosmos DB."""
import structlog
from src.config import get_settings
from src.models import HIPAAAuditRecord

logger = structlog.get_logger(__name__)


class HIPAAAuditLogger:
    """Writes immutable HIPAA-compliant audit records with 7-year TTL."""

    def __init__(self) -> None:
        self.settings = get_settings()

    async def log(self, record: HIPAAAuditRecord) -> None:
        try:
            from azure.cosmos.aio import CosmosClient
            async with CosmosClient(
                url=self.settings.cosmos_endpoint,
                credential=self.settings.cosmos_key,
            ) as client:
                db = client.get_database_client(self.settings.cosmos_database)
                container = db.get_container_client(self.settings.cosmos_audit_container)
                doc = record.model_dump()
                doc["timestamp"] = doc["timestamp"].isoformat()
                doc["ttl"] = 7 * 365 * 24 * 3600
                doc["_partitionKey"] = record.clinician_id
                await container.create_item(body=doc)
                logger.info("hipaa_audit_written", id=record.id, clinician=record.clinician_id)
        except Exception as exc:
            logger.error("hipaa_audit_failed", error=str(exc))
