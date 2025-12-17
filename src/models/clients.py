"""
Modelos para gerenciamento de clientes.

Define tipos e schemas Pydantic para representar
clientes e suas informações cadastrais.

O client_id é usado como partition key no Cosmos DB,
garantindo isolamento de dados entre clientes.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class ClientStatus(str, Enum):
    """Status do cliente no sistema."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class Client(BaseModel):
    """
    Representa um cliente no sistema.

    Um cliente pode ter múltiplos contratos e documentos associados.
    O ID do cliente é usado como partition key em todas as coleções
    para garantir isolamento de dados (multi-tenancy).
    """

    id: UUID = Field(default_factory=uuid4, description="ID único do cliente")
    name: str = Field(..., min_length=2, max_length=200, description="Nome/Razão Social")
    document: str = Field(
        ...,
        min_length=11,
        max_length=18,
        description="CPF ou CNPJ (apenas números ou formatado)",
    )
    document_type: str = Field(
        default="cnpj",
        description="Tipo do documento: 'cpf' ou 'cnpj'",
    )

    # Contato
    email: Optional[str] = Field(default=None, description="E-mail de contato")
    phone: Optional[str] = Field(default=None, description="Telefone de contato")

    # Endereço (opcional)
    address: Optional[str] = Field(default=None, description="Endereço completo")
    city: Optional[str] = Field(default=None, description="Cidade")
    state: Optional[str] = Field(default=None, max_length=2, description="UF")

    # Status
    status: ClientStatus = Field(
        default=ClientStatus.ACTIVE,
        description="Status do cliente",
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Data de criação",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Última atualização",
    )

    # Metadados extras
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Dados adicionais customizados",
    )

    @field_validator("document_type")
    @classmethod
    def validate_document_type(cls, v: str) -> str:
        """Valida o tipo de documento."""
        v = v.lower()
        if v not in ["cpf", "cnpj"]:
            raise ValueError("document_type deve ser 'cpf' ou 'cnpj'")
        return v

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: Optional[str]) -> Optional[str]:
        """Valida UF (2 letras maiúsculas)."""
        if v is not None:
            return v.upper()
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Empresa ABC Ltda",
                    "document": "12.345.678/0001-90",
                    "document_type": "cnpj",
                    "email": "contato@empresaabc.com.br",
                    "phone": "(11) 99999-9999",
                    "city": "São Paulo",
                    "state": "SP",
                    "status": "active",
                }
            ]
        }
    }


# ============================================
# Modelos de API
# ============================================


class ClientSummary(BaseModel):
    """Resumo de um cliente para listagem."""

    id: UUID = Field(..., description="ID do cliente")
    name: str = Field(..., description="Nome/Razão Social")
    document: str = Field(..., description="CPF ou CNPJ")
    document_type: str = Field(..., description="Tipo do documento")
    status: ClientStatus = Field(..., description="Status")
    created_at: datetime = Field(..., description="Data de criação")

    # Estatísticas (opcionais, preenchidas sob demanda)
    contract_count: Optional[int] = Field(
        default=None,
        description="Número de contratos",
    )
    document_count: Optional[int] = Field(
        default=None,
        description="Número de documentos",
    )


class ClientListResponse(BaseModel):
    """Resposta de listagem de clientes."""

    clients: List[ClientSummary] = Field(..., description="Lista de clientes")
    total_count: int = Field(..., description="Total de clientes")
    has_more: bool = Field(
        default=False,
        description="Se há mais clientes para paginar",
    )


class ClientDetailResponse(BaseModel):
    """Resposta com detalhes completos de um cliente."""

    id: UUID = Field(..., description="ID do cliente")
    name: str = Field(..., description="Nome/Razão Social")
    document: str = Field(..., description="CPF ou CNPJ")
    document_type: str = Field(..., description="Tipo do documento")
    email: Optional[str] = Field(default=None, description="E-mail")
    phone: Optional[str] = Field(default=None, description="Telefone")
    address: Optional[str] = Field(default=None, description="Endereço")
    city: Optional[str] = Field(default=None, description="Cidade")
    state: Optional[str] = Field(default=None, description="UF")
    status: ClientStatus = Field(..., description="Status")
    created_at: datetime = Field(..., description="Data de criação")
    updated_at: datetime = Field(..., description="Última atualização")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadados")

    # Estatísticas
    contract_count: int = Field(default=0, description="Número de contratos")
    document_count: int = Field(default=0, description="Número de documentos")
    conversation_count: int = Field(default=0, description="Número de conversas")


class CreateClientRequest(BaseModel):
    """Request para criar um novo cliente."""

    name: str = Field(
        ...,
        min_length=2,
        max_length=200,
        description="Nome/Razão Social",
    )
    document: str = Field(
        ...,
        min_length=11,
        max_length=18,
        description="CPF ou CNPJ",
    )
    document_type: str = Field(
        default="cnpj",
        description="Tipo do documento: 'cpf' ou 'cnpj'",
    )
    email: Optional[str] = Field(default=None, description="E-mail")
    phone: Optional[str] = Field(default=None, description="Telefone")
    address: Optional[str] = Field(default=None, description="Endereço")
    city: Optional[str] = Field(default=None, description="Cidade")
    state: Optional[str] = Field(default=None, max_length=2, description="UF")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadados adicionais",
    )


class UpdateClientRequest(BaseModel):
    """Request para atualizar um cliente."""

    name: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=200,
        description="Nome/Razão Social",
    )
    email: Optional[str] = Field(default=None, description="E-mail")
    phone: Optional[str] = Field(default=None, description="Telefone")
    address: Optional[str] = Field(default=None, description="Endereço")
    city: Optional[str] = Field(default=None, description="Cidade")
    state: Optional[str] = Field(default=None, max_length=2, description="UF")
    status: Optional[ClientStatus] = Field(default=None, description="Status")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Metadados (substitui existentes)",
    )


# ============================================
# Modelos para Contratos por Cliente
# ============================================


class ContractSummary(BaseModel):
    """Resumo de um contrato para listagem."""

    id: UUID = Field(..., description="ID do documento/contrato")
    filename: str = Field(..., description="Nome do arquivo")
    status: str = Field(..., description="Status de processamento")
    created_at: datetime = Field(..., description="Data de upload")
    processed_at: Optional[datetime] = Field(
        default=None,
        description="Data de processamento",
    )
    page_count: Optional[int] = Field(
        default=None,
        description="Número de páginas (se disponível)",
    )


class ClientContractsResponse(BaseModel):
    """Resposta de listagem de contratos de um cliente."""

    client_id: str = Field(..., description="ID do cliente")
    contracts: List[ContractSummary] = Field(..., description="Lista de contratos")
    total_count: int = Field(..., description="Total de contratos")
    has_more: bool = Field(
        default=False,
        description="Se há mais contratos para paginar",
    )


# ============================================
# Modelos para Status de Processamento
# ============================================


class DocumentProcessingStatus(BaseModel):
    """Status de processamento de um documento."""

    id: UUID = Field(..., description="ID do documento")
    filename: str = Field(..., description="Nome do arquivo")
    document_type: str = Field(..., description="Tipo: contract ou cost_data")
    status: str = Field(..., description="Status: uploaded, processing, indexed, failed")
    created_at: datetime = Field(..., description="Data de upload")
    updated_at: datetime = Field(..., description="Última atualização")
    processed_at: Optional[datetime] = Field(
        default=None,
        description="Data de conclusão do processamento",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Mensagem de erro (se status=failed)",
    )


class ProcessingStatusResponse(BaseModel):
    """Resposta com status de processamento de documentos de um cliente."""

    client_id: str = Field(..., description="ID do cliente")

    # Resumo geral
    total_documents: int = Field(..., description="Total de documentos")
    documents_uploaded: int = Field(
        default=0,
        description="Aguardando processamento",
    )
    documents_processing: int = Field(
        default=0,
        description="Em processamento",
    )
    documents_indexed: int = Field(
        default=0,
        description="Processados com sucesso",
    )
    documents_failed: int = Field(
        default=0,
        description="Falharam no processamento",
    )

    # Lista de documentos (opcional, para detalhes)
    documents: Optional[List[DocumentProcessingStatus]] = Field(
        default=None,
        description="Lista detalhada de documentos",
    )


class ClientStatsResponse(BaseModel):
    """Estatísticas gerais de um cliente."""

    client_id: str = Field(..., description="ID do cliente")
    client_name: str = Field(..., description="Nome do cliente")

    # Documentos
    total_contracts: int = Field(default=0, description="Total de contratos")
    total_cost_files: int = Field(default=0, description="Total de arquivos de custos")
    documents_pending: int = Field(default=0, description="Documentos pendentes")
    documents_ready: int = Field(default=0, description="Documentos prontos")

    # Conversas
    total_conversations: int = Field(default=0, description="Total de conversas")
    active_conversations: int = Field(default=0, description="Conversas ativas")

    # Custos (se houver dados)
    total_cost_records: Optional[int] = Field(
        default=None,
        description="Total de registros de custos",
    )
    total_charged_amount: Optional[float] = Field(
        default=None,
        description="Total cobrado (sum)",
    )
    cost_period_start: Optional[str] = Field(
        default=None,
        description="Início do período de custos",
    )
    cost_period_end: Optional[str] = Field(
        default=None,
        description="Fim do período de custos",
    )
