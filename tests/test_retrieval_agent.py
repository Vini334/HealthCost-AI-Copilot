"""
Testes para o RetrievalAgent e ferramentas de busca.

Testa:
- Ferramentas de busca (HybridSearchTool, VectorSearchTool, etc.)
- RetrievalAgent (busca direta e guiada por LLM)
- Integração com SearchService
"""

import asyncio
import pytest
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from src.models.agents import (
    AgentContext,
    AgentExecutionResult,
    AgentStatus,
    AgentType,
    ToolCall,
    ToolParameter,
    ToolResult,
    ToolResultStatus,
)
from src.agents.tools import ToolRegistry
from src.agents.search_tools import (
    HybridSearchTool,
    VectorSearchTool,
    KeywordSearchTool,
    SimilarChunksTool,
    register_search_tools,
)
from src.agents.retrieval_agent import RetrievalAgent, create_retrieval_agent
from src.search.search_service import SearchMode, SearchResponse, SearchResult


# ============================================
# Mock Data e Fixtures
# ============================================


@dataclass
class MockSearchResult:
    """Mock de SearchResult para testes."""
    id: str = "chunk-1"
    document_id: str = "doc-123"
    client_id: str = "cliente-123"
    content: str = "Conteúdo do chunk de teste"
    content_length: int = 30
    page_number: int = 5
    page_start: int = 5
    page_end: int = 5
    section_title: str = "Carência"
    section_number: str = "3.1"
    section_type: str = "clausula"
    chunk_index: int = 0
    total_chunks: int = 10
    score: float = 0.85
    vector_score: float = 0.85
    keyword_score: float = 0.80
    reranker_score: float = 0.90
    created_at: Any = None

    def to_dict(self) -> Dict[str, Any]:
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
            "created_at": self.created_at,
        }


def create_mock_search_response(
    num_results: int = 3,
    query: str = "teste",
    mode: SearchMode = SearchMode.HYBRID,
) -> SearchResponse:
    """Cria um SearchResponse mock para testes."""
    results = []
    for i in range(num_results):
        result = MockSearchResult(
            id=f"chunk-{i}",
            content=f"Conteúdo do chunk {i}",
            page_number=i + 1,
            section_title=f"Seção {i}",
            score=0.9 - (i * 0.1),
            reranker_score=0.95 - (i * 0.1),
        )
        results.append(result)

    return SearchResponse(
        results=results,
        total_count=num_results,
        query=query,
        mode=mode,
        filters_applied={"client_id": "cliente-123"},
        search_time_ms=150.0,
    )


@pytest.fixture
def mock_search_service():
    """Fixture que fornece um SearchService mockado."""
    mock = MagicMock()
    mock.hybrid_search = AsyncMock(
        return_value=create_mock_search_response(mode=SearchMode.HYBRID)
    )
    mock.vector_search = AsyncMock(
        return_value=create_mock_search_response(mode=SearchMode.VECTOR)
    )
    mock.keyword_search = AsyncMock(
        return_value=create_mock_search_response(mode=SearchMode.KEYWORD)
    )
    mock.get_similar_chunks = AsyncMock(
        return_value=create_mock_search_response(num_results=2)
    )
    mock.search = AsyncMock(
        return_value=create_mock_search_response()
    )
    return mock


# ============================================
# Testes de Ferramentas de Busca
# ============================================


class TestHybridSearchTool:
    """Testes para HybridSearchTool."""

    def test_tool_properties(self):
        """Testa propriedades da ferramenta."""
        tool = HybridSearchTool()

        assert tool.name == "search_hybrid"
        assert "híbrida" in tool.description.lower()

    def test_get_parameters(self):
        """Testa parâmetros da ferramenta."""
        tool = HybridSearchTool()
        params = tool.get_parameters()

        param_names = [p.name for p in params]
        assert "query" in param_names
        assert "client_id" in param_names
        assert "document_id" in param_names
        assert "top" in param_names

        # query e client_id são obrigatórios
        query_param = next(p for p in params if p.name == "query")
        client_param = next(p for p in params if p.name == "client_id")
        assert query_param.required is True
        assert client_param.required is True

    @pytest.mark.asyncio
    async def test_execute(self, mock_search_service):
        """Testa execução da busca híbrida."""
        tool = HybridSearchTool(search_service=mock_search_service)

        result = await tool.execute(
            query="prazo de carência",
            client_id="cliente-123",
            document_id="doc-456",
            top=5,
        )

        assert "chunks" in result
        assert "total_count" in result
        assert "search_time_ms" in result
        assert len(result["chunks"]) == 3

        mock_search_service.hybrid_search.assert_called_once_with(
            query="prazo de carência",
            client_id="cliente-123",
            document_id="doc-456",
            section_type=None,
            top=5,
        )

    @pytest.mark.asyncio
    async def test_execute_via_tool_call(self, mock_search_service):
        """Testa execução via ToolCall."""
        tool = HybridSearchTool(search_service=mock_search_service)

        call = ToolCall(
            tool_name="search_hybrid",
            arguments={
                "query": "cobertura",
                "client_id": "cliente-123",
            },
        )

        result = await tool.run(call)

        assert result.status == ToolResultStatus.SUCCESS
        assert "chunks" in result.result


class TestVectorSearchTool:
    """Testes para VectorSearchTool."""

    def test_tool_properties(self):
        """Testa propriedades da ferramenta."""
        tool = VectorSearchTool()

        assert tool.name == "search_vector"
        assert "semanticamente" in tool.description.lower()

    @pytest.mark.asyncio
    async def test_execute(self, mock_search_service):
        """Testa execução da busca vetorial."""
        tool = VectorSearchTool(search_service=mock_search_service)

        result = await tool.execute(
            query="procedimentos hospitalares",
            client_id="cliente-123",
            top=10,
        )

        assert "chunks" in result
        mock_search_service.vector_search.assert_called_once()


class TestKeywordSearchTool:
    """Testes para KeywordSearchTool."""

    def test_tool_properties(self):
        """Testa propriedades da ferramenta."""
        tool = KeywordSearchTool()

        assert tool.name == "search_keyword"
        assert "palavras-chave" in tool.description.lower()

    @pytest.mark.asyncio
    async def test_execute(self, mock_search_service):
        """Testa execução da busca por keywords."""
        tool = KeywordSearchTool(search_service=mock_search_service)

        result = await tool.execute(
            query="código 123",
            client_id="cliente-123",
        )

        assert "chunks" in result
        mock_search_service.keyword_search.assert_called_once()


class TestSimilarChunksTool:
    """Testes para SimilarChunksTool."""

    def test_tool_properties(self):
        """Testa propriedades da ferramenta."""
        tool = SimilarChunksTool()

        assert tool.name == "find_similar_chunks"
        assert "similar" in tool.description.lower()

    def test_get_parameters(self):
        """Testa parâmetros da ferramenta."""
        tool = SimilarChunksTool()
        params = tool.get_parameters()

        param_names = [p.name for p in params]
        assert "chunk_id" in param_names
        assert "client_id" in param_names
        assert "exclude_same_document" in param_names

    @pytest.mark.asyncio
    async def test_execute(self, mock_search_service):
        """Testa execução da busca de similares."""
        tool = SimilarChunksTool(search_service=mock_search_service)

        result = await tool.execute(
            chunk_id="chunk-123",
            client_id="cliente-123",
            exclude_same_document=True,
            top=5,
        )

        assert "similar_chunks" in result
        assert "reference_chunk_id" in result
        mock_search_service.get_similar_chunks.assert_called_once()


class TestRegisterSearchTools:
    """Testes para register_search_tools."""

    def test_register_all_tools(self):
        """Testa registro de todas as ferramentas."""
        registry = ToolRegistry()
        register_search_tools(registry)

        tools = registry.list_tools()

        assert "search_hybrid" in tools
        assert "search_vector" in tools
        assert "search_keyword" in tools
        assert "find_similar_chunks" in tools


# ============================================
# Testes do RetrievalAgent
# ============================================


class TestRetrievalAgent:
    """Testes para RetrievalAgent."""

    def test_agent_properties(self):
        """Testa propriedades do agente."""
        with patch("src.agents.retrieval_agent.get_search_service"):
            agent = RetrievalAgent(auto_register_tools=False)

            assert agent.agent_type == AgentType.RETRIEVAL
            assert agent.agent_name == "retrieval_agent"
            assert agent.temperature == 0.1  # Baixa para determinismo

    def test_get_tools(self):
        """Testa ferramentas disponíveis."""
        with patch("src.agents.retrieval_agent.get_search_service"):
            agent = RetrievalAgent(auto_register_tools=False)
            tools = agent.get_tools()

            assert "search_hybrid" in tools
            assert "search_vector" in tools
            assert "search_keyword" in tools
            assert "find_similar_chunks" in tools

    def test_auto_register_tools(self):
        """Testa registro automático de ferramentas."""
        registry = ToolRegistry()

        with patch("src.agents.retrieval_agent.get_search_service"):
            agent = RetrievalAgent(
                tool_registry=registry,
                auto_register_tools=True,
            )

            tools = registry.list_tools()
            assert "search_hybrid" in tools

    @pytest.mark.asyncio
    async def test_direct_search(self, mock_search_service):
        """Testa busca direta (sem LLM)."""
        registry = ToolRegistry()
        register_search_tools(registry)

        # Patch o search service usado pelas tools
        with patch(
            "src.agents.search_tools.get_search_service",
            return_value=mock_search_service,
        ), patch(
            "src.agents.retrieval_agent.get_search_service",
            return_value=mock_search_service,
        ):
            agent = RetrievalAgent(
                tool_registry=registry,
                auto_register_tools=False,
            )

            result = await agent.execute(
                query="Qual o prazo de carência?",
                client_id="cliente-123",
                contract_id="contrato-456",
                metadata={"direct_search": True},
            )

            assert result.status == AgentStatus.COMPLETED
            assert result.structured_output is not None
            assert "chunks" in result.structured_output
            assert result.structured_output["chunk_count"] == 3

    @pytest.mark.asyncio
    async def test_direct_search_no_results(self, mock_search_service):
        """Testa busca direta sem resultados."""
        mock_search_service.hybrid_search = AsyncMock(
            return_value=create_mock_search_response(num_results=0)
        )

        registry = ToolRegistry()
        register_search_tools(registry)

        with patch(
            "src.agents.search_tools.get_search_service",
            return_value=mock_search_service,
        ), patch(
            "src.agents.retrieval_agent.get_search_service",
            return_value=mock_search_service,
        ):
            agent = RetrievalAgent(
                tool_registry=registry,
                auto_register_tools=False,
            )

            result = await agent.execute(
                query="termo inexistente",
                client_id="cliente-123",
            )

            assert result.status == AgentStatus.COMPLETED
            assert result.structured_output["chunk_count"] == 0
            assert "Nenhum resultado" in result.response

    @pytest.mark.asyncio
    async def test_sources_extraction(self, mock_search_service):
        """Testa extração de fontes dos chunks."""
        registry = ToolRegistry()
        register_search_tools(registry)

        with patch(
            "src.agents.search_tools.get_search_service",
            return_value=mock_search_service,
        ), patch(
            "src.agents.retrieval_agent.get_search_service",
            return_value=mock_search_service,
        ):
            agent = RetrievalAgent(
                tool_registry=registry,
                auto_register_tools=False,
            )

            result = await agent.execute(
                query="teste",
                client_id="cliente-123",
            )

            assert len(result.sources) > 0
            # Verifica que as fontes têm informações relevantes
            source = result.sources[0]
            assert "page_number" in source or source.get("page_number") is not None

    @pytest.mark.asyncio
    async def test_search_convenience_method(self, mock_search_service):
        """Testa método de busca de conveniência."""
        with patch(
            "src.agents.retrieval_agent.get_search_service",
            return_value=mock_search_service,
        ):
            agent = RetrievalAgent(auto_register_tools=False)

            result = await agent.search(
                query="cobertura",
                client_id="cliente-123",
                contract_id="contrato-456",
                mode=SearchMode.HYBRID,
                top=5,
            )

            assert "chunks" in result
            assert "chunk_count" in result
            mock_search_service.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_multi_query_search(self, mock_search_service):
        """Testa busca com múltiplas queries."""
        with patch(
            "src.agents.retrieval_agent.get_search_service",
            return_value=mock_search_service,
        ):
            agent = RetrievalAgent(auto_register_tools=False)

            queries = [
                "prazo de carência",
                "período de carência",
                "carência para internação",
            ]

            result = await agent.multi_query_search(
                queries=queries,
                client_id="cliente-123",
                top_per_query=3,
                deduplicate=True,
            )

            assert "chunks" in result
            assert "queries" in result
            assert len(result["queries"]) == 3
            # Verifica que hybrid_search foi chamado 3 vezes
            assert mock_search_service.hybrid_search.call_count == 3


class TestCreateRetrievalAgent:
    """Testes para factory function."""

    def test_create_agent(self):
        """Testa criação via factory."""
        with patch("src.agents.retrieval_agent.get_search_service"):
            agent = create_retrieval_agent()

            assert isinstance(agent, RetrievalAgent)
            assert agent.agent_type == AgentType.RETRIEVAL

    def test_create_with_custom_registry(self):
        """Testa criação com registry customizado."""
        registry = ToolRegistry()

        with patch("src.agents.retrieval_agent.get_search_service"):
            agent = create_retrieval_agent(tool_registry=registry)

            assert agent._tool_registry is registry


# ============================================
# Testes de Integração
# ============================================


class TestRetrievalAgentIntegration:
    """Testes de integração do RetrievalAgent."""

    @pytest.mark.asyncio
    async def test_execute_with_context(self, mock_search_service):
        """Testa execução com contexto existente."""
        registry = ToolRegistry()
        register_search_tools(registry)

        with patch(
            "src.agents.search_tools.get_search_service",
            return_value=mock_search_service,
        ), patch(
            "src.agents.retrieval_agent.get_search_service",
            return_value=mock_search_service,
        ):
            agent = RetrievalAgent(
                tool_registry=registry,
                auto_register_tools=False,
            )

            context = AgentContext(
                client_id="cliente-123",
                contract_id="contrato-456",
                query="Qual o prazo de carência?",
            )

            result = await agent.execute_with_context(context)

            assert result.status == AgentStatus.COMPLETED
            assert result.agent_type == AgentType.RETRIEVAL

    @pytest.mark.asyncio
    async def test_context_manager_integration(self, mock_search_service):
        """Testa integração com ContextManager."""
        from src.agents.context import ContextManager

        registry = ToolRegistry()
        register_search_tools(registry)
        context_manager = ContextManager()

        with patch(
            "src.agents.search_tools.get_search_service",
            return_value=mock_search_service,
        ), patch(
            "src.agents.retrieval_agent.get_search_service",
            return_value=mock_search_service,
        ):
            agent = RetrievalAgent(
                tool_registry=registry,
                context_manager=context_manager,
                auto_register_tools=False,
            )

            result = await agent.execute(
                query="teste",
                client_id="cliente-123",
            )

            # Verifica que chunks foram setados no contexto
            # (o contexto é limpo após execução, então não podemos verificar diretamente)
            assert result.status == AgentStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_execution_tracking(self, mock_search_service):
        """Testa rastreamento de execução."""
        from src.agents.execution_logger import ExecutionTracker

        registry = ToolRegistry()
        register_search_tools(registry)
        tracker = ExecutionTracker()

        with patch(
            "src.agents.search_tools.get_search_service",
            return_value=mock_search_service,
        ), patch(
            "src.agents.retrieval_agent.get_search_service",
            return_value=mock_search_service,
        ):
            agent = RetrievalAgent(
                tool_registry=registry,
                execution_tracker=tracker,
                auto_register_tools=False,
            )

            result = await agent.execute(
                query="teste",
                client_id="cliente-123",
            )

            # Verifica que a execução foi registrada
            tracked = tracker.get(result.execution_id)
            assert tracked is not None
            assert tracked.agent_type == AgentType.RETRIEVAL
