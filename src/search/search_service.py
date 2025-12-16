"""
Serviço de busca semântica no Azure AI Search.

Este módulo implementa:
- Busca vetorial (similaridade semântica)
- Busca híbrida (vetorial + keyword)
- Filtros por client_id e contract_id
- Re-ranking de resultados
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

from src.config.logging import get_logger
from src.config.settings import get_settings
from src.search.embedding_service import get_embedding_service, EMBEDDING_DIMENSION

logger = get_logger(__name__)


class SearchMode(str, Enum):
    """Modo de busca."""
    VECTOR = "vector"           # Apenas busca vetorial
    KEYWORD = "keyword"         # Apenas busca por keywords
    HYBRID = "hybrid"           # Vetorial + Keyword combinados


@dataclass
class SearchResult:
    """
    Resultado individual de uma busca.

    Contém o chunk encontrado e metadados de relevância.
    """
    # Identificação
    id: str
    document_id: str
    client_id: str

    # Conteúdo
    content: str
    content_length: int

    # Localização no documento
    page_number: Optional[int]
    page_start: Optional[int]
    page_end: Optional[int]
    section_title: Optional[str]
    section_number: Optional[str]
    section_type: Optional[str]

    # Metadados de busca
    chunk_index: int
    total_chunks: Optional[int]

    # Scores de relevância
    score: float                    # Score combinado/principal
    vector_score: Optional[float]   # Score da busca vetorial
    keyword_score: Optional[float]  # Score da busca por keyword
    reranker_score: Optional[float] # Score após re-ranking

    # Timestamps
    created_at: Optional[datetime]

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "client_id": self.client_id,
            "content": self.content,
            "content_length": self.content_length,
            "page_number": self.page_number,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "section_title": self.section_title,
            "section_number": self.section_number,
            "section_type": self.section_type,
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
            "score": self.score,
            "vector_score": self.vector_score,
            "keyword_score": self.keyword_score,
            "reranker_score": self.reranker_score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class SearchResponse:
    """
    Resposta completa de uma busca.

    Contém os resultados e metadados da busca.
    """
    results: List[SearchResult]
    total_count: int
    query: str
    mode: SearchMode
    filters_applied: Dict[str, str]
    search_time_ms: float

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "results": [r.to_dict() for r in self.results],
            "total_count": self.total_count,
            "query": self.query,
            "mode": self.mode.value,
            "filters_applied": self.filters_applied,
            "search_time_ms": self.search_time_ms,
        }


class SearchService:
    """
    Serviço de busca semântica.

    Implementa busca vetorial, híbrida e por keywords no Azure AI Search.

    Exemplo:
        service = SearchService()

        # Busca híbrida (recomendada)
        response = await service.search(
            query="qual o prazo de carência?",
            client_id="cliente-123",
            mode=SearchMode.HYBRID,
        )

        # Busca apenas vetorial
        response = await service.vector_search(
            query="cobertura hospitalar",
            client_id="cliente-123",
        )
    """

    def __init__(self):
        """Inicializa o serviço de busca."""
        settings = get_settings()

        self.search_client = SearchClient(
            endpoint=settings.azure_search.endpoint,
            index_name=settings.azure_search.index_name,
            credential=AzureKeyCredential(settings.azure_search.api_key),
        )
        self.embedding_service = get_embedding_service()
        self.index_name = settings.azure_search.index_name

        logger.info(
            "SearchService inicializado",
            index_name=self.index_name,
        )

    def _build_filter(
        self,
        client_id: str,
        document_id: Optional[Union[str, UUID]] = None,
        section_type: Optional[str] = None,
    ) -> str:
        """
        Constrói string de filtro OData para Azure AI Search.

        Args:
            client_id: ID do cliente (obrigatório para multi-tenancy)
            document_id: Filtrar por documento específico
            section_type: Filtrar por tipo de seção

        Returns:
            String de filtro OData
        """
        filters = [f"client_id eq '{client_id}'"]

        if document_id:
            doc_id = str(document_id)
            filters.append(f"document_id eq '{doc_id}'")

        if section_type:
            filters.append(f"section_type eq '{section_type}'")

        return " and ".join(filters)

    def _parse_result(self, result: Dict[str, Any], mode: SearchMode) -> SearchResult:
        """
        Converte resultado do Azure AI Search para SearchResult.

        Args:
            result: Resultado bruto do Azure AI Search
            mode: Modo de busca utilizado

        Returns:
            SearchResult formatado
        """
        # Extrair scores conforme o modo
        score = result.get("@search.score", 0.0)
        vector_score = None
        keyword_score = None
        reranker_score = result.get("@search.reranker_score")

        # Em busca híbrida, o score é uma combinação
        if mode == SearchMode.VECTOR:
            vector_score = score
        elif mode == SearchMode.KEYWORD:
            keyword_score = score
        else:  # HYBRID
            # Azure AI Search combina os scores automaticamente
            vector_score = score
            keyword_score = score

        # Parse de data
        created_at = None
        if result.get("created_at"):
            try:
                created_at = datetime.fromisoformat(
                    result["created_at"].replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                pass

        return SearchResult(
            id=result.get("id", ""),
            document_id=result.get("document_id", ""),
            client_id=result.get("client_id", ""),
            content=result.get("content", ""),
            content_length=result.get("content_length", 0),
            page_number=result.get("page_number"),
            page_start=result.get("page_start"),
            page_end=result.get("page_end"),
            section_title=result.get("section_title"),
            section_number=result.get("section_number"),
            section_type=result.get("section_type"),
            chunk_index=result.get("chunk_index", 0),
            total_chunks=result.get("total_chunks"),
            score=score,
            vector_score=vector_score,
            keyword_score=keyword_score,
            reranker_score=reranker_score,
            created_at=created_at,
        )

    def _rerank_results(
        self,
        results: List[SearchResult],
        query: str,
    ) -> List[SearchResult]:
        """
        Re-rankeia resultados para melhorar relevância.

        Aplica heurísticas adicionais:
        1. Boost para chunks com título de seção que contém palavras da query
        2. Boost para primeiros chunks de seções (geralmente mais informativos)
        3. Penalidade para chunks muito curtos

        Args:
            results: Lista de resultados
            query: Query original

        Returns:
            Lista re-rankeada
        """
        if not results:
            return results

        query_words = set(query.lower().split())

        for result in results:
            boost = 0.0

            # Boost para título de seção com palavras da query
            if result.section_title:
                title_words = set(result.section_title.lower().split())
                overlap = len(query_words & title_words)
                if overlap > 0:
                    boost += 0.1 * overlap

            # Boost para primeiros chunks de seção (índice baixo)
            if result.chunk_index < 3:
                boost += 0.05 * (3 - result.chunk_index)

            # Penalidade para chunks muito curtos (menos informativos)
            if result.content_length < 200:
                boost -= 0.1

            # Aplicar boost ao score
            result.reranker_score = result.score + boost

        # Ordenar por reranker_score
        results.sort(key=lambda r: r.reranker_score or r.score, reverse=True)

        return results

    async def vector_search(
        self,
        query: str,
        client_id: str,
        document_id: Optional[Union[str, UUID]] = None,
        section_type: Optional[str] = None,
        top: int = 10,
        min_score: float = 0.0,
    ) -> SearchResponse:
        """
        Busca vetorial (similaridade semântica).

        Converte a query em embedding e busca chunks similares.

        Args:
            query: Texto da pergunta/busca
            client_id: ID do cliente (obrigatório)
            document_id: Filtrar por documento específico
            section_type: Filtrar por tipo de seção
            top: Número máximo de resultados
            min_score: Score mínimo para incluir resultado

        Returns:
            SearchResponse com resultados
        """
        import asyncio
        import time

        start_time = time.time()

        logger.info(
            "Iniciando busca vetorial",
            query=query[:100],
            client_id=client_id,
            document_id=str(document_id) if document_id else None,
        )

        # 1. Gerar embedding da query
        query_embedding = await self.embedding_service.get_embedding(query)

        # 2. Construir filtro
        filter_str = self._build_filter(client_id, document_id, section_type)

        # 3. Criar query vetorial
        vector_query = VectorizedQuery(
            vector=query_embedding,
            k_nearest_neighbors=top,
            fields="content_vector",
        )

        # 4. Executar busca
        loop = asyncio.get_event_loop()
        search_results = await loop.run_in_executor(
            None,
            lambda: list(self.search_client.search(
                search_text=None,
                vector_queries=[vector_query],
                filter=filter_str,
                select=[
                    "id", "document_id", "client_id", "content", "content_length",
                    "page_number", "page_start", "page_end",
                    "section_title", "section_number", "section_type",
                    "chunk_index", "total_chunks", "created_at",
                ],
                top=top,
            )),
        )

        # 5. Processar resultados
        results = [
            self._parse_result(r, SearchMode.VECTOR)
            for r in search_results
            if r.get("@search.score", 0) >= min_score
        ]

        # 6. Aplicar re-ranking
        results = self._rerank_results(results, query)

        search_time = (time.time() - start_time) * 1000

        logger.info(
            "Busca vetorial concluída",
            results_count=len(results),
            search_time_ms=round(search_time, 2),
        )

        return SearchResponse(
            results=results,
            total_count=len(results),
            query=query,
            mode=SearchMode.VECTOR,
            filters_applied={
                "client_id": client_id,
                "document_id": str(document_id) if document_id else None,
                "section_type": section_type,
            },
            search_time_ms=search_time,
        )

    async def keyword_search(
        self,
        query: str,
        client_id: str,
        document_id: Optional[Union[str, UUID]] = None,
        section_type: Optional[str] = None,
        top: int = 10,
    ) -> SearchResponse:
        """
        Busca por keywords (texto).

        Busca tradicional por palavras-chave usando analyzer português.

        Args:
            query: Texto da busca
            client_id: ID do cliente (obrigatório)
            document_id: Filtrar por documento específico
            section_type: Filtrar por tipo de seção
            top: Número máximo de resultados

        Returns:
            SearchResponse com resultados
        """
        import asyncio
        import time

        start_time = time.time()

        logger.info(
            "Iniciando busca por keywords",
            query=query[:100],
            client_id=client_id,
        )

        # 1. Construir filtro
        filter_str = self._build_filter(client_id, document_id, section_type)

        # 2. Executar busca
        loop = asyncio.get_event_loop()
        search_results = await loop.run_in_executor(
            None,
            lambda: list(self.search_client.search(
                search_text=query,
                filter=filter_str,
                select=[
                    "id", "document_id", "client_id", "content", "content_length",
                    "page_number", "page_start", "page_end",
                    "section_title", "section_number", "section_type",
                    "chunk_index", "total_chunks", "created_at",
                ],
                top=top,
                query_type="simple",
            )),
        )

        # 3. Processar resultados
        results = [
            self._parse_result(r, SearchMode.KEYWORD)
            for r in search_results
        ]

        # 4. Aplicar re-ranking
        results = self._rerank_results(results, query)

        search_time = (time.time() - start_time) * 1000

        logger.info(
            "Busca por keywords concluída",
            results_count=len(results),
            search_time_ms=round(search_time, 2),
        )

        return SearchResponse(
            results=results,
            total_count=len(results),
            query=query,
            mode=SearchMode.KEYWORD,
            filters_applied={
                "client_id": client_id,
                "document_id": str(document_id) if document_id else None,
                "section_type": section_type,
            },
            search_time_ms=search_time,
        )

    async def hybrid_search(
        self,
        query: str,
        client_id: str,
        document_id: Optional[Union[str, UUID]] = None,
        section_type: Optional[str] = None,
        top: int = 10,
        min_score: float = 0.0,
    ) -> SearchResponse:
        """
        Busca híbrida (vetorial + keyword).

        Combina busca semântica com busca por keywords para melhor precisão.
        Recomendada para a maioria dos casos de uso.

        Args:
            query: Texto da pergunta/busca
            client_id: ID do cliente (obrigatório)
            document_id: Filtrar por documento específico
            section_type: Filtrar por tipo de seção
            top: Número máximo de resultados
            min_score: Score mínimo para incluir resultado

        Returns:
            SearchResponse com resultados
        """
        import asyncio
        import time

        start_time = time.time()

        logger.info(
            "Iniciando busca híbrida",
            query=query[:100],
            client_id=client_id,
            document_id=str(document_id) if document_id else None,
        )

        # 1. Gerar embedding da query
        query_embedding = await self.embedding_service.get_embedding(query)

        # 2. Construir filtro
        filter_str = self._build_filter(client_id, document_id, section_type)

        # 3. Criar query vetorial
        vector_query = VectorizedQuery(
            vector=query_embedding,
            k_nearest_neighbors=top * 2,  # Buscar mais para combinar
            fields="content_vector",
        )

        # 4. Executar busca híbrida
        loop = asyncio.get_event_loop()
        search_results = await loop.run_in_executor(
            None,
            lambda: list(self.search_client.search(
                search_text=query,  # Keyword search
                vector_queries=[vector_query],  # Vector search
                filter=filter_str,
                select=[
                    "id", "document_id", "client_id", "content", "content_length",
                    "page_number", "page_start", "page_end",
                    "section_title", "section_number", "section_type",
                    "chunk_index", "total_chunks", "created_at",
                ],
                top=top,
                query_type="simple",
            )),
        )

        # 5. Processar resultados
        results = [
            self._parse_result(r, SearchMode.HYBRID)
            for r in search_results
            if r.get("@search.score", 0) >= min_score
        ]

        # 6. Aplicar re-ranking
        results = self._rerank_results(results, query)

        search_time = (time.time() - start_time) * 1000

        logger.info(
            "Busca híbrida concluída",
            results_count=len(results),
            search_time_ms=round(search_time, 2),
        )

        return SearchResponse(
            results=results,
            total_count=len(results),
            query=query,
            mode=SearchMode.HYBRID,
            filters_applied={
                "client_id": client_id,
                "document_id": str(document_id) if document_id else None,
                "section_type": section_type,
            },
            search_time_ms=search_time,
        )

    async def search(
        self,
        query: str,
        client_id: str,
        document_id: Optional[Union[str, UUID]] = None,
        section_type: Optional[str] = None,
        mode: SearchMode = SearchMode.HYBRID,
        top: int = 10,
        min_score: float = 0.0,
    ) -> SearchResponse:
        """
        Método principal de busca.

        Seleciona o modo de busca apropriado.

        Args:
            query: Texto da pergunta/busca
            client_id: ID do cliente (obrigatório)
            document_id: Filtrar por documento específico
            section_type: Filtrar por tipo de seção
            mode: Modo de busca (VECTOR, KEYWORD, HYBRID)
            top: Número máximo de resultados
            min_score: Score mínimo para incluir resultado

        Returns:
            SearchResponse com resultados
        """
        if mode == SearchMode.VECTOR:
            return await self.vector_search(
                query=query,
                client_id=client_id,
                document_id=document_id,
                section_type=section_type,
                top=top,
                min_score=min_score,
            )
        elif mode == SearchMode.KEYWORD:
            return await self.keyword_search(
                query=query,
                client_id=client_id,
                document_id=document_id,
                section_type=section_type,
                top=top,
            )
        else:  # HYBRID
            return await self.hybrid_search(
                query=query,
                client_id=client_id,
                document_id=document_id,
                section_type=section_type,
                top=top,
                min_score=min_score,
            )

    async def get_similar_chunks(
        self,
        chunk_id: str,
        client_id: str,
        top: int = 5,
        exclude_same_document: bool = False,
    ) -> SearchResponse:
        """
        Encontra chunks similares a um chunk específico.

        Útil para encontrar cláusulas similares em outros contratos.

        Args:
            chunk_id: ID do chunk de referência
            client_id: ID do cliente
            top: Número de resultados
            exclude_same_document: Se True, exclui chunks do mesmo documento

        Returns:
            SearchResponse com chunks similares
        """
        import asyncio
        import time

        start_time = time.time()

        logger.info(
            "Buscando chunks similares",
            chunk_id=chunk_id,
            client_id=client_id,
        )

        # 1. Buscar o chunk original
        loop = asyncio.get_event_loop()
        original_results = await loop.run_in_executor(
            None,
            lambda: list(self.search_client.search(
                search_text="*",
                filter=f"id eq '{chunk_id}' and client_id eq '{client_id}'",
                select=["id", "document_id", "content", "content_vector"],
                top=1,
            )),
        )

        if not original_results:
            logger.warning("Chunk não encontrado", chunk_id=chunk_id)
            return SearchResponse(
                results=[],
                total_count=0,
                query=f"similar_to:{chunk_id}",
                mode=SearchMode.VECTOR,
                filters_applied={"client_id": client_id},
                search_time_ms=(time.time() - start_time) * 1000,
            )

        original = original_results[0]
        original_document_id = original.get("document_id")

        # 2. Usar o conteúdo para gerar embedding (mais preciso que usar o vetor armazenado)
        content = original.get("content", "")
        query_embedding = await self.embedding_service.get_embedding(content)

        # 3. Construir filtro
        filter_parts = [f"client_id eq '{client_id}'", f"id ne '{chunk_id}'"]
        if exclude_same_document and original_document_id:
            filter_parts.append(f"document_id ne '{original_document_id}'")
        filter_str = " and ".join(filter_parts)

        # 4. Buscar similares
        vector_query = VectorizedQuery(
            vector=query_embedding,
            k_nearest_neighbors=top,
            fields="content_vector",
        )

        search_results = await loop.run_in_executor(
            None,
            lambda: list(self.search_client.search(
                search_text=None,
                vector_queries=[vector_query],
                filter=filter_str,
                select=[
                    "id", "document_id", "client_id", "content", "content_length",
                    "page_number", "page_start", "page_end",
                    "section_title", "section_number", "section_type",
                    "chunk_index", "total_chunks", "created_at",
                ],
                top=top,
            )),
        )

        # 5. Processar resultados
        results = [
            self._parse_result(r, SearchMode.VECTOR)
            for r in search_results
        ]

        search_time = (time.time() - start_time) * 1000

        logger.info(
            "Busca por similares concluída",
            results_count=len(results),
            search_time_ms=round(search_time, 2),
        )

        return SearchResponse(
            results=results,
            total_count=len(results),
            query=f"similar_to:{chunk_id}",
            mode=SearchMode.VECTOR,
            filters_applied={
                "client_id": client_id,
                "exclude_same_document": str(exclude_same_document),
            },
            search_time_ms=search_time,
        )


# Singleton
_search_service: Optional[SearchService] = None


def get_search_service() -> SearchService:
    """Retorna instância singleton do serviço de busca."""
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service
