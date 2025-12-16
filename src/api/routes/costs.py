"""
Endpoints de consulta e análise de dados de custos.

Responsável por:
- Processamento de arquivos de custos
- Consulta de registros
- Agregações e análises
"""

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.config.logging import get_logger
from src.ingestion.cost_processor import get_cost_processor
from src.models.costs import CostCategory, CostProcessingResult
from src.storage.cosmos_db import get_cosmos_client

logger = get_logger(__name__)

router = APIRouter(prefix="/costs", tags=["costs"])


# ============================================================
# Modelos de Request/Response
# ============================================================


class ProcessCostsRequest(BaseModel):
    """Request para processar um documento de custos."""

    document_id: UUID = Field(..., description="ID do documento a processar")
    client_id: str = Field(..., description="ID do cliente")


class ProcessCostsResponse(BaseModel):
    """Response do processamento de custos."""

    success: bool
    document_id: UUID
    total_rows: int = 0
    processed_rows: int = 0
    error_rows: int = 0
    total_charged: Optional[float] = None
    total_paid: Optional[float] = None
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None
    processing_time_seconds: Optional[float] = None
    error_message: Optional[str] = None
    message: str = ""


class CostRecordResponse(BaseModel):
    """Registro de custo para resposta da API."""

    id: str
    service_date: date
    procedure_description: str
    procedure_code: Optional[str] = None
    beneficiary_name: Optional[str] = None
    provider_name: Optional[str] = None
    charged_amount: float
    paid_amount: float
    category: str


class CostRecordsListResponse(BaseModel):
    """Lista de registros de custos."""

    client_id: str
    records: list[CostRecordResponse]
    total: int
    limit: int
    offset: int


class CostSummaryResponse(BaseModel):
    """Resumo de custos."""

    client_id: str
    contract_id: Optional[str] = None
    total_records: int
    total_charged: float
    total_paid: float
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    by_category: list[dict] = []


# ============================================================
# Endpoint: Processar Documento de Custos
# ============================================================


@router.post(
    "/process",
    response_model=ProcessCostsResponse,
    status_code=status.HTTP_200_OK,
    summary="Processar documento de custos",
    description="""
    Processa um arquivo de custos (CSV/Excel) que já foi enviado via upload.

    O processamento inclui:
    1. Download do arquivo do Blob Storage
    2. Validação de colunas
    3. Normalização de dados
    4. Armazenamento dos registros no Cosmos DB
    """,
)
async def process_costs_document(
    request: ProcessCostsRequest,
) -> ProcessCostsResponse:
    """
    Processa um documento de custos.

    Args:
        request: Contém document_id e client_id

    Returns:
        ProcessCostsResponse com estatísticas do processamento

    Raises:
        HTTPException 404: Se documento não encontrado
        HTTPException 500: Se erro no processamento
    """
    logger.info(
        "Iniciando processamento de custos",
        document_id=str(request.document_id),
        client_id=request.client_id,
    )

    try:
        processor = get_cost_processor()
        result = await processor.process_document(
            document_id=request.document_id,
            client_id=request.client_id,
        )

        if not result.success:
            return ProcessCostsResponse(
                success=False,
                document_id=result.document_id,
                error_message=result.error_message,
                message=f"Falha no processamento: {result.error_message}",
            )

        return ProcessCostsResponse(
            success=True,
            document_id=result.document_id,
            total_rows=result.total_rows,
            processed_rows=result.processed_rows,
            error_rows=result.error_rows,
            total_charged=float(result.total_charged) if result.total_charged else None,
            total_paid=float(result.total_paid) if result.total_paid else None,
            date_range_start=result.date_range_start,
            date_range_end=result.date_range_end,
            processing_time_seconds=result.processing_time_seconds,
            message=f"Processamento concluído. {result.processed_rows} registros criados.",
        )

    except Exception as e:
        logger.error(
            "Erro no processamento de custos",
            document_id=str(request.document_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro no processamento: {str(e)}",
        )


# ============================================================
# Endpoint: Listar Registros de Custos
# ============================================================


@router.get(
    "/records",
    response_model=CostRecordsListResponse,
    summary="Listar registros de custos",
    description="""
    Lista registros de custos de um cliente com filtros opcionais.

    Suporta paginação e filtros por:
    - contract_id
    - date_start / date_end
    - category
    """,
)
async def list_cost_records(
    client_id: str = Query(..., description="ID do cliente"),
    contract_id: Optional[str] = Query(None, description="Filtrar por contrato"),
    date_start: Optional[date] = Query(None, description="Data inicial"),
    date_end: Optional[date] = Query(None, description="Data final"),
    category: Optional[CostCategory] = Query(None, description="Filtrar por categoria"),
    limit: int = Query(100, ge=1, le=1000, description="Máximo de registros"),
    offset: int = Query(0, ge=0, description="Pular N primeiros registros"),
) -> CostRecordsListResponse:
    """
    Lista registros de custos.

    Args:
        client_id: ID do cliente
        contract_id: Filtrar por contrato (opcional)
        date_start: Data inicial (opcional)
        date_end: Data final (opcional)
        category: Filtrar por categoria (opcional)
        limit: Máximo de registros (default: 100, max: 1000)
        offset: Pular primeiros N registros

    Returns:
        Lista de registros com informações de paginação
    """
    logger.info(
        "Listando registros de custos",
        client_id=client_id,
        limit=limit,
        offset=offset,
    )

    try:
        cosmos_client = get_cosmos_client()
        records = await cosmos_client.get_cost_records_by_client(
            client_id=client_id,
            contract_id=contract_id,
            date_start=date_start,
            date_end=date_end,
            category=category.value if category else None,
            limit=limit,
            offset=offset,
        )

        # Converte para modelo de resposta
        response_records = [
            CostRecordResponse(
                id=str(r.get("id")),
                service_date=r.get("service_date"),
                procedure_description=r.get("procedure_description", ""),
                procedure_code=r.get("procedure_code"),
                beneficiary_name=r.get("beneficiary_name"),
                provider_name=r.get("provider_name"),
                charged_amount=float(r.get("charged_amount", 0)),
                paid_amount=float(r.get("paid_amount", 0)),
                category=r.get("category", "outros"),
            )
            for r in records
        ]

        return CostRecordsListResponse(
            client_id=client_id,
            records=response_records,
            total=len(response_records),
            limit=limit,
            offset=offset,
        )

    except Exception as e:
        logger.error(
            "Erro ao listar registros de custos",
            client_id=client_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar registros: {str(e)}",
        )


# ============================================================
# Endpoint: Resumo de Custos
# ============================================================


@router.get(
    "/summary",
    response_model=CostSummaryResponse,
    summary="Resumo de custos",
    description="""
    Retorna um resumo agregado dos custos de um cliente.

    Inclui:
    - Totais (registros, valores cobrados, valores pagos)
    - Período dos dados
    - Agregação por categoria
    """,
)
async def get_cost_summary(
    client_id: str = Query(..., description="ID do cliente"),
    contract_id: Optional[str] = Query(None, description="Filtrar por contrato"),
) -> CostSummaryResponse:
    """
    Retorna resumo de custos.

    Args:
        client_id: ID do cliente
        contract_id: Filtrar por contrato (opcional)

    Returns:
        Resumo com totais e agregações
    """
    logger.info(
        "Buscando resumo de custos",
        client_id=client_id,
        contract_id=contract_id,
    )

    try:
        cosmos_client = get_cosmos_client()

        # Busca resumo geral
        summary = await cosmos_client.get_cost_summary(
            client_id=client_id,
            contract_id=contract_id,
        )

        # Busca agregação por categoria
        by_category = await cosmos_client.get_cost_by_category(
            client_id=client_id,
            contract_id=contract_id,
        )

        return CostSummaryResponse(
            client_id=client_id,
            contract_id=contract_id,
            total_records=summary.get("total_records", 0),
            total_charged=float(summary.get("total_charged", 0) or 0),
            total_paid=float(summary.get("total_paid", 0) or 0),
            date_start=summary.get("date_start"),
            date_end=summary.get("date_end"),
            by_category=by_category,
        )

    except Exception as e:
        logger.error(
            "Erro ao buscar resumo de custos",
            client_id=client_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar resumo: {str(e)}",
        )


# ============================================================
# Endpoint: Registros por Documento
# ============================================================


@router.get(
    "/by-document/{document_id}",
    response_model=CostRecordsListResponse,
    summary="Registros por documento",
    description="Lista registros de custos de um documento específico.",
)
async def get_costs_by_document(
    document_id: UUID,
    client_id: str = Query(..., description="ID do cliente"),
    limit: int = Query(100, ge=1, le=1000),
) -> CostRecordsListResponse:
    """
    Lista registros de um documento específico.

    Args:
        document_id: ID do documento
        client_id: ID do cliente
        limit: Máximo de registros

    Returns:
        Lista de registros do documento
    """
    logger.info(
        "Buscando registros por documento",
        document_id=str(document_id),
        client_id=client_id,
    )

    try:
        cosmos_client = get_cosmos_client()
        records = await cosmos_client.get_cost_records_by_document(
            document_id=document_id,
            client_id=client_id,
            limit=limit,
        )

        response_records = [
            CostRecordResponse(
                id=str(r.get("id")),
                service_date=r.get("service_date"),
                procedure_description=r.get("procedure_description", ""),
                procedure_code=r.get("procedure_code"),
                beneficiary_name=r.get("beneficiary_name"),
                provider_name=r.get("provider_name"),
                charged_amount=float(r.get("charged_amount", 0)),
                paid_amount=float(r.get("paid_amount", 0)),
                category=r.get("category", "outros"),
            )
            for r in records
        ]

        return CostRecordsListResponse(
            client_id=client_id,
            records=response_records,
            total=len(response_records),
            limit=limit,
            offset=0,
        )

    except Exception as e:
        logger.error(
            "Erro ao buscar registros por documento",
            document_id=str(document_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar registros: {str(e)}",
        )
