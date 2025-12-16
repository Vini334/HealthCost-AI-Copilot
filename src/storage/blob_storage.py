"""
Cliente para Azure Blob Storage.

Responsável por:
- Upload de arquivos (contratos e planilhas)
- Download de arquivos
- Gerenciamento de blobs por cliente (multi-tenancy)
"""

from typing import BinaryIO, Optional

from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError

from src.config.settings import get_settings
from src.config.logging import get_logger

logger = get_logger(__name__)


class BlobStorageClient:
    """
    Cliente para operações no Azure Blob Storage.

    Organiza arquivos em estrutura multi-tenant:
        {container}/{client_id}/{document_id}/{filename}

    Exemplo:
        contracts/cliente-abc/doc-123/contrato-2024.pdf
    """

    def __init__(self) -> None:
        """
        Inicializa o cliente com as configurações do Azure.

        A conexão é feita via connection string definida em AZURE_STORAGE_CONNECTION_STRING.
        """
        settings = get_settings()
        self._connection_string = settings.azure_storage.connection_string

        # BlobServiceClient é o ponto de entrada para todas operações
        # Ele gerencia a conexão com a conta de storage
        self._service_client = BlobServiceClient.from_connection_string(
            self._connection_string
        )

        # Nomes dos containers configurados
        self._container_contracts = settings.azure_storage.container_contracts
        self._container_costs = settings.azure_storage.container_costs
        self._container_processed = settings.azure_storage.container_processed

        logger.info(
            "BlobStorageClient inicializado",
            containers={
                "contracts": self._container_contracts,
                "costs": self._container_costs,
                "processed": self._container_processed,
            },
        )

    def _ensure_container_exists(self, container_name: str) -> None:
        """
        Garante que o container existe, criando se necessário.

        Args:
            container_name: Nome do container
        """
        try:
            container_client = self._service_client.get_container_client(container_name)
            container_client.create_container()
            logger.info("Container criado", container=container_name)
        except ResourceExistsError:
            # Container já existe, tudo ok
            pass

    def _build_blob_path(
        self,
        client_id: str,
        document_id: str,
        filename: str,
    ) -> str:
        """
        Constrói o caminho do blob seguindo padrão multi-tenant.

        Args:
            client_id: ID do cliente
            document_id: ID do documento
            filename: Nome do arquivo

        Returns:
            Caminho no formato: {client_id}/{document_id}/{filename}
        """
        # Sanitiza os componentes para evitar problemas
        safe_client_id = client_id.replace("/", "_").replace("\\", "_")
        safe_doc_id = str(document_id).replace("/", "_").replace("\\", "_")
        safe_filename = filename.replace("/", "_").replace("\\", "_")

        return f"{safe_client_id}/{safe_doc_id}/{safe_filename}"

    async def upload_contract(
        self,
        file_content: BinaryIO,
        client_id: str,
        document_id: str,
        filename: str,
        content_type: str = "application/pdf",
    ) -> str:
        """
        Faz upload de um contrato PDF.

        Args:
            file_content: Conteúdo binário do arquivo (file-like object)
            client_id: ID do cliente dono do documento
            document_id: ID único do documento
            filename: Nome original do arquivo
            content_type: MIME type (padrão: application/pdf)

        Returns:
            Caminho completo do blob (blob_path)

        Raises:
            Exception: Se o upload falhar
        """
        container_name = self._container_contracts
        blob_path = self._build_blob_path(client_id, document_id, filename)

        logger.info(
            "Iniciando upload de contrato",
            client_id=client_id,
            document_id=document_id,
            filename=filename,
            container=container_name,
            blob_path=blob_path,
        )

        # Garante que o container existe
        self._ensure_container_exists(container_name)

        # Obtém o client para este blob específico
        blob_client = self._service_client.get_blob_client(
            container=container_name,
            blob=blob_path,
        )

        # ContentSettings define metadados HTTP do blob
        # Isso ajuda navegadores e outros clientes a entender o tipo de arquivo
        content_settings = ContentSettings(content_type=content_type)

        # Upload do arquivo
        # overwrite=True substitui se já existir (útil para re-uploads)
        blob_client.upload_blob(
            file_content,
            overwrite=True,
            content_settings=content_settings,
        )

        logger.info(
            "Upload de contrato concluído",
            blob_path=blob_path,
            container=container_name,
        )

        return blob_path

    async def upload_costs(
        self,
        file_content: BinaryIO,
        client_id: str,
        document_id: str,
        filename: str,
        content_type: str,
    ) -> str:
        """
        Faz upload de dados de custos (CSV/Excel).

        Args:
            file_content: Conteúdo binário do arquivo
            client_id: ID do cliente
            document_id: ID único do documento
            filename: Nome original do arquivo
            content_type: MIME type do arquivo

        Returns:
            Caminho completo do blob

        Raises:
            Exception: Se o upload falhar
        """
        container_name = self._container_costs
        blob_path = self._build_blob_path(client_id, document_id, filename)

        logger.info(
            "Iniciando upload de dados de custos",
            client_id=client_id,
            document_id=document_id,
            filename=filename,
            content_type=content_type,
            container=container_name,
        )

        self._ensure_container_exists(container_name)

        blob_client = self._service_client.get_blob_client(
            container=container_name,
            blob=blob_path,
        )

        content_settings = ContentSettings(content_type=content_type)

        blob_client.upload_blob(
            file_content,
            overwrite=True,
            content_settings=content_settings,
        )

        logger.info(
            "Upload de dados de custos concluído",
            blob_path=blob_path,
        )

        return blob_path

    async def download_blob(
        self,
        container_name: str,
        blob_path: str,
    ) -> bytes:
        """
        Faz download de um blob.

        Args:
            container_name: Nome do container
            blob_path: Caminho do blob

        Returns:
            Conteúdo do arquivo em bytes

        Raises:
            ResourceNotFoundError: Se o blob não existir
        """
        logger.info(
            "Baixando blob",
            container=container_name,
            blob_path=blob_path,
        )

        blob_client = self._service_client.get_blob_client(
            container=container_name,
            blob=blob_path,
        )

        download_stream = blob_client.download_blob()
        content = download_stream.readall()

        logger.info(
            "Download concluído",
            size_bytes=len(content),
        )

        return content

    async def delete_blob(
        self,
        container_name: str,
        blob_path: str,
    ) -> bool:
        """
        Remove um blob do storage.

        Args:
            container_name: Nome do container
            blob_path: Caminho do blob

        Returns:
            True se removido, False se não existia
        """
        try:
            blob_client = self._service_client.get_blob_client(
                container=container_name,
                blob=blob_path,
            )
            blob_client.delete_blob()
            logger.info("Blob removido", blob_path=blob_path)
            return True
        except ResourceNotFoundError:
            logger.warning("Blob não encontrado para remoção", blob_path=blob_path)
            return False

    async def blob_exists(
        self,
        container_name: str,
        blob_path: str,
    ) -> bool:
        """
        Verifica se um blob existe.

        Args:
            container_name: Nome do container
            blob_path: Caminho do blob

        Returns:
            True se existir, False caso contrário
        """
        blob_client = self._service_client.get_blob_client(
            container=container_name,
            blob=blob_path,
        )
        return blob_client.exists()


# Instância singleton para uso na aplicação
# Usamos uma função para lazy initialization (cria só quando precisa)
_blob_client: Optional[BlobStorageClient] = None


def get_blob_storage_client() -> BlobStorageClient:
    """
    Retorna instância singleton do cliente de Blob Storage.

    Singleton significa que existe apenas uma instância compartilhada
    em toda a aplicação, evitando criar múltiplas conexões.
    """
    global _blob_client
    if _blob_client is None:
        _blob_client = BlobStorageClient()
    return _blob_client
