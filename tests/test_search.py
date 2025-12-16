"""
Testes para o módulo de busca e indexação.

Testes unitários para:
- EmbeddingService
- SearchIndexManager
- DocumentIndexer
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from uuid import uuid4
from datetime import datetime

from src.models.chunks import DocumentChunk, ChunkingStrategy
from src.search.embedding_service import EMBEDDING_DIMENSION


class TestEmbeddingService:
    """Testes para o serviço de embeddings."""

    @pytest.fixture
    def mock_openai_client(self):
        """Mock do cliente Azure OpenAI."""
        with patch("src.search.embedding_service.AzureOpenAI") as mock:
            client_instance = Mock()
            mock.return_value = client_instance
            yield client_instance

    @pytest.fixture
    def embedding_service(self, mock_openai_client):
        """Fixture do EmbeddingService com cliente mockado."""
        from src.search.embedding_service import EmbeddingService

        # Reset singleton
        import src.search.embedding_service as module
        module._embedding_service = None

        return EmbeddingService()

    def test_embedding_dimension_constant(self):
        """Verifica que a dimensão do embedding está correta."""
        assert EMBEDDING_DIMENSION == 1536

    @pytest.mark.asyncio
    async def test_get_embedding_success(self, embedding_service, mock_openai_client):
        """Testa geração de embedding para um texto."""
        # Arrange
        test_text = "Texto de exemplo para gerar embedding"
        fake_embedding = [0.1] * EMBEDDING_DIMENSION

        mock_response = Mock()
        mock_response.data = [Mock(embedding=fake_embedding)]
        mock_openai_client.embeddings.create.return_value = mock_response

        # Act
        result = await embedding_service.get_embedding(test_text)

        # Assert
        assert len(result) == EMBEDDING_DIMENSION
        assert result == fake_embedding
        mock_openai_client.embeddings.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_embedding_empty_text_raises(self, embedding_service):
        """Testa que texto vazio lança exceção."""
        with pytest.raises(ValueError, match="Texto não pode estar vazio"):
            await embedding_service.get_embedding("")

    @pytest.mark.asyncio
    async def test_get_embedding_whitespace_text_raises(self, embedding_service):
        """Testa que texto só com espaços lança exceção."""
        with pytest.raises(ValueError, match="Texto não pode estar vazio"):
            await embedding_service.get_embedding("   ")

    @pytest.mark.asyncio
    async def test_get_embeddings_batch_success(self, embedding_service, mock_openai_client):
        """Testa geração de embeddings em batch."""
        # Arrange
        texts = ["Texto 1", "Texto 2", "Texto 3"]
        fake_embeddings = [[0.1 * i] * EMBEDDING_DIMENSION for i in range(len(texts))]

        mock_response = Mock()
        mock_response.data = [Mock(embedding=emb) for emb in fake_embeddings]
        mock_openai_client.embeddings.create.return_value = mock_response

        # Act
        results = await embedding_service.get_embeddings_batch(texts, batch_size=10)

        # Assert
        assert len(results) == len(texts)
        for result in results:
            assert len(result) == EMBEDDING_DIMENSION

    @pytest.mark.asyncio
    async def test_get_embeddings_batch_empty_list_raises(self, embedding_service):
        """Testa que lista vazia lança exceção."""
        with pytest.raises(ValueError, match="Lista de textos não pode estar vazia"):
            await embedding_service.get_embeddings_batch([])


class TestSearchIndexSchema:
    """Testes para o schema do índice."""

    def test_get_index_schema_returns_valid_index(self):
        """Testa que o schema do índice é válido."""
        from src.search.search_index import get_index_schema

        index = get_index_schema()

        # Verifica campos obrigatórios
        field_names = [f.name for f in index.fields]

        assert "id" in field_names
        assert "document_id" in field_names
        assert "client_id" in field_names
        assert "content" in field_names
        assert "content_vector" in field_names
        assert "page_number" in field_names
        assert "section_title" in field_names

    def test_index_has_vector_search_config(self):
        """Testa que o índice tem configuração de busca vetorial."""
        from src.search.search_index import get_index_schema

        index = get_index_schema()

        assert index.vector_search is not None
        assert len(index.vector_search.profiles) > 0

    def test_index_uses_portuguese_analyzer(self):
        """Testa que o campo content usa analyzer português."""
        from src.search.search_index import get_index_schema

        index = get_index_schema()

        content_field = next((f for f in index.fields if f.name == "content"), None)
        assert content_field is not None
        assert content_field.analyzer_name == "pt-Br.lucene"


class TestSearchIndexManager:
    """Testes para o gerenciador de índice."""

    @pytest.fixture
    def mock_search_index_client(self):
        """Mock do SearchIndexClient."""
        with patch("src.search.search_index.SearchIndexClient") as mock:
            client_instance = Mock()
            mock.return_value = client_instance
            yield client_instance

    @pytest.fixture
    def index_manager(self, mock_search_index_client):
        """Fixture do SearchIndexManager com cliente mockado."""
        from src.search.search_index import SearchIndexManager

        # Reset singleton
        import src.search.search_index as module
        module._index_manager = None

        return SearchIndexManager()

    @pytest.mark.asyncio
    async def test_index_exists_true(self, index_manager, mock_search_index_client):
        """Testa verificação quando índice existe."""
        mock_search_index_client.list_index_names.return_value = ["contracts-index", "other-index"]

        result = await index_manager.index_exists()

        assert result is True

    @pytest.mark.asyncio
    async def test_index_exists_false(self, index_manager, mock_search_index_client):
        """Testa verificação quando índice não existe."""
        mock_search_index_client.list_index_names.return_value = ["other-index"]

        result = await index_manager.index_exists()

        assert result is False

    @pytest.mark.asyncio
    async def test_create_or_update_index(self, index_manager, mock_search_index_client):
        """Testa criação/atualização do índice."""
        mock_index = Mock()
        mock_index.name = "contracts-index"
        mock_index.fields = [Mock()] * 15  # 15 campos no schema
        mock_search_index_client.create_or_update_index.return_value = mock_index

        result = await index_manager.create_or_update_index()

        assert result.name == "contracts-index"
        mock_search_index_client.create_or_update_index.assert_called_once()


class TestDocumentIndexer:
    """Testes para o indexador de documentos."""

    @pytest.fixture
    def mock_search_client(self):
        """Mock do SearchClient."""
        with patch("src.search.indexer.SearchClient") as mock:
            client_instance = Mock()
            mock.return_value = client_instance
            yield client_instance

    @pytest.fixture
    def mock_embedding_service(self):
        """Mock do EmbeddingService."""
        with patch("src.search.indexer.get_embedding_service") as mock:
            service_instance = Mock()
            service_instance.get_embeddings_batch = AsyncMock(
                return_value=[[0.1] * EMBEDDING_DIMENSION]
            )
            mock.return_value = service_instance
            yield service_instance

    @pytest.fixture
    def document_indexer(self, mock_search_client, mock_embedding_service):
        """Fixture do DocumentIndexer com clientes mockados."""
        from src.search.indexer import DocumentIndexer

        # Reset singleton
        import src.search.indexer as module
        module._indexer = None

        return DocumentIndexer()

    @pytest.fixture
    def sample_chunk(self):
        """Fixture de um chunk de exemplo."""
        return DocumentChunk(
            id=uuid4(),
            document_id=uuid4(),
            client_id="client-123",
            content="Conteúdo do chunk de teste",
            chunk_index=0,
            total_chunks=1,
            page_number=1,
            section_title="CLÁUSULA 1",
            section_type="clausula",
            strategy=ChunkingStrategy.HYBRID,
            created_at=datetime.utcnow(),
        )

    def test_chunk_to_document_format(self, document_indexer, sample_chunk):
        """Testa conversão de chunk para formato do índice."""
        fake_embedding = [0.1] * EMBEDDING_DIMENSION

        doc = document_indexer._chunk_to_document(sample_chunk, fake_embedding)

        assert doc["id"] == str(sample_chunk.id)
        assert doc["document_id"] == str(sample_chunk.document_id)
        assert doc["client_id"] == sample_chunk.client_id
        assert doc["content"] == sample_chunk.content
        assert doc["content_vector"] == fake_embedding
        assert doc["page_number"] == sample_chunk.page_number
        assert doc["section_title"] == sample_chunk.section_title
        assert doc["strategy"] == "hybrid"

    @pytest.mark.asyncio
    async def test_index_chunks_success(
        self, document_indexer, mock_search_client, mock_embedding_service, sample_chunk
    ):
        """Testa indexação de chunks com sucesso."""
        # Arrange
        mock_result = Mock()
        mock_result.succeeded = True
        mock_result.key = str(sample_chunk.id)
        mock_search_client.upload_documents.return_value = [mock_result]

        # Act
        result = await document_indexer.index_chunks([sample_chunk])

        # Assert
        assert result["indexed_count"] == 1
        assert result["failed_count"] == 0
        assert result["errors"] == []
        mock_embedding_service.get_embeddings_batch.assert_called_once()
        mock_search_client.upload_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_chunks_empty_list(self, document_indexer):
        """Testa indexação com lista vazia."""
        result = await document_indexer.index_chunks([])

        assert result["indexed_count"] == 0
        assert result["failed_count"] == 0

    @pytest.mark.asyncio
    async def test_index_chunks_with_failures(
        self, document_indexer, mock_search_client, mock_embedding_service, sample_chunk
    ):
        """Testa indexação com algumas falhas."""
        # Arrange
        mock_result = Mock()
        mock_result.succeeded = False
        mock_result.key = str(sample_chunk.id)
        mock_result.error_message = "Erro de teste"
        mock_search_client.upload_documents.return_value = [mock_result]

        # Act
        result = await document_indexer.index_chunks([sample_chunk])

        # Assert
        assert result["indexed_count"] == 0
        assert result["failed_count"] == 1
        assert len(result["errors"]) == 1
        assert result["errors"][0]["error"] == "Erro de teste"

    @pytest.mark.asyncio
    async def test_delete_document_chunks(
        self, document_indexer, mock_search_client
    ):
        """Testa remoção de chunks de um documento."""
        # Arrange
        doc_id = str(uuid4())
        client_id = "client-123"
        chunk_ids = [str(uuid4()), str(uuid4())]

        # Mock da busca retornando chunks
        mock_search_client.search.return_value = [
            {"id": chunk_ids[0]},
            {"id": chunk_ids[1]},
        ]

        # Mock da deleção
        mock_delete_result = Mock()
        mock_delete_result.succeeded = True
        mock_search_client.delete_documents.return_value = [
            mock_delete_result, mock_delete_result
        ]

        # Act
        result = await document_indexer.delete_document_chunks(doc_id, client_id)

        # Assert
        assert result["deleted_count"] == 2
        mock_search_client.delete_documents.assert_called_once()


class TestIntegration:
    """Testes de integração entre componentes."""

    def test_document_chunk_model_compatibility(self):
        """Verifica que DocumentChunk tem todos os campos necessários para indexação."""
        from src.search.search_index import get_index_schema

        index = get_index_schema()
        index_field_names = {f.name for f in index.fields}

        # Campos do DocumentChunk que devem mapear para o índice
        chunk_fields = {
            "id",
            "document_id",
            "client_id",
            "content",
            "content_length",
            "page_number",
            "page_start",
            "page_end",
            "section_title",
            "section_number",
            "section_type",
            "chunk_index",
            "total_chunks",
            "strategy",
            "created_at",
        }

        # Todos os campos do chunk devem existir no índice (exceto content_vector que é derivado)
        mapped_fields = chunk_fields.intersection(index_field_names)
        assert len(mapped_fields) == len(chunk_fields)
