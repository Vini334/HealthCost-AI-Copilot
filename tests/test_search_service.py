"""
Testes para o serviço de busca semântica.

Testes unitários para:
- SearchService (busca vetorial, keyword, híbrida)
- Re-ranking de resultados
- Filtros
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from src.search.search_service import (
    SearchService,
    SearchMode,
    SearchResult,
    SearchResponse,
)
from src.search.embedding_service import EMBEDDING_DIMENSION


class TestSearchService:
    """Testes para o serviço de busca."""

    @pytest.fixture
    def mock_search_client(self):
        """Mock do SearchClient do Azure."""
        with patch("src.search.search_service.SearchClient") as mock:
            client_instance = Mock()
            mock.return_value = client_instance
            yield client_instance

    @pytest.fixture
    def mock_embedding_service(self):
        """Mock do EmbeddingService."""
        with patch("src.search.search_service.get_embedding_service") as mock:
            service_instance = Mock()
            service_instance.get_embedding = AsyncMock(
                return_value=[0.1] * EMBEDDING_DIMENSION
            )
            mock.return_value = service_instance
            yield service_instance

    @pytest.fixture
    def search_service(self, mock_search_client, mock_embedding_service):
        """Fixture do SearchService com mocks."""
        # Reset singleton
        import src.search.search_service as module
        module._search_service = None

        return SearchService()

    @pytest.fixture
    def sample_search_results(self):
        """Resultados de busca de exemplo."""
        return [
            {
                "id": "chunk-1",
                "document_id": "doc-1",
                "client_id": "client-123",
                "content": "CLÁUSULA 5 - CARÊNCIAS. O prazo de carência...",
                "content_length": 500,
                "page_number": 5,
                "page_start": 5,
                "page_end": 5,
                "section_title": "CLÁUSULA 5 - CARÊNCIAS",
                "section_number": "5",
                "section_type": "clausula",
                "chunk_index": 4,
                "total_chunks": 45,
                "@search.score": 0.85,
                "created_at": "2024-01-15T10:30:00Z",
            },
            {
                "id": "chunk-2",
                "document_id": "doc-1",
                "client_id": "client-123",
                "content": "Parágrafo único. A carência não se aplica...",
                "content_length": 300,
                "page_number": 6,
                "page_start": 6,
                "page_end": 6,
                "section_title": None,
                "section_number": None,
                "section_type": "paragrafo",
                "chunk_index": 5,
                "total_chunks": 45,
                "@search.score": 0.72,
                "created_at": "2024-01-15T10:30:00Z",
            },
        ]

    def test_build_filter_client_only(self, search_service):
        """Testa construção de filtro apenas com client_id."""
        filter_str = search_service._build_filter(client_id="client-123")

        assert filter_str == "client_id eq 'client-123'"

    def test_build_filter_with_document_id(self, search_service):
        """Testa construção de filtro com document_id."""
        filter_str = search_service._build_filter(
            client_id="client-123",
            document_id="doc-456",
        )

        assert "client_id eq 'client-123'" in filter_str
        assert "document_id eq 'doc-456'" in filter_str
        assert " and " in filter_str

    def test_build_filter_with_section_type(self, search_service):
        """Testa construção de filtro com section_type."""
        filter_str = search_service._build_filter(
            client_id="client-123",
            section_type="clausula",
        )

        assert "client_id eq 'client-123'" in filter_str
        assert "section_type eq 'clausula'" in filter_str

    def test_build_filter_all_params(self, search_service):
        """Testa construção de filtro com todos os parâmetros."""
        filter_str = search_service._build_filter(
            client_id="client-123",
            document_id="doc-456",
            section_type="clausula",
        )

        assert "client_id eq 'client-123'" in filter_str
        assert "document_id eq 'doc-456'" in filter_str
        assert "section_type eq 'clausula'" in filter_str
        assert filter_str.count(" and ") == 2

    def test_parse_result_vector_mode(self, search_service, sample_search_results):
        """Testa parsing de resultado em modo vetorial."""
        result = search_service._parse_result(
            sample_search_results[0],
            SearchMode.VECTOR,
        )

        assert isinstance(result, SearchResult)
        assert result.id == "chunk-1"
        assert result.document_id == "doc-1"
        assert result.client_id == "client-123"
        assert result.content == "CLÁUSULA 5 - CARÊNCIAS. O prazo de carência..."
        assert result.page_number == 5
        assert result.section_title == "CLÁUSULA 5 - CARÊNCIAS"
        assert result.score == 0.85
        assert result.vector_score == 0.85

    def test_parse_result_keyword_mode(self, search_service, sample_search_results):
        """Testa parsing de resultado em modo keyword."""
        result = search_service._parse_result(
            sample_search_results[0],
            SearchMode.KEYWORD,
        )

        assert result.keyword_score == 0.85
        assert result.vector_score is None

    def test_parse_result_hybrid_mode(self, search_service, sample_search_results):
        """Testa parsing de resultado em modo híbrido."""
        result = search_service._parse_result(
            sample_search_results[0],
            SearchMode.HYBRID,
        )

        assert result.score == 0.85
        # Em modo híbrido, ambos os scores são definidos
        assert result.vector_score is not None
        assert result.keyword_score is not None

    def test_rerank_results_boost_title_match(self, search_service):
        """Testa que re-ranking aplica boost quando título contém palavras da query."""
        results = [
            SearchResult(
                id="1",
                document_id="doc-1",
                client_id="client-123",
                content="Conteúdo sobre carência",
                content_length=500,
                page_number=5,
                page_start=5,
                page_end=5,
                section_title="CLÁUSULA 5 - CARÊNCIAS",  # Contém "carência"
                section_number="5",
                section_type="clausula",
                chunk_index=4,
                total_chunks=45,
                score=0.7,
                vector_score=0.7,
                keyword_score=None,
                reranker_score=None,
                created_at=datetime.utcnow(),
            ),
            SearchResult(
                id="2",
                document_id="doc-1",
                client_id="client-123",
                content="Outro conteúdo",
                content_length=500,
                page_number=10,
                page_start=10,
                page_end=10,
                section_title="CLÁUSULA 10 - EXCLUSÕES",  # Não contém "carência"
                section_number="10",
                section_type="clausula",
                chunk_index=9,
                total_chunks=45,
                score=0.7,  # Mesmo score original
                vector_score=0.7,
                keyword_score=None,
                reranker_score=None,
                created_at=datetime.utcnow(),
            ),
        ]

        # Usando "cláusula" e "5" que estão no título
        reranked = search_service._rerank_results(results, "cláusula 5")

        # O resultado com título contendo palavras da query deve ter boost
        result_with_match = next(r for r in reranked if r.id == "1")
        result_without_match = next(r for r in reranked if r.id == "2")

        # Boost aplicado ao resultado com match no título ("cláusula" e "5" aparecem)
        assert result_with_match.reranker_score > result_with_match.score
        # Resultado com match deve ter score maior que sem match
        assert result_with_match.reranker_score > result_without_match.reranker_score

    def test_rerank_results_boost_early_chunks(self, search_service):
        """Testa que re-ranking aplica boost para chunks iniciais."""
        results = [
            SearchResult(
                id="1",
                document_id="doc-1",
                client_id="client-123",
                content="Conteúdo",
                content_length=500,
                page_number=5,
                page_start=5,
                page_end=5,
                section_title="Seção",
                section_number="5",
                section_type="clausula",
                chunk_index=10,  # Chunk tardio
                total_chunks=45,
                score=0.8,
                vector_score=0.8,
                keyword_score=None,
                reranker_score=None,
                created_at=datetime.utcnow(),
            ),
            SearchResult(
                id="2",
                document_id="doc-1",
                client_id="client-123",
                content="Outro conteúdo",
                content_length=500,
                page_number=1,
                page_start=1,
                page_end=1,
                section_title="Seção",
                section_number="1",
                section_type="clausula",
                chunk_index=0,  # Primeiro chunk - recebe boost
                total_chunks=45,
                score=0.8,  # Mesmo score original
                vector_score=0.8,
                keyword_score=None,
                reranker_score=None,
                created_at=datetime.utcnow(),
            ),
        ]

        reranked = search_service._rerank_results(results, "teste")

        # Chunk inicial (index 0) deve ter boost
        early_chunk = next(r for r in reranked if r.id == "2")
        late_chunk = next(r for r in reranked if r.id == "1")

        # Chunk inicial recebe boost, tardio não
        assert early_chunk.reranker_score > early_chunk.score
        assert early_chunk.reranker_score > late_chunk.reranker_score

    def test_rerank_results_penalize_short_content(self, search_service):
        """Testa que re-ranking penaliza chunks muito curtos."""
        results = [
            SearchResult(
                id="1",
                document_id="doc-1",
                client_id="client-123",
                content="X" * 100,  # Conteúdo curto (< 200)
                content_length=100,
                page_number=5,
                page_start=5,
                page_end=5,
                section_title="Seção",
                section_number="5",
                section_type="clausula",
                chunk_index=4,
                total_chunks=45,
                score=0.8,
                vector_score=0.8,
                keyword_score=None,
                reranker_score=None,
                created_at=datetime.utcnow(),
            ),
        ]

        reranked = search_service._rerank_results(results, "teste")

        # Deve ter penalidade (reranker_score < score original)
        assert reranked[0].reranker_score < reranked[0].score

    @pytest.mark.asyncio
    async def test_vector_search(
        self, search_service, mock_search_client, mock_embedding_service, sample_search_results
    ):
        """Testa busca vetorial."""
        # Arrange
        mock_search_client.search.return_value = sample_search_results

        # Act
        response = await search_service.vector_search(
            query="prazo de carência",
            client_id="client-123",
            top=10,
        )

        # Assert
        assert isinstance(response, SearchResponse)
        assert response.mode == SearchMode.VECTOR
        assert response.total_count == 2
        assert len(response.results) == 2
        assert response.query == "prazo de carência"
        assert response.filters_applied["client_id"] == "client-123"

        # Deve ter gerado embedding
        mock_embedding_service.get_embedding.assert_called_once_with("prazo de carência")

    @pytest.mark.asyncio
    async def test_keyword_search(
        self, search_service, mock_search_client, sample_search_results
    ):
        """Testa busca por keywords."""
        # Arrange
        mock_search_client.search.return_value = sample_search_results

        # Act
        response = await search_service.keyword_search(
            query="carência",
            client_id="client-123",
            top=10,
        )

        # Assert
        assert response.mode == SearchMode.KEYWORD
        assert response.total_count == 2

    @pytest.mark.asyncio
    async def test_hybrid_search(
        self, search_service, mock_search_client, mock_embedding_service, sample_search_results
    ):
        """Testa busca híbrida."""
        # Arrange
        mock_search_client.search.return_value = sample_search_results

        # Act
        response = await search_service.hybrid_search(
            query="prazo de carência",
            client_id="client-123",
            top=10,
        )

        # Assert
        assert response.mode == SearchMode.HYBRID
        assert response.total_count == 2

        # Deve ter gerado embedding para busca vetorial
        mock_embedding_service.get_embedding.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_with_document_filter(
        self, search_service, mock_search_client, mock_embedding_service, sample_search_results
    ):
        """Testa busca com filtro de documento."""
        # Arrange
        mock_search_client.search.return_value = sample_search_results

        # Act
        response = await search_service.search(
            query="carência",
            client_id="client-123",
            document_id="doc-456",
            mode=SearchMode.HYBRID,
        )

        # Assert
        assert response.filters_applied["document_id"] == "doc-456"

    @pytest.mark.asyncio
    async def test_search_with_min_score(
        self, search_service, mock_search_client, mock_embedding_service
    ):
        """Testa busca com score mínimo."""
        # Arrange - resultado com score baixo
        low_score_result = {
            "id": "chunk-low",
            "document_id": "doc-1",
            "client_id": "client-123",
            "content": "Conteúdo",
            "content_length": 100,
            "page_number": 1,
            "@search.score": 0.3,  # Score baixo
        }
        mock_search_client.search.return_value = [low_score_result]

        # Act
        response = await search_service.vector_search(
            query="teste",
            client_id="client-123",
            min_score=0.5,  # Score mínimo alto
        )

        # Assert - resultado deve ser filtrado
        assert response.total_count == 0

    @pytest.mark.asyncio
    async def test_search_mode_selection(
        self, search_service, mock_search_client, mock_embedding_service, sample_search_results
    ):
        """Testa seleção de modo de busca."""
        mock_search_client.search.return_value = sample_search_results

        # Teste modo VECTOR
        response = await search_service.search(
            query="teste",
            client_id="client-123",
            mode=SearchMode.VECTOR,
        )
        assert response.mode == SearchMode.VECTOR

        # Teste modo KEYWORD
        response = await search_service.search(
            query="teste",
            client_id="client-123",
            mode=SearchMode.KEYWORD,
        )
        assert response.mode == SearchMode.KEYWORD

        # Teste modo HYBRID (padrão)
        response = await search_service.search(
            query="teste",
            client_id="client-123",
        )
        assert response.mode == SearchMode.HYBRID


class TestSearchResult:
    """Testes para o modelo SearchResult."""

    def test_to_dict(self):
        """Testa conversão para dicionário."""
        result = SearchResult(
            id="chunk-1",
            document_id="doc-1",
            client_id="client-123",
            content="Conteúdo de teste",
            content_length=17,
            page_number=5,
            page_start=5,
            page_end=5,
            section_title="CLÁUSULA 5",
            section_number="5",
            section_type="clausula",
            chunk_index=4,
            total_chunks=45,
            score=0.85,
            vector_score=0.85,
            keyword_score=None,
            reranker_score=0.90,
            created_at=datetime(2024, 1, 15, 10, 30),
        )

        d = result.to_dict()

        assert d["id"] == "chunk-1"
        assert d["document_id"] == "doc-1"
        assert d["score"] == 0.85
        assert d["reranker_score"] == 0.90
        assert d["created_at"] == "2024-01-15T10:30:00"


class TestSearchResponse:
    """Testes para o modelo SearchResponse."""

    def test_to_dict(self):
        """Testa conversão para dicionário."""
        response = SearchResponse(
            results=[],
            total_count=0,
            query="teste",
            mode=SearchMode.HYBRID,
            filters_applied={"client_id": "client-123"},
            search_time_ms=50.5,
        )

        d = response.to_dict()

        assert d["total_count"] == 0
        assert d["query"] == "teste"
        assert d["mode"] == "hybrid"
        assert d["search_time_ms"] == 50.5
