"""
Endpoints de busca semântica.

Endpoints para busca de chunks de contratos usando:
- Busca vetorial (similaridade semântica)
- Busca por keywords
- Busca híbrida (combinação)
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from uuid import UUID

from src.config.logging import get_logger
from src.models.search import (
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    SearchModeEnum,
    SimilarChunksRequest,
)
from src.search.search_service import (
    get_search_service,
    SearchMode,
    SearchResponse as ServiceSearchResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


def _convert_service_response(
    service_response: ServiceSearchResponse,
) -> SearchResponse:
    """Converte resposta do serviço para modelo Pydantic da API."""
    return SearchResponse(
        results=[
            SearchResultItem(
                id=r.id,
                document_id=r.document_id,
                client_id=r.client_id,
                content=r.content,
                content_length=r.content_length,
                page_number=r.page_number,
                page_start=r.page_start,
                page_end=r.page_end,
                section_title=r.section_title,
                section_number=r.section_number,
                section_type=r.section_type,
                chunk_index=r.chunk_index,
                total_chunks=r.total_chunks,
                score=r.score,
                vector_score=r.vector_score,
                keyword_score=r.keyword_score,
                reranker_score=r.reranker_score,
                created_at=r.created_at,
            )
            for r in service_response.results
        ],
        total_count=service_response.total_count,
        query=service_response.query,
        mode=SearchModeEnum(service_response.mode.value),
        filters_applied=service_response.filters_applied,
        search_time_ms=service_response.search_time_ms,
    )


@router.post(
    "/",
    response_model=SearchResponse,
    summary="Buscar chunks de contratos",
    description="""
Busca semântica em chunks de contratos.

## Modos de busca

- **hybrid** (recomendado): Combina busca vetorial com keywords para melhor precisão
- **vector**: Busca por similaridade semântica (entende sinônimos e contexto)
- **keyword**: Busca tradicional por palavras-chave

## Exemplos de uso

### Busca simples
```json
{
    "query": "qual o prazo de carência?",
    "client_id": "cliente-123"
}
```

### Busca em documento específico
```json
{
    "query": "cobertura hospitalar",
    "client_id": "cliente-123",
    "document_id": "550e8400-e29b-41d4-a716-446655440001",
    "mode": "hybrid",
    "top": 5
}
```

### Busca por tipo de seção
```json
{
    "query": "exclusões",
    "client_id": "cliente-123",
    "section_type": "clausula"
}
```
    """,
)
async def search_chunks(request: SearchRequest) -> SearchResponse:
    """
    Busca chunks de contratos.

    Retorna chunks relevantes para a query, ordenados por relevância.
    """
    logger.info(
        "Requisição de busca recebida",
        query=request.query[:50],
        client_id=request.client_id,
        mode=request.mode.value,
    )

    try:
        search_service = get_search_service()

        # Converter enum da API para enum do serviço
        mode_map = {
            SearchModeEnum.VECTOR: SearchMode.VECTOR,
            SearchModeEnum.KEYWORD: SearchMode.KEYWORD,
            SearchModeEnum.HYBRID: SearchMode.HYBRID,
        }

        result = await search_service.search(
            query=request.query,
            client_id=request.client_id,
            document_id=request.document_id,
            section_type=request.section_type,
            mode=mode_map[request.mode],
            top=request.top,
            min_score=request.min_score,
        )

        response = _convert_service_response(result)

        logger.info(
            "Busca concluída",
            results_count=response.total_count,
            search_time_ms=response.search_time_ms,
        )

        return response

    except ValueError as e:
        logger.warning("Erro de validação na busca", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error("Erro na busca", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao realizar busca: {str(e)}",
        )


@router.get(
    "/",
    response_model=SearchResponse,
    summary="Buscar chunks (GET)",
    description="Versão GET do endpoint de busca para facilitar testes.",
)
async def search_chunks_get(
    query: str = Query(..., min_length=1, description="Texto da busca"),
    client_id: str = Query(..., description="ID do cliente"),
    document_id: Optional[UUID] = Query(None, description="ID do documento"),
    section_type: Optional[str] = Query(None, description="Tipo de seção"),
    mode: SearchModeEnum = Query(SearchModeEnum.HYBRID, description="Modo de busca"),
    top: int = Query(10, ge=1, le=50, description="Número de resultados"),
    min_score: float = Query(0.0, ge=0.0, le=1.0, description="Score mínimo"),
) -> SearchResponse:
    """Busca chunks via GET (facilita testes no navegador)."""
    request = SearchRequest(
        query=query,
        client_id=client_id,
        document_id=document_id,
        section_type=section_type,
        mode=mode,
        top=top,
        min_score=min_score,
    )
    return await search_chunks(request)


@router.post(
    "/similar",
    response_model=SearchResponse,
    summary="Buscar chunks similares",
    description="""
Encontra chunks similares a um chunk específico.

Útil para:
- Encontrar cláusulas similares em outros contratos
- Comparar termos entre diferentes documentos
- Identificar padrões contratuais

## Exemplo

```json
{
    "chunk_id": "550e8400-e29b-41d4-a716-446655440000",
    "client_id": "cliente-123",
    "top": 5,
    "exclude_same_document": true
}
```
    """,
)
async def search_similar_chunks(request: SimilarChunksRequest) -> SearchResponse:
    """
    Busca chunks similares a um chunk de referência.

    Retorna chunks com conteúdo semanticamente similar.
    """
    logger.info(
        "Busca por chunks similares",
        chunk_id=request.chunk_id,
        client_id=request.client_id,
    )

    try:
        search_service = get_search_service()

        result = await search_service.get_similar_chunks(
            chunk_id=request.chunk_id,
            client_id=request.client_id,
            top=request.top,
            exclude_same_document=request.exclude_same_document,
        )

        response = _convert_service_response(result)

        logger.info(
            "Busca por similares concluída",
            results_count=response.total_count,
        )

        return response

    except Exception as e:
        logger.error("Erro na busca por similares", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao buscar chunks similares: {str(e)}",
        )


@router.get(
    "/vector",
    response_model=SearchResponse,
    summary="Busca vetorial pura",
    description="Busca apenas por similaridade semântica (sem keywords).",
)
async def vector_search(
    query: str = Query(..., min_length=1, description="Texto da busca"),
    client_id: str = Query(..., description="ID do cliente"),
    document_id: Optional[UUID] = Query(None, description="ID do documento"),
    top: int = Query(10, ge=1, le=50, description="Número de resultados"),
) -> SearchResponse:
    """Busca vetorial pura."""
    search_service = get_search_service()

    result = await search_service.vector_search(
        query=query,
        client_id=client_id,
        document_id=document_id,
        top=top,
    )

    return _convert_service_response(result)


@router.get(
    "/keyword",
    response_model=SearchResponse,
    summary="Busca por keywords",
    description="Busca tradicional por palavras-chave.",
)
async def keyword_search(
    query: str = Query(..., min_length=1, description="Texto da busca"),
    client_id: str = Query(..., description="ID do cliente"),
    document_id: Optional[UUID] = Query(None, description="ID do documento"),
    top: int = Query(10, ge=1, le=50, description="Número de resultados"),
) -> SearchResponse:
    """Busca por keywords."""
    search_service = get_search_service()

    result = await search_service.keyword_search(
        query=query,
        client_id=client_id,
        document_id=document_id,
        top=top,
    )

    return _convert_service_response(result)
