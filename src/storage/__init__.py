"""
Módulo de armazenamento.

Contém clientes para comunicação com serviços de storage do Azure:
- Azure Blob Storage (arquivos)
- Azure Cosmos DB (metadados estruturados)
"""

from src.storage.blob_storage import BlobStorageClient, get_blob_storage_client
from src.storage.cosmos_db import CosmosDBClient, get_cosmos_client

__all__ = [
    "BlobStorageClient",
    "get_blob_storage_client",
    "CosmosDBClient",
    "get_cosmos_client",
]
