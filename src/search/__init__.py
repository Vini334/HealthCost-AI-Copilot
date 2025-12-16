"""
Módulo de busca e indexação.

Este módulo contém os serviços para:
- Geração de embeddings via Azure OpenAI
- Gerenciamento do índice Azure AI Search
- Indexação de chunks de documentos
- Busca semântica (vetorial, keyword, híbrida)
"""

from src.search.embedding_service import (
    EmbeddingService,
    get_embedding_service,
    EMBEDDING_DIMENSION,
)
from src.search.search_index import (
    SearchIndexManager,
    get_search_index_manager,
    get_index_schema,
    VECTOR_SEARCH_PROFILE,
)
from src.search.indexer import (
    DocumentIndexer,
    get_document_indexer,
)
from src.search.search_service import (
    SearchService,
    get_search_service,
    SearchMode,
    SearchResult,
    SearchResponse,
)

__all__ = [
    # Embedding Service
    "EmbeddingService",
    "get_embedding_service",
    "EMBEDDING_DIMENSION",
    # Search Index
    "SearchIndexManager",
    "get_search_index_manager",
    "get_index_schema",
    "VECTOR_SEARCH_PROFILE",
    # Document Indexer
    "DocumentIndexer",
    "get_document_indexer",
    # Search Service
    "SearchService",
    "get_search_service",
    "SearchMode",
    "SearchResult",
    "SearchResponse",
]
