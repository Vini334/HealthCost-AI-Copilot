"""
Serviço de indexação de documentos no Azure AI Search.

Este módulo é responsável por indexar chunks de documentos
junto com seus embeddings no Azure AI Search.
"""

from typing import Optional, Union
from uuid import UUID

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import IndexingResult

from src.config.logging import get_logger
from src.config.settings import get_settings
from src.models.chunks import DocumentChunk
from src.search.embedding_service import get_embedding_service

logger = get_logger(__name__)


class DocumentIndexer:
    """
    Serviço para indexar chunks no Azure AI Search.

    Responsável por:
    1. Gerar embeddings para chunks
    2. Formatar documentos para o índice
    3. Enviar para o Azure AI Search

    Exemplo:
        indexer = DocumentIndexer()
        result = await indexer.index_chunks(chunks)
        print(f"Indexados: {result['indexed_count']} chunks")
    """

    def __init__(self):
        """Inicializa o indexador com configurações do Azure AI Search."""
        settings = get_settings()

        self.search_client = SearchClient(
            endpoint=settings.azure_search.endpoint,
            index_name=settings.azure_search.index_name,
            credential=AzureKeyCredential(settings.azure_search.api_key),
        )
        self.embedding_service = get_embedding_service()
        self.index_name = settings.azure_search.index_name

        logger.info(
            "DocumentIndexer inicializado",
            index_name=self.index_name,
        )

    def _chunk_to_document(
        self,
        chunk: DocumentChunk,
        embedding: list[float],
    ) -> dict:
        """
        Converte um DocumentChunk para formato do Azure AI Search.

        Args:
            chunk: Chunk do documento
            embedding: Vetor de embedding do conteúdo

        Returns:
            Dicionário formatado para indexação
        """
        return {
            "id": str(chunk.id),
            "document_id": str(chunk.document_id),
            "client_id": chunk.client_id,
            "content": chunk.content,
            "content_vector": embedding,
            "content_length": chunk.content_length,
            "page_number": chunk.page_number,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "section_title": chunk.section_title,
            "section_number": chunk.section_number,
            "section_type": chunk.section_type,
            "chunk_index": chunk.chunk_index,
            "total_chunks": chunk.total_chunks,
            "strategy": chunk.strategy.value if chunk.strategy else None,
            "created_at": f"{chunk.created_at.isoformat()}Z" if chunk.created_at else None,
        }

    async def index_chunks(
        self,
        chunks: list[DocumentChunk],
        batch_size: int = 16,
    ) -> dict:
        """
        Indexa uma lista de chunks no Azure AI Search.

        Este método:
        1. Gera embeddings para todos os chunks em batch
        2. Converte chunks para formato do índice
        3. Envia para o Azure AI Search

        Args:
            chunks: Lista de DocumentChunk para indexar
            batch_size: Tamanho do lote para geração de embeddings

        Returns:
            Dicionário com estatísticas da indexação:
            - indexed_count: Número de chunks indexados com sucesso
            - failed_count: Número de falhas
            - errors: Lista de erros (se houver)
        """
        if not chunks:
            logger.warning("Nenhum chunk para indexar")
            return {
                "indexed_count": 0,
                "failed_count": 0,
                "errors": [],
            }

        logger.info(
            "Iniciando indexação de chunks",
            total_chunks=len(chunks),
        )

        # 1. Extrair conteúdos para gerar embeddings
        contents = [chunk.content for chunk in chunks]

        # 2. Gerar embeddings em batch
        logger.info("Gerando embeddings para chunks")
        embeddings = await self.embedding_service.get_embeddings_batch(
            texts=contents,
            batch_size=batch_size,
        )

        # 3. Criar documentos para indexação
        documents = [
            self._chunk_to_document(chunk, embedding)
            for chunk, embedding in zip(chunks, embeddings)
        ]

        # 4. Indexar documentos no Azure AI Search
        logger.info("Enviando documentos para Azure AI Search")

        import asyncio

        try:
            loop = asyncio.get_event_loop()
            results: list[IndexingResult] = await loop.run_in_executor(
                None,
                lambda: self.search_client.upload_documents(documents=documents),
            )

            # 5. Processar resultados
            indexed_count = sum(1 for r in results if r.succeeded)
            failed_count = sum(1 for r in results if not r.succeeded)
            errors = [
                {"key": r.key, "error": r.error_message}
                for r in results
                if not r.succeeded
            ]

            logger.info(
                "Indexação concluída",
                indexed_count=indexed_count,
                failed_count=failed_count,
            )

            if errors:
                logger.warning(
                    "Alguns chunks falharam na indexação",
                    errors=errors,
                )

            return {
                "indexed_count": indexed_count,
                "failed_count": failed_count,
                "errors": errors,
            }

        except Exception as e:
            logger.error(
                "Erro na indexação",
                error=str(e),
            )
            raise

    async def index_single_chunk(
        self,
        chunk: DocumentChunk,
    ) -> bool:
        """
        Indexa um único chunk.

        Útil para atualizações incrementais.

        Args:
            chunk: Chunk para indexar

        Returns:
            True se indexado com sucesso
        """
        result = await self.index_chunks([chunk])
        return result["indexed_count"] == 1

    async def delete_document_chunks(
        self,
        document_id: Union[str, UUID],
        client_id: str,
    ) -> dict:
        """
        Remove todos os chunks de um documento do índice.

        Útil quando um documento é reprocessado ou removido.

        Args:
            document_id: ID do documento
            client_id: ID do cliente (para validação)

        Returns:
            Dicionário com contagem de chunks removidos
        """
        import asyncio

        doc_id = str(document_id)

        logger.info(
            "Removendo chunks do documento",
            document_id=doc_id,
            client_id=client_id,
        )

        try:
            # Primeiro, buscar IDs dos chunks deste documento
            loop = asyncio.get_event_loop()

            # Busca todos os chunks do documento
            search_results = await loop.run_in_executor(
                None,
                lambda: self.search_client.search(
                    search_text="*",
                    filter=f"document_id eq '{doc_id}' and client_id eq '{client_id}'",
                    select=["id"],
                ),
            )

            # Coletar IDs dos chunks
            chunk_ids = [result["id"] for result in search_results]

            if not chunk_ids:
                logger.info(
                    "Nenhum chunk encontrado para remoção",
                    document_id=doc_id,
                )
                return {"deleted_count": 0}

            # Criar documentos para deleção
            documents_to_delete = [{"id": chunk_id} for chunk_id in chunk_ids]

            # Deletar chunks
            results = await loop.run_in_executor(
                None,
                lambda: self.search_client.delete_documents(
                    documents=documents_to_delete
                ),
            )

            deleted_count = sum(1 for r in results if r.succeeded)

            logger.info(
                "Chunks removidos com sucesso",
                document_id=doc_id,
                deleted_count=deleted_count,
            )

            return {"deleted_count": deleted_count}

        except Exception as e:
            logger.error(
                "Erro ao remover chunks",
                document_id=doc_id,
                error=str(e),
            )
            raise

    async def get_document_chunk_count(
        self,
        document_id: Union[str, UUID],
        client_id: str,
    ) -> int:
        """
        Retorna o número de chunks indexados de um documento.

        Args:
            document_id: ID do documento
            client_id: ID do cliente

        Returns:
            Número de chunks indexados
        """
        import asyncio

        doc_id = str(document_id)

        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: self.search_client.search(
                    search_text="*",
                    filter=f"document_id eq '{doc_id}' and client_id eq '{client_id}'",
                    include_total_count=True,
                ),
            )

            # Precisamos consumir o iterator para obter count
            count = 0
            for _ in results:
                count += 1

            return count

        except Exception as e:
            logger.error(
                "Erro ao contar chunks",
                document_id=doc_id,
                error=str(e),
            )
            raise


# Singleton
_indexer: Optional[DocumentIndexer] = None


def get_document_indexer() -> DocumentIndexer:
    """Retorna instância singleton do indexador."""
    global _indexer
    if _indexer is None:
        _indexer = DocumentIndexer()
    return _indexer
