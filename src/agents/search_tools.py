"""
Ferramentas de busca para agentes.

Este módulo implementa as ferramentas de busca que podem ser
utilizadas pelos agentes, especialmente pelo RetrievalAgent.
"""

from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from src.agents.tools import AgentTool, tool
from src.config.logging import get_logger
from src.models.agents import ToolParameter
from src.search.search_service import (
    SearchMode,
    SearchResponse,
    SearchService,
    get_search_service,
)

logger = get_logger(__name__)


class HybridSearchTool(AgentTool):
    """
    Ferramenta de busca híbrida (vetorial + keyword).

    Combina busca semântica com busca por palavras-chave para
    encontrar trechos relevantes de contratos.
    """

    name = "search_hybrid"
    description = (
        "Busca trechos relevantes em contratos usando busca híbrida "
        "(semântica + keywords). Use esta ferramenta para encontrar "
        "informações específicas em contratos de planos de saúde, "
        "como cláusulas, prazos, coberturas e condições."
    )

    def __init__(self, search_service: Optional[SearchService] = None):
        """
        Inicializa a ferramenta.

        Args:
            search_service: Serviço de busca (usa singleton se não fornecido)
        """
        super().__init__()
        self._search_service = search_service

    @property
    def search_service(self) -> SearchService:
        """Retorna o serviço de busca (lazy loading)."""
        if self._search_service is None:
            self._search_service = get_search_service()
        return self._search_service

    def get_parameters(self) -> List[ToolParameter]:
        """Define os parâmetros da ferramenta."""
        return [
            ToolParameter(
                name="query",
                type="string",
                description="Texto da busca. Pode ser uma pergunta ou termos-chave.",
                required=True,
            ),
            ToolParameter(
                name="client_id",
                type="string",
                description="ID do cliente para filtrar a busca.",
                required=True,
            ),
            ToolParameter(
                name="document_id",
                type="string",
                description="ID do documento/contrato específico (opcional).",
                required=False,
            ),
            ToolParameter(
                name="section_type",
                type="string",
                description=(
                    "Tipo de seção para filtrar: clausula, capitulo, artigo, "
                    "paragrafo, anexo (opcional)."
                ),
                required=False,
            ),
            ToolParameter(
                name="top",
                type="integer",
                description="Número máximo de resultados (padrão: 10).",
                required=False,
                default=10,
            ),
        ]

    async def execute(
        self,
        query: str,
        client_id: str,
        document_id: Optional[str] = None,
        section_type: Optional[str] = None,
        top: int = 10,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Executa a busca híbrida.

        Args:
            query: Texto da busca
            client_id: ID do cliente
            document_id: ID do documento (opcional)
            section_type: Tipo de seção (opcional)
            top: Número máximo de resultados

        Returns:
            Dicionário com resultados da busca
        """
        self._logger.info(
            "Executando busca híbrida",
            query=query[:100],
            client_id=client_id,
            document_id=document_id,
        )

        response = await self.search_service.hybrid_search(
            query=query,
            client_id=client_id,
            document_id=document_id,
            section_type=section_type,
            top=top,
        )

        return self._format_response(response)

    def _format_response(self, response: SearchResponse) -> Dict[str, Any]:
        """Formata a resposta para retorno."""
        chunks = []
        for result in response.results:
            chunks.append({
                "id": result.id,
                "content": result.content,
                "document_id": result.document_id,
                "page_number": result.page_number,
                "page_start": result.page_start,
                "page_end": result.page_end,
                "section_title": result.section_title,
                "section_type": result.section_type,
                "score": result.reranker_score or result.score,
            })

        return {
            "chunks": chunks,
            "total_count": response.total_count,
            "query": response.query,
            "search_time_ms": response.search_time_ms,
        }


class VectorSearchTool(AgentTool):
    """
    Ferramenta de busca vetorial (semântica).

    Busca por similaridade semântica, ideal para encontrar
    conteúdo relacionado mesmo com diferentes palavras.
    """

    name = "search_vector"
    description = (
        "Busca trechos semanticamente similares em contratos. "
        "Ideal para encontrar conteúdo relacionado mesmo quando "
        "as palavras exatas não estão presentes."
    )

    def __init__(self, search_service: Optional[SearchService] = None):
        """Inicializa a ferramenta."""
        super().__init__()
        self._search_service = search_service

    @property
    def search_service(self) -> SearchService:
        """Retorna o serviço de busca (lazy loading)."""
        if self._search_service is None:
            self._search_service = get_search_service()
        return self._search_service

    def get_parameters(self) -> List[ToolParameter]:
        """Define os parâmetros da ferramenta."""
        return [
            ToolParameter(
                name="query",
                type="string",
                description="Texto da busca semântica.",
                required=True,
            ),
            ToolParameter(
                name="client_id",
                type="string",
                description="ID do cliente para filtrar a busca.",
                required=True,
            ),
            ToolParameter(
                name="document_id",
                type="string",
                description="ID do documento/contrato específico (opcional).",
                required=False,
            ),
            ToolParameter(
                name="top",
                type="integer",
                description="Número máximo de resultados (padrão: 10).",
                required=False,
                default=10,
            ),
        ]

    async def execute(
        self,
        query: str,
        client_id: str,
        document_id: Optional[str] = None,
        top: int = 10,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Executa a busca vetorial.

        Args:
            query: Texto da busca
            client_id: ID do cliente
            document_id: ID do documento (opcional)
            top: Número máximo de resultados

        Returns:
            Dicionário com resultados da busca
        """
        self._logger.info(
            "Executando busca vetorial",
            query=query[:100],
            client_id=client_id,
        )

        response = await self.search_service.vector_search(
            query=query,
            client_id=client_id,
            document_id=document_id,
            top=top,
        )

        return self._format_response(response)

    def _format_response(self, response: SearchResponse) -> Dict[str, Any]:
        """Formata a resposta para retorno."""
        chunks = []
        for result in response.results:
            chunks.append({
                "id": result.id,
                "content": result.content,
                "document_id": result.document_id,
                "page_number": result.page_number,
                "section_title": result.section_title,
                "section_type": result.section_type,
                "score": result.reranker_score or result.score,
            })

        return {
            "chunks": chunks,
            "total_count": response.total_count,
            "query": response.query,
            "search_time_ms": response.search_time_ms,
        }


class KeywordSearchTool(AgentTool):
    """
    Ferramenta de busca por keywords.

    Busca tradicional por palavras-chave, útil para termos
    técnicos específicos ou códigos.
    """

    name = "search_keyword"
    description = (
        "Busca trechos por palavras-chave exatas em contratos. "
        "Útil para encontrar termos técnicos específicos, "
        "códigos de procedimentos ou referências numéricas."
    )

    def __init__(self, search_service: Optional[SearchService] = None):
        """Inicializa a ferramenta."""
        super().__init__()
        self._search_service = search_service

    @property
    def search_service(self) -> SearchService:
        """Retorna o serviço de busca (lazy loading)."""
        if self._search_service is None:
            self._search_service = get_search_service()
        return self._search_service

    def get_parameters(self) -> List[ToolParameter]:
        """Define os parâmetros da ferramenta."""
        return [
            ToolParameter(
                name="query",
                type="string",
                description="Palavras-chave ou termos exatos para buscar.",
                required=True,
            ),
            ToolParameter(
                name="client_id",
                type="string",
                description="ID do cliente para filtrar a busca.",
                required=True,
            ),
            ToolParameter(
                name="document_id",
                type="string",
                description="ID do documento/contrato específico (opcional).",
                required=False,
            ),
            ToolParameter(
                name="top",
                type="integer",
                description="Número máximo de resultados (padrão: 10).",
                required=False,
                default=10,
            ),
        ]

    async def execute(
        self,
        query: str,
        client_id: str,
        document_id: Optional[str] = None,
        top: int = 10,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Executa a busca por keywords.

        Args:
            query: Palavras-chave para buscar
            client_id: ID do cliente
            document_id: ID do documento (opcional)
            top: Número máximo de resultados

        Returns:
            Dicionário com resultados da busca
        """
        self._logger.info(
            "Executando busca por keywords",
            query=query[:100],
            client_id=client_id,
        )

        response = await self.search_service.keyword_search(
            query=query,
            client_id=client_id,
            document_id=document_id,
            top=top,
        )

        return self._format_response(response)

    def _format_response(self, response: SearchResponse) -> Dict[str, Any]:
        """Formata a resposta para retorno."""
        chunks = []
        for result in response.results:
            chunks.append({
                "id": result.id,
                "content": result.content,
                "document_id": result.document_id,
                "page_number": result.page_number,
                "section_title": result.section_title,
                "section_type": result.section_type,
                "score": result.score,
            })

        return {
            "chunks": chunks,
            "total_count": response.total_count,
            "query": response.query,
            "search_time_ms": response.search_time_ms,
        }


class SimilarChunksTool(AgentTool):
    """
    Ferramenta para encontrar chunks similares.

    Dado um chunk de referência, encontra outros chunks
    semanticamente similares, útil para comparação entre contratos.
    """

    name = "find_similar_chunks"
    description = (
        "Encontra trechos similares a um trecho de referência. "
        "Útil para encontrar cláusulas similares em outros contratos "
        "ou identificar padrões de linguagem contratual."
    )

    def __init__(self, search_service: Optional[SearchService] = None):
        """Inicializa a ferramenta."""
        super().__init__()
        self._search_service = search_service

    @property
    def search_service(self) -> SearchService:
        """Retorna o serviço de busca (lazy loading)."""
        if self._search_service is None:
            self._search_service = get_search_service()
        return self._search_service

    def get_parameters(self) -> List[ToolParameter]:
        """Define os parâmetros da ferramenta."""
        return [
            ToolParameter(
                name="chunk_id",
                type="string",
                description="ID do chunk de referência.",
                required=True,
            ),
            ToolParameter(
                name="client_id",
                type="string",
                description="ID do cliente.",
                required=True,
            ),
            ToolParameter(
                name="exclude_same_document",
                type="boolean",
                description="Se True, exclui chunks do mesmo documento (padrão: False).",
                required=False,
                default=False,
            ),
            ToolParameter(
                name="top",
                type="integer",
                description="Número máximo de resultados (padrão: 5).",
                required=False,
                default=5,
            ),
        ]

    async def execute(
        self,
        chunk_id: str,
        client_id: str,
        exclude_same_document: bool = False,
        top: int = 5,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Encontra chunks similares.

        Args:
            chunk_id: ID do chunk de referência
            client_id: ID do cliente
            exclude_same_document: Se deve excluir o mesmo documento
            top: Número máximo de resultados

        Returns:
            Dicionário com chunks similares
        """
        self._logger.info(
            "Buscando chunks similares",
            chunk_id=chunk_id,
            client_id=client_id,
        )

        response = await self.search_service.get_similar_chunks(
            chunk_id=chunk_id,
            client_id=client_id,
            top=top,
            exclude_same_document=exclude_same_document,
        )

        chunks = []
        for result in response.results:
            chunks.append({
                "id": result.id,
                "content": result.content,
                "document_id": result.document_id,
                "page_number": result.page_number,
                "section_title": result.section_title,
                "similarity_score": result.score,
            })

        return {
            "similar_chunks": chunks,
            "total_count": response.total_count,
            "reference_chunk_id": chunk_id,
            "search_time_ms": response.search_time_ms,
        }


def register_search_tools(registry: "ToolRegistry") -> None:
    """
    Registra todas as ferramentas de busca no registry.

    Args:
        registry: ToolRegistry onde registrar as ferramentas
    """
    from src.agents.tools import ToolRegistry

    tools = [
        HybridSearchTool(),
        VectorSearchTool(),
        KeywordSearchTool(),
        SimilarChunksTool(),
    ]

    for tool in tools:
        registry.register(tool)

    logger.info(
        "Ferramentas de busca registradas",
        tool_count=len(tools),
        tools=[t.name for t in tools],
    )
