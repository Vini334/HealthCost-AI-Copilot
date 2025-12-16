"""
Endpoints para gerenciamento e processamento de documentos.

Responsável por:
- Listar documentos de um cliente
- Acionar processamento de documentos
- Consultar status de processamento
- Buscar detalhes de um documento
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.config.logging import get_logger
from src.ingestion.contract_processor import get_contract_processor
from src.models.chunks import ProcessingResult, DocumentChunk
from src.models.documents import DocumentMetadata, DocumentStatus, DocumentType
from src.storage.cosmos_db import get_cosmos_client

logger = get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


# ============================================================
# Modelos de Request/Response
# ============================================================

class ProcessDocumentRequest(BaseModel):
    """Request para processar um documento."""
    document_id: UUID = Field(..., description="ID do documento a processar")
    client_id: str = Field(..., description="ID do cliente")


class ProcessDocumentResponse(BaseModel):
    """Resposta do processamento de documento."""
    success: bool
    document_id: UUID
    message: str
    total_pages: Optional[int] = None
    total_chunks: Optional[int] = None
    processing_time_seconds: Optional[float] = None
    error_message: Optional[str] = None


class DocumentListResponse(BaseModel):
    """Lista de documentos."""
    client_id: str
    documents: list[DocumentMetadata]
    total: int


class DocumentDetailResponse(BaseModel):
    """Detalhes de um documento com chunks (se processado)."""
    document: DocumentMetadata
    chunks: Optional[list[DocumentChunk]] = None
    total_chunks: int = 0


# ============================================================
# ENDPOINTS
# ============================================================

@router.get(
    "/",
    response_model=DocumentListResponse,
    summary="Listar documentos",
    description="Lista todos os documentos de um cliente, com filtros opcionais.",
)
async def list_documents(
    client_id: str = Query(..., description="ID do cliente"),
    document_type: Optional[str] = Query(
        None,
        description="Filtrar por tipo: 'contract' ou 'cost_data'"
    ),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filtrar por status: 'uploaded', 'processing', 'indexed', 'failed'"
    ),
    limit: int = Query(100, ge=1, le=500, description="Máximo de resultados"),
) -> DocumentListResponse:
    """
    Lista documentos de um cliente.

    Permite filtrar por tipo e status para facilitar a gestão.

    Exemplo:
        GET /api/v1/documents/?client_id=cliente-123&status=uploaded
    """
    logger.info(
        "Listando documentos",
        client_id=client_id,
        document_type=document_type,
        status=status_filter,
    )

    # Converte status string para enum se fornecido
    status_enum = None
    if status_filter:
        try:
            status_enum = DocumentStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Status inválido: {status_filter}. "
                       f"Use: uploaded, processing, indexed, failed"
            )

    cosmos_client = get_cosmos_client()
    documents = await cosmos_client.list_documents_by_client(
        client_id=client_id,
        document_type=document_type,
        status=status_enum,
        limit=limit,
    )

    return DocumentListResponse(
        client_id=client_id,
        documents=documents,
        total=len(documents),
    )


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    summary="Detalhes de documento",
    description="Retorna detalhes de um documento específico.",
)
async def get_document(
    document_id: UUID,
    client_id: str = Query(..., description="ID do cliente"),
) -> DocumentDetailResponse:
    """
    Busca detalhes de um documento.

    Retorna metadados e, se já processado, informações dos chunks.
    """
    logger.info(
        "Buscando documento",
        document_id=str(document_id),
        client_id=client_id,
    )

    cosmos_client = get_cosmos_client()
    document = await cosmos_client.get_document_metadata(
        document_id=str(document_id),
        client_id=client_id,
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento não encontrado"
        )

    # Por ora, chunks não são persistidos no Cosmos
    # Serão adicionados quando implementarmos a indexação
    return DocumentDetailResponse(
        document=document,
        chunks=None,
        total_chunks=0,
    )


@router.post(
    "/process",
    response_model=ProcessDocumentResponse,
    summary="Processar documento",
    description="""
    Aciona o processamento de um documento já uploaded.

    O processamento inclui:
    1. Download do PDF do Blob Storage
    2. Extração de texto
    3. Criação de chunks
    4. (Futuro) Geração de embeddings e indexação

    O status do documento é atualizado automaticamente.
    """,
)
async def process_document(
    request: ProcessDocumentRequest,
) -> ProcessDocumentResponse:
    """
    Processa um documento (extração + chunking).

    Use este endpoint para processar documentos que foram
    uploaded mas ainda não processados.

    Exemplo de chamada:
        POST /api/v1/documents/process
        {
            "document_id": "abc-123-...",
            "client_id": "cliente-456"
        }
    """
    logger.info(
        "Solicitação de processamento",
        document_id=str(request.document_id),
        client_id=request.client_id,
    )

    # Verifica se documento existe
    cosmos_client = get_cosmos_client()
    document = await cosmos_client.get_document_metadata(
        document_id=str(request.document_id),
        client_id=request.client_id,
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento não encontrado"
        )

    # Verifica se é um contrato (por ora só processamos contratos)
    if document.document_type != DocumentType.CONTRACT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Por enquanto, apenas contratos PDF podem ser processados"
        )

    # Verifica se já está sendo processado
    if document.status == DocumentStatus.PROCESSING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Documento já está em processamento"
        )

    # Processa o documento
    processor = get_contract_processor()
    result = await processor.process_document(
        document_id=request.document_id,
        client_id=request.client_id,
    )

    if result.success:
        return ProcessDocumentResponse(
            success=True,
            document_id=request.document_id,
            message="Documento processado com sucesso",
            total_pages=result.total_pages,
            total_chunks=result.total_chunks,
            processing_time_seconds=result.processing_time_seconds,
        )
    else:
        return ProcessDocumentResponse(
            success=False,
            document_id=request.document_id,
            message="Falha no processamento",
            error_message=result.error_message,
            processing_time_seconds=result.processing_time_seconds,
        )


@router.post(
    "/{document_id}/reprocess",
    response_model=ProcessDocumentResponse,
    summary="Reprocessar documento",
    description="Força o reprocessamento de um documento, mesmo que já tenha sido processado.",
)
async def reprocess_document(
    document_id: UUID,
    client_id: str = Query(..., description="ID do cliente"),
) -> ProcessDocumentResponse:
    """
    Reprocessa um documento.

    Útil quando:
    - Processamento anterior falhou
    - Configurações de chunking mudaram
    - Quer atualizar os chunks
    """
    logger.info(
        "Solicitação de reprocessamento",
        document_id=str(document_id),
        client_id=client_id,
    )

    # Reseta status para UPLOADED antes de reprocessar
    cosmos_client = get_cosmos_client()
    document = await cosmos_client.get_document_metadata(
        document_id=str(document_id),
        client_id=client_id,
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento não encontrado"
        )

    # Atualiza status para UPLOADED (reseta)
    await cosmos_client.update_document_status(
        document_id=str(document_id),
        client_id=client_id,
        status=DocumentStatus.UPLOADED,
    )

    # Processa
    processor = get_contract_processor()
    result = await processor.process_document(
        document_id=document_id,
        client_id=client_id,
    )

    if result.success:
        return ProcessDocumentResponse(
            success=True,
            document_id=document_id,
            message="Documento reprocessado com sucesso",
            total_pages=result.total_pages,
            total_chunks=result.total_chunks,
            processing_time_seconds=result.processing_time_seconds,
        )
    else:
        return ProcessDocumentResponse(
            success=False,
            document_id=document_id,
            message="Falha no reprocessamento",
            error_message=result.error_message,
            processing_time_seconds=result.processing_time_seconds,
        )
