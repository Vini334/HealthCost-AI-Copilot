"""
Serviço de geração de embeddings via Azure OpenAI.

Este serviço converte texto em vetores numéricos (embeddings) que serão
usados para busca semântica no Azure AI Search.
"""

import asyncio
from typing import Optional

from openai import AzureOpenAI

from src.config.logging import get_logger
from src.config.settings import get_settings

logger = get_logger(__name__)

# Dimensão do modelo text-embedding-3-small
EMBEDDING_DIMENSION = 1536


class EmbeddingService:
    """
    Serviço para geração de embeddings usando Azure OpenAI.

    Usa o modelo text-embedding-3-small (ou configurado) para gerar
    vetores de 1536 dimensões a partir de texto.

    Exemplo:
        service = EmbeddingService()
        embedding = await service.get_embedding("Texto do contrato...")
        embeddings = await service.get_embeddings_batch(["Texto 1", "Texto 2"])
    """

    def __init__(self):
        """Inicializa o serviço com configurações do Azure OpenAI."""
        settings = get_settings()

        self.client = AzureOpenAI(
            api_key=settings.azure_openai.api_key,
            api_version=settings.azure_openai.api_version,
            azure_endpoint=settings.azure_openai.endpoint,
        )
        self.deployment_name = settings.azure_openai.embedding_deployment

        logger.info(
            "EmbeddingService inicializado",
            deployment=self.deployment_name,
        )

    async def get_embedding(self, text: str) -> list[float]:
        """
        Gera embedding para um único texto.

        Args:
            text: Texto para gerar embedding

        Returns:
            Lista de floats representando o vetor de embedding

        Raises:
            ValueError: Se texto estiver vazio
            Exception: Se falha na API do Azure OpenAI
        """
        if not text or not text.strip():
            raise ValueError("Texto não pode estar vazio")

        # Limitar tamanho do texto (8191 tokens ~ 32000 chars aprox.)
        text = text[:32000]

        logger.debug(
            "Gerando embedding",
            text_length=len(text),
        )

        try:
            # Executar chamada síncrona em thread separada para não bloquear
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.embeddings.create(
                    input=text,
                    model=self.deployment_name,
                ),
            )

            embedding = response.data[0].embedding

            logger.debug(
                "Embedding gerado",
                dimensions=len(embedding),
            )

            return embedding

        except Exception as e:
            logger.error(
                "Erro ao gerar embedding",
                error=str(e),
                text_length=len(text),
            )
            raise

    async def get_embeddings_batch(
        self,
        texts: list[str],
        batch_size: int = 16,
    ) -> list[list[float]]:
        """
        Gera embeddings para múltiplos textos em lotes.

        Processa em batches para respeitar limites da API e otimizar performance.

        Args:
            texts: Lista de textos para gerar embeddings
            batch_size: Tamanho do lote (máximo recomendado: 16)

        Returns:
            Lista de embeddings na mesma ordem dos textos

        Raises:
            ValueError: Se lista estiver vazia
        """
        if not texts:
            raise ValueError("Lista de textos não pode estar vazia")

        logger.info(
            "Gerando embeddings em batch",
            total_texts=len(texts),
            batch_size=batch_size,
        )

        all_embeddings: list[list[float]] = []

        # Processar em batches
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            # Limpar e truncar textos do batch
            cleaned_batch = [t[:32000] if t else " " for t in batch]

            try:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda b=cleaned_batch: self.client.embeddings.create(
                        input=b,
                        model=self.deployment_name,
                    ),
                )

                # Extrair embeddings na ordem correta
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)

                logger.debug(
                    "Batch processado",
                    batch_index=i // batch_size,
                    batch_size=len(batch),
                )

            except Exception as e:
                logger.error(
                    "Erro ao processar batch de embeddings",
                    batch_index=i // batch_size,
                    error=str(e),
                )
                raise

        logger.info(
            "Embeddings gerados com sucesso",
            total_embeddings=len(all_embeddings),
        )

        return all_embeddings


# Singleton
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Retorna instância singleton do serviço de embeddings."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
