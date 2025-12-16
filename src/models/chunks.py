"""
Modelos para chunks de documentos.

Chunks são pedaços de texto extraídos de documentos maiores (PDFs).
Cada chunk contém:
- O texto em si
- Metadados de localização (página, seção)
- Referência ao documento original
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ChunkingStrategy(str, Enum):
    """
    Estratégia utilizada para criar os chunks.

    - PAGE: Um chunk por página do PDF
    - SECTION: Chunks baseados em seções/cláusulas detectadas
    - FIXED_SIZE: Chunks de tamanho fixo com overlap
    - HYBRID: Combinação de estratégias (seção quando possível, senão página)
    """
    PAGE = "page"
    SECTION = "section"
    FIXED_SIZE = "fixed_size"
    HYBRID = "hybrid"


class DocumentChunk(BaseModel):
    """
    Um chunk (pedaço) de texto extraído de um documento.

    Este é o modelo central para busca semântica. Cada chunk será:
    1. Transformado em embedding (vetor numérico)
    2. Indexado no Azure AI Search
    3. Recuperado quando relevante para uma pergunta

    Estrutura pensada para multi-tenancy e rastreabilidade:
    - client_id: Isolamento por cliente
    - document_id: Referência ao documento original
    - page_number: Permite citar "página X" na resposta
    - section_title: Permite citar "cláusula Y" na resposta
    """

    # Identificação
    id: UUID = Field(
        default_factory=uuid4,
        description="ID único do chunk"
    )
    document_id: UUID = Field(
        ...,
        description="ID do documento original (referência ao DocumentMetadata)"
    )
    client_id: str = Field(
        ...,
        description="ID do cliente para isolamento multi-tenant"
    )

    # Conteúdo
    content: str = Field(
        ...,
        description="Texto do chunk"
    )
    content_length: int = Field(
        default=0,
        description="Número de caracteres do conteúdo"
    )

    # Localização no documento original
    page_number: Optional[int] = Field(
        default=None,
        description="Número da página (1-indexed)"
    )
    page_start: Optional[int] = Field(
        default=None,
        description="Página inicial (para chunks multi-página)"
    )
    page_end: Optional[int] = Field(
        default=None,
        description="Página final (para chunks multi-página)"
    )

    # Informações de seção/cláusula
    section_title: Optional[str] = Field(
        default=None,
        description="Título da seção detectada (ex: 'CLÁUSULA 5 - CARÊNCIAS')"
    )
    section_number: Optional[str] = Field(
        default=None,
        description="Número da seção/cláusula (ex: '5.1', '5.2.1')"
    )
    section_type: Optional[str] = Field(
        default=None,
        description="Tipo de seção (ex: 'clausula', 'paragrafo', 'anexo')"
    )

    # Metadados de processamento
    chunk_index: int = Field(
        ...,
        description="Índice do chunk no documento (0-indexed)"
    )
    total_chunks: Optional[int] = Field(
        default=None,
        description="Total de chunks do documento"
    )
    strategy: ChunkingStrategy = Field(
        default=ChunkingStrategy.HYBRID,
        description="Estratégia usada para criar este chunk"
    )

    # Contexto adicional (para melhorar retrieval)
    previous_chunk_id: Optional[UUID] = Field(
        default=None,
        description="ID do chunk anterior (para contexto)"
    )
    next_chunk_id: Optional[UUID] = Field(
        default=None,
        description="ID do próximo chunk (para contexto)"
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Data de criação do chunk"
    )

    def __init__(self, **data):
        super().__init__(**data)
        # Calcula content_length automaticamente
        if self.content and self.content_length == 0:
            object.__setattr__(self, 'content_length', len(self.content))

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


class ProcessingResult(BaseModel):
    """
    Resultado do processamento de um documento.

    Retornado após extrair texto, criar chunks e indexar.
    """

    document_id: UUID = Field(..., description="ID do documento processado")
    success: bool = Field(..., description="Se o processamento foi bem-sucedido")

    # Estatísticas
    total_pages: int = Field(default=0, description="Total de páginas do PDF")
    total_chunks: int = Field(default=0, description="Total de chunks criados")
    total_characters: int = Field(default=0, description="Total de caracteres extraídos")

    # Chunks criados
    chunks: list[DocumentChunk] = Field(
        default_factory=list,
        description="Lista de chunks extraídos"
    )

    # Informações de indexação
    indexed_count: Optional[int] = Field(
        default=None,
        description="Número de chunks indexados no Azure AI Search"
    )

    # Informações de erro (se houver)
    error_message: Optional[str] = Field(
        default=None,
        description="Mensagem de erro se success=False"
    )

    # Tempo de processamento
    processing_time_seconds: Optional[float] = Field(
        default=None,
        description="Tempo de processamento em segundos"
    )


class ChunkingConfig(BaseModel):
    """
    Configurações para o processo de chunking.

    Permite customizar como os documentos são divididos.
    """

    # Estratégia principal
    strategy: ChunkingStrategy = Field(
        default=ChunkingStrategy.HYBRID,
        description="Estratégia de chunking"
    )

    # Configurações de tamanho (para FIXED_SIZE e fallback)
    chunk_size: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Tamanho alvo do chunk em caracteres"
    )
    chunk_overlap: int = Field(
        default=200,
        ge=0,
        le=500,
        description="Sobreposição entre chunks consecutivos"
    )

    # Configurações de seção
    detect_sections: bool = Field(
        default=True,
        description="Tentar detectar seções/cláusulas"
    )
    min_section_length: int = Field(
        default=100,
        description="Tamanho mínimo para considerar uma seção"
    )
    max_section_length: int = Field(
        default=5000,
        description="Tamanho máximo de seção (divide se maior)"
    )

    # Limpeza de texto
    remove_headers_footers: bool = Field(
        default=True,
        description="Remover cabeçalhos e rodapés repetidos"
    )
    normalize_whitespace: bool = Field(
        default=True,
        description="Normalizar espaços em branco"
    )


# Configuração padrão
DEFAULT_CHUNKING_CONFIG = ChunkingConfig()
