"""
Serviço de processamento de contratos.

Orquestra todo o fluxo de processamento:
1. Baixar PDF do Blob Storage
2. Extrair texto
3. Criar chunks
4. Gerar embeddings via Azure OpenAI
5. Indexar no Azure AI Search
6. Atualizar status no Cosmos DB
"""

import time
from typing import Optional, Union
from uuid import UUID

from src.config.logging import get_logger
from src.ingestion.pdf_extractor import PDFExtractor
from src.ingestion.chunker import TextChunker
from src.models.chunks import (
    ChunkingConfig,
    DocumentChunk,
    ProcessingResult,
    DEFAULT_CHUNKING_CONFIG,
)
from src.models.documents import DocumentMetadata, DocumentStatus
from src.storage.blob_storage import get_blob_storage_client
from src.storage.cosmos_db import get_cosmos_client
from src.search.indexer import get_document_indexer

logger = get_logger(__name__)


class ContractProcessor:
    """
    Processa contratos PDF para indexação.

    Fluxo completo:
        PDF (Blob Storage)
            ↓
        Extração de texto (pdfplumber)
            ↓
        Chunking (seções/páginas)
            ↓
        Chunks prontos para embedding

    Exemplo de uso:
        processor = ContractProcessor()
        result = await processor.process_document(
            document_id="abc-123",
            client_id="cliente-456"
        )
        if result.success:
            print(f"Criados {result.total_chunks} chunks")
    """

    def __init__(
        self,
        chunking_config: Optional[ChunkingConfig] = None,
        enable_indexing: bool = True,
    ):
        """
        Inicializa o processador.

        Args:
            chunking_config: Configuração de chunking (opcional)
            enable_indexing: Se True, indexa chunks no Azure AI Search (padrão: True)
        """
        self.chunking_config = chunking_config or DEFAULT_CHUNKING_CONFIG
        self.pdf_extractor = PDFExtractor()
        self.chunker = TextChunker(self.chunking_config)
        self.enable_indexing = enable_indexing

        logger.info(
            "ContractProcessor inicializado",
            enable_indexing=enable_indexing,
        )

    async def process_document(
        self,
        document_id: Union[str, UUID],
        client_id: str,
    ) -> ProcessingResult:
        """
        Processa um documento já armazenado.

        Este método:
        1. Busca metadados do documento no Cosmos DB
        2. Baixa o PDF do Blob Storage
        3. Extrai texto
        4. Cria chunks
        5. Atualiza status do documento

        Args:
            document_id: ID do documento (UUID)
            client_id: ID do cliente

        Returns:
            ProcessingResult com os chunks criados

        Raises:
            ValueError: Se documento não encontrado
        """
        start_time = time.time()
        doc_id = str(document_id)

        logger.info(
            "Iniciando processamento de documento",
            document_id=doc_id,
            client_id=client_id,
        )

        # 1. Buscar metadados do documento
        cosmos_client = get_cosmos_client()
        metadata = await cosmos_client.get_document_metadata(doc_id, client_id)

        if not metadata:
            logger.error("Documento não encontrado", document_id=doc_id)
            return ProcessingResult(
                document_id=UUID(doc_id),
                success=False,
                error_message="Documento não encontrado",
            )

        # 2. Atualizar status para PROCESSING
        await cosmos_client.update_document_status(
            document_id=doc_id,
            client_id=client_id,
            status=DocumentStatus.PROCESSING,
        )

        try:
            # 3. Baixar PDF do Blob Storage
            logger.info(
                "Baixando PDF do Blob Storage",
                blob_path=metadata.blob_path,
                container=metadata.container_name,
            )

            blob_client = get_blob_storage_client()
            pdf_bytes = await blob_client.download_blob(
                container_name=metadata.container_name,
                blob_path=metadata.blob_path,
            )

            logger.info("PDF baixado", size_bytes=len(pdf_bytes))

            # 4. Extrair texto do PDF
            extraction_result = self.pdf_extractor.extract_from_bytes(pdf_bytes)

            if not extraction_result.success:
                raise Exception(
                    f"Falha na extração: {extraction_result.error_message}"
                )

            logger.info(
                "Texto extraído",
                pages=extraction_result.total_pages,
                chars=extraction_result.total_characters,
            )

            # 5. Criar chunks
            chunks = self.chunker.chunk_pages(
                pages=extraction_result.pages,
                document_id=metadata.id,
                client_id=client_id,
                document_name=metadata.filename,
            )

            logger.info("Chunks criados", total_chunks=len(chunks))

            # 6. Indexar no Azure AI Search (se habilitado)
            indexed_count = 0
            if self.enable_indexing and chunks:
                logger.info("Iniciando indexação no Azure AI Search")

                # Remove chunks anteriores deste documento (se houver)
                indexer = get_document_indexer()
                await indexer.delete_document_chunks(doc_id, client_id)

                # Indexa os novos chunks
                indexing_result = await indexer.index_chunks(chunks)
                indexed_count = indexing_result["indexed_count"]

                logger.info(
                    "Indexação concluída",
                    indexed_count=indexed_count,
                    failed_count=indexing_result["failed_count"],
                )

                if indexing_result["failed_count"] > 0:
                    logger.warning(
                        "Alguns chunks falharam na indexação",
                        failed_count=indexing_result["failed_count"],
                        errors=indexing_result["errors"],
                    )

            # 7. Atualizar status para INDEXED
            await cosmos_client.update_document_status(
                document_id=doc_id,
                client_id=client_id,
                status=DocumentStatus.INDEXED,
            )

            # Calcular tempo de processamento
            processing_time = time.time() - start_time

            logger.info(
                "Processamento concluído com sucesso",
                document_id=doc_id,
                total_chunks=len(chunks),
                indexed_chunks=indexed_count,
                processing_time_seconds=round(processing_time, 2),
            )

            return ProcessingResult(
                document_id=metadata.id,
                success=True,
                total_pages=extraction_result.total_pages,
                total_chunks=len(chunks),
                total_characters=extraction_result.total_characters,
                chunks=chunks,
                processing_time_seconds=processing_time,
                indexed_count=indexed_count if self.enable_indexing else None,
            )

        except Exception as e:
            # Em caso de erro, atualizar status para FAILED
            logger.error(
                "Erro no processamento",
                document_id=doc_id,
                error=str(e),
            )

            await cosmos_client.update_document_status(
                document_id=doc_id,
                client_id=client_id,
                status=DocumentStatus.FAILED,
                error_message=str(e),
            )

            processing_time = time.time() - start_time

            return ProcessingResult(
                document_id=UUID(doc_id),
                success=False,
                error_message=str(e),
                processing_time_seconds=processing_time,
            )

    async def process_bytes(
        self,
        pdf_bytes: bytes,
        document_id: UUID,
        client_id: str,
        document_name: Optional[str] = None,
    ) -> ProcessingResult:
        """
        Processa um PDF diretamente de bytes.

        Versão que não depende de Blob Storage.
        Útil para testes ou processamento inline.

        Args:
            pdf_bytes: Conteúdo do PDF
            document_id: ID do documento
            client_id: ID do cliente
            document_name: Nome do documento (opcional)

        Returns:
            ProcessingResult com os chunks
        """
        start_time = time.time()

        logger.info(
            "Processando PDF de bytes",
            size_bytes=len(pdf_bytes),
            document_id=str(document_id),
        )

        try:
            # Extrair texto
            extraction_result = self.pdf_extractor.extract_from_bytes(pdf_bytes)

            if not extraction_result.success:
                return ProcessingResult(
                    document_id=document_id,
                    success=False,
                    error_message=extraction_result.error_message,
                )

            # Criar chunks
            chunks = self.chunker.chunk_pages(
                pages=extraction_result.pages,
                document_id=document_id,
                client_id=client_id,
                document_name=document_name,
            )

            processing_time = time.time() - start_time

            return ProcessingResult(
                document_id=document_id,
                success=True,
                total_pages=extraction_result.total_pages,
                total_chunks=len(chunks),
                total_characters=extraction_result.total_characters,
                chunks=chunks,
                processing_time_seconds=processing_time,
            )

        except Exception as e:
            logger.error("Erro no processamento", error=str(e))
            return ProcessingResult(
                document_id=document_id,
                success=False,
                error_message=str(e),
                processing_time_seconds=time.time() - start_time,
            )


# Singleton
_processor: Optional[ContractProcessor] = None


def get_contract_processor() -> ContractProcessor:
    """Retorna instância singleton do processador."""
    global _processor
    if _processor is None:
        _processor = ContractProcessor()
    return _processor
