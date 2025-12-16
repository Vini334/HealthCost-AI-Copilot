"""
Modelos Pydantic para a API de busca.

Schemas de request e response para os endpoints de busca semântica.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SearchModeEnum(str, Enum):
    """Modo de busca."""
    VECTOR = "vector"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


class SearchRequest(BaseModel):
    """
    Request para busca de chunks.

    Exemplo:
        {
            "query": "qual o prazo de carência para internação?",
            "client_id": "cliente-123",
            "mode": "hybrid",
            "top": 5
        }
    """
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Texto da pergunta ou busca",
    )
    client_id: str = Field(
        ...,
        min_length=1,
        description="ID do cliente (obrigatório para multi-tenancy)",
    )
    document_id: Optional[UUID] = Field(
        default=None,
        description="Filtrar por documento específico",
    )
    section_type: Optional[str] = Field(
        default=None,
        description="Filtrar por tipo de seção (clausula, paragrafo, anexo)",
    )
    mode: SearchModeEnum = Field(
        default=SearchModeEnum.HYBRID,
        description="Modo de busca: vector, keyword ou hybrid (recomendado)",
    )
    top: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Número máximo de resultados",
    )
    min_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Score mínimo para incluir resultado (0.0 a 1.0)",
    )


class SearchResultItem(BaseModel):
    """
    Item individual do resultado de busca.

    Contém o chunk encontrado e metadados de relevância.
    """
    # Identificação
    id: str = Field(..., description="ID único do chunk")
    document_id: str = Field(..., description="ID do documento original")
    client_id: str = Field(..., description="ID do cliente")

    # Conteúdo
    content: str = Field(..., description="Texto do chunk")
    content_length: int = Field(..., description="Tamanho do conteúdo em caracteres")

    # Localização no documento (para citações)
    page_number: Optional[int] = Field(None, description="Número da página")
    page_start: Optional[int] = Field(None, description="Página inicial")
    page_end: Optional[int] = Field(None, description="Página final")
    section_title: Optional[str] = Field(None, description="Título da seção/cláusula")
    section_number: Optional[str] = Field(None, description="Número da seção")
    section_type: Optional[str] = Field(None, description="Tipo de seção")

    # Metadados
    chunk_index: int = Field(..., description="Índice do chunk no documento")
    total_chunks: Optional[int] = Field(None, description="Total de chunks do documento")

    # Scores de relevância
    score: float = Field(..., description="Score de relevância principal")
    vector_score: Optional[float] = Field(None, description="Score da busca vetorial")
    keyword_score: Optional[float] = Field(None, description="Score da busca por keyword")
    reranker_score: Optional[float] = Field(None, description="Score após re-ranking")

    # Timestamps
    created_at: Optional[datetime] = Field(None, description="Data de criação")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "document_id": "550e8400-e29b-41d4-a716-446655440001",
                "client_id": "cliente-123",
                "content": "CLÁUSULA 5 - CARÊNCIAS. O prazo de carência para internação hospitalar é de 24 (vinte e quatro) horas...",
                "content_length": 850,
                "page_number": 5,
                "section_title": "CLÁUSULA 5 - CARÊNCIAS",
                "section_type": "clausula",
                "chunk_index": 4,
                "total_chunks": 45,
                "score": 0.85,
                "reranker_score": 0.92,
            }
        }


class SearchResponse(BaseModel):
    """
    Resposta completa da busca.

    Contém os resultados e metadados da operação.
    """
    results: List[SearchResultItem] = Field(
        ...,
        description="Lista de chunks encontrados",
    )
    total_count: int = Field(
        ...,
        description="Número total de resultados",
    )
    query: str = Field(
        ...,
        description="Query original",
    )
    mode: SearchModeEnum = Field(
        ...,
        description="Modo de busca utilizado",
    )
    filters_applied: Dict[str, Optional[str]] = Field(
        ...,
        description="Filtros aplicados na busca",
    )
    search_time_ms: float = Field(
        ...,
        description="Tempo de busca em milissegundos",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "results": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "document_id": "550e8400-e29b-41d4-a716-446655440001",
                        "client_id": "cliente-123",
                        "content": "CLÁUSULA 5 - CARÊNCIAS...",
                        "content_length": 850,
                        "page_number": 5,
                        "section_title": "CLÁUSULA 5 - CARÊNCIAS",
                        "score": 0.85,
                        "chunk_index": 4,
                    }
                ],
                "total_count": 1,
                "query": "qual o prazo de carência?",
                "mode": "hybrid",
                "filters_applied": {
                    "client_id": "cliente-123",
                    "document_id": None,
                },
                "search_time_ms": 125.5,
            }
        }


class SimilarChunksRequest(BaseModel):
    """
    Request para buscar chunks similares a um chunk específico.

    Útil para encontrar cláusulas similares em outros contratos.
    """
    chunk_id: str = Field(
        ...,
        description="ID do chunk de referência",
    )
    client_id: str = Field(
        ...,
        description="ID do cliente",
    )
    top: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Número de resultados",
    )
    exclude_same_document: bool = Field(
        default=False,
        description="Se True, exclui chunks do mesmo documento",
    )
