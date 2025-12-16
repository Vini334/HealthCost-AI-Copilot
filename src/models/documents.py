"""
Modelos Pydantic para documentos (contratos e custos).

Estes modelos definem a estrutura dos dados para:
- Uploads de arquivos
- Metadados armazenados no Cosmos DB
- Respostas da API
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class DocumentType(str, Enum):
    """
    Tipo de documento suportado.

    - CONTRACT: Contratos em PDF
    - COST_DATA: Dados de custos em CSV/Excel
    """
    CONTRACT = "contract"
    COST_DATA = "cost_data"


class DocumentStatus(str, Enum):
    """
    Status do processamento do documento.

    - UPLOADED: Arquivo recebido e armazenado no Blob Storage
    - PROCESSING: Em processamento (extração de texto, chunking, etc.)
    - INDEXED: Processado e indexado no Azure AI Search
    - FAILED: Falha no processamento
    """
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class DocumentMetadata(BaseModel):
    """
    Metadados de um documento armazenado.

    Este modelo é salvo no Cosmos DB para cada documento.
    O partition key é o client_id para isolamento multi-tenant.
    """

    # Identificadores
    id: UUID = Field(default_factory=uuid4, description="ID único do documento")
    client_id: str = Field(..., description="ID do cliente (multi-tenancy)")

    # Informações do arquivo
    filename: str = Field(..., description="Nome original do arquivo")
    file_size: int = Field(..., ge=0, description="Tamanho em bytes")
    content_type: str = Field(..., description="MIME type do arquivo")
    document_type: DocumentType = Field(..., description="Tipo do documento")

    # Localização no Azure
    blob_path: str = Field(..., description="Caminho completo no Blob Storage")
    container_name: str = Field(..., description="Nome do container no Blob Storage")

    # Status e timestamps
    status: DocumentStatus = Field(
        default=DocumentStatus.UPLOADED,
        description="Status do processamento"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Data de upload"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Última atualização"
    )
    processed_at: Optional[datetime] = Field(
        default=None,
        description="Data de conclusão do processamento"
    )

    # Metadados específicos (opcional)
    contract_id: Optional[str] = Field(
        default=None,
        description="ID do contrato (para contratos)"
    )
    period_start: Optional[datetime] = Field(
        default=None,
        description="Início do período (para dados de custos)"
    )
    period_end: Optional[datetime] = Field(
        default=None,
        description="Fim do período (para dados de custos)"
    )

    # Informações de erro (se houver)
    error_message: Optional[str] = Field(
        default=None,
        description="Mensagem de erro se status=FAILED"
    )

    @field_validator("client_id")
    @classmethod
    def validate_client_id(cls, v: str) -> str:
        """Valida que client_id não está vazio."""
        if not v or not v.strip():
            raise ValueError("client_id não pode ser vazio")
        return v.strip()

    class Config:
        """Configuração do modelo."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


# ============================================================
# Modelos de Request/Response para a API
# ============================================================

class UploadResponse(BaseModel):
    """
    Resposta de sucesso após upload de documento.

    Retornada quando um arquivo é salvo com sucesso.
    """
    success: bool = Field(default=True, description="Indica sucesso")
    document_id: UUID = Field(..., description="ID do documento criado")
    filename: str = Field(..., description="Nome do arquivo")
    blob_path: str = Field(..., description="Caminho no storage")
    message: str = Field(..., description="Mensagem informativa")


class UploadError(BaseModel):
    """
    Resposta de erro no upload.

    Retornada quando ocorre erro na validação ou upload.
    """
    success: bool = Field(default=False)
    error: str = Field(..., description="Tipo do erro")
    detail: str = Field(..., description="Descrição detalhada")


class DocumentListResponse(BaseModel):
    """
    Lista de documentos de um cliente.
    """
    client_id: str
    documents: list[DocumentMetadata]
    total: int = Field(..., description="Total de documentos")


# ============================================================
# Constantes de Validação
# ============================================================

# Tamanho máximo de arquivo (50MB)
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Tipos MIME permitidos por tipo de documento
ALLOWED_CONTRACT_TYPES = {
    "application/pdf",
}

ALLOWED_COST_TYPES = {
    "text/csv",
    "application/vnd.ms-excel",  # .xls
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
}

# Extensões permitidas
ALLOWED_CONTRACT_EXTENSIONS = {".pdf"}
ALLOWED_COST_EXTENSIONS = {".csv", ".xls", ".xlsx"}
