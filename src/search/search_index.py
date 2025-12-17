"""
Definição e gerenciamento do índice Azure AI Search.

Este módulo define o schema do índice de contratos e fornece
métodos para criar/atualizar o índice no Azure AI Search.
"""

from typing import Optional

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SearchableField,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
    HnswAlgorithmConfiguration,
)

from src.config.logging import get_logger
from src.config.settings import get_settings
from src.search.embedding_service import EMBEDDING_DIMENSION

logger = get_logger(__name__)

# Nome do perfil de busca vetorial
VECTOR_SEARCH_PROFILE = "contracts-vector-profile"
VECTOR_ALGORITHM_CONFIG = "contracts-hnsw-config"


def get_index_schema() -> SearchIndex:
    """
    Define o schema do índice de contratos.

    O índice contém:
    - Campos de identificação (id, document_id, client_id)
    - Conteúdo do chunk (content - buscável e vetorial)
    - Metadados de localização (page, section)
    - Metadados de processamento (strategy, timestamps)

    Returns:
        SearchIndex configurado com busca híbrida (keyword + vetorial)
    """
    settings = get_settings()
    index_name = settings.azure_search.index_name

    # Configuração do algoritmo HNSW para busca vetorial
    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name=VECTOR_ALGORITHM_CONFIG,
                parameters={
                    "m": 4,  # Número de conexões bi-direcionais
                    "efConstruction": 400,  # Tamanho da lista de candidatos durante indexação
                    "efSearch": 500,  # Tamanho da lista de candidatos durante busca
                    "metric": "cosine",  # Métrica de similaridade
                },
            ),
        ],
        profiles=[
            VectorSearchProfile(
                name=VECTOR_SEARCH_PROFILE,
                algorithm_configuration_name=VECTOR_ALGORITHM_CONFIG,
            ),
        ],
    )

    # Definição dos campos do índice
    fields = [
        # Identificação única do chunk
        SimpleField(
            name="id",
            type=SearchFieldDataType.String,
            key=True,
            filterable=True,
        ),
        # Referência ao documento original
        SimpleField(
            name="document_id",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        # Nome do documento original (para exibição em citações)
        SearchableField(
            name="document_name",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        # Multi-tenancy: filtragem obrigatória por cliente
        SimpleField(
            name="client_id",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        # Conteúdo textual do chunk (buscável por keyword)
        SearchableField(
            name="content",
            type=SearchFieldDataType.String,
            analyzer_name="pt-Br.lucene",  # Analyzer para português brasileiro
        ),
        # Vetor de embedding do conteúdo
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=EMBEDDING_DIMENSION,
            vector_search_profile_name=VECTOR_SEARCH_PROFILE,
        ),
        # Tamanho do conteúdo em caracteres
        SimpleField(
            name="content_length",
            type=SearchFieldDataType.Int32,
            filterable=True,
            sortable=True,
        ),
        # Número da página no PDF
        SimpleField(
            name="page_number",
            type=SearchFieldDataType.Int32,
            filterable=True,
            sortable=True,
        ),
        # Página inicial (para chunks multi-página)
        SimpleField(
            name="page_start",
            type=SearchFieldDataType.Int32,
            filterable=True,
        ),
        # Página final (para chunks multi-página)
        SimpleField(
            name="page_end",
            type=SearchFieldDataType.Int32,
            filterable=True,
        ),
        # Título da seção/cláusula
        SearchableField(
            name="section_title",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        # Número da seção (ex: "5.1", "5.2.1")
        SimpleField(
            name="section_number",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        # Tipo de seção (clausula, paragrafo, anexo)
        SimpleField(
            name="section_type",
            type=SearchFieldDataType.String,
            filterable=True,
            facetable=True,
        ),
        # Índice do chunk no documento
        SimpleField(
            name="chunk_index",
            type=SearchFieldDataType.Int32,
            sortable=True,
        ),
        # Total de chunks do documento
        SimpleField(
            name="total_chunks",
            type=SearchFieldDataType.Int32,
        ),
        # Estratégia de chunking utilizada
        SimpleField(
            name="strategy",
            type=SearchFieldDataType.String,
            filterable=True,
            facetable=True,
        ),
        # Data de criação do chunk
        SimpleField(
            name="created_at",
            type=SearchFieldDataType.DateTimeOffset,
            filterable=True,
            sortable=True,
        ),
    ]

    index = SearchIndex(
        name=index_name,
        fields=fields,
        vector_search=vector_search,
    )

    return index


class SearchIndexManager:
    """
    Gerenciador do índice Azure AI Search.

    Responsável por criar, atualizar e verificar o índice.

    Exemplo:
        manager = SearchIndexManager()
        await manager.create_or_update_index()
        exists = await manager.index_exists()
    """

    def __init__(self):
        """Inicializa o gerenciador com credenciais do Azure AI Search."""
        settings = get_settings()

        self.index_name = settings.azure_search.index_name
        self.client = SearchIndexClient(
            endpoint=settings.azure_search.endpoint,
            credential=AzureKeyCredential(settings.azure_search.api_key),
        )

        logger.info(
            "SearchIndexManager inicializado",
            index_name=self.index_name,
        )

    async def create_or_update_index(self) -> SearchIndex:
        """
        Cria ou atualiza o índice de contratos.

        Se o índice já existir, atualiza o schema.
        Se não existir, cria um novo.

        Returns:
            SearchIndex criado ou atualizado
        """
        import asyncio

        index = get_index_schema()

        logger.info(
            "Criando/atualizando índice",
            index_name=self.index_name,
        )

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.client.create_or_update_index(index),
            )

            logger.info(
                "Índice criado/atualizado com sucesso",
                index_name=result.name,
                fields_count=len(result.fields),
            )

            return result

        except Exception as e:
            logger.error(
                "Erro ao criar/atualizar índice",
                index_name=self.index_name,
                error=str(e),
            )
            raise

    async def index_exists(self) -> bool:
        """
        Verifica se o índice existe.

        Returns:
            True se o índice existir
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            names = await loop.run_in_executor(
                None,
                lambda: list(self.client.list_index_names()),
            )

            return self.index_name in names

        except Exception as e:
            logger.error(
                "Erro ao verificar existência do índice",
                error=str(e),
            )
            raise

    async def delete_index(self) -> None:
        """
        Remove o índice.

        CUIDADO: Esta operação é irreversível e remove todos os dados.
        """
        import asyncio

        logger.warning(
            "Removendo índice",
            index_name=self.index_name,
        )

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.client.delete_index(self.index_name),
            )

            logger.info(
                "Índice removido com sucesso",
                index_name=self.index_name,
            )

        except Exception as e:
            logger.error(
                "Erro ao remover índice",
                index_name=self.index_name,
                error=str(e),
            )
            raise

    async def get_index_stats(self) -> dict:
        """
        Obtém estatísticas do índice.

        Returns:
            Dicionário com estatísticas (document_count, storage_size)
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            index = await loop.run_in_executor(
                None,
                lambda: self.client.get_index(self.index_name),
            )

            return {
                "name": index.name,
                "fields_count": len(index.fields),
            }

        except Exception as e:
            logger.error(
                "Erro ao obter estatísticas do índice",
                error=str(e),
            )
            raise


# Singleton
_index_manager: Optional[SearchIndexManager] = None


def get_search_index_manager() -> SearchIndexManager:
    """Retorna instância singleton do gerenciador de índice."""
    global _index_manager
    if _index_manager is None:
        _index_manager = SearchIndexManager()
    return _index_manager
