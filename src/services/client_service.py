"""
Serviço de gerenciamento de clientes.

Responsável por:
- CRUD de clientes
- Listagem de contratos por cliente
- Status de processamento de documentos
- Estatísticas do cliente
"""

from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from src.config.logging import get_logger
from src.models.clients import (
    Client,
    ClientStatus,
    ClientSummary,
    ClientDetailResponse,
    ClientContractsResponse,
    ContractSummary,
    ProcessingStatusResponse,
    DocumentProcessingStatus,
    ClientStatsResponse,
)
from src.models.documents import DocumentMetadata, DocumentStatus, DocumentType
from src.storage.cosmos_db import get_cosmos_client, CosmosDBClient

logger = get_logger(__name__)


class ClientService:
    """
    Serviço para gerenciamento de clientes.

    Encapsula a lógica de negócios para criar, atualizar,
    listar e recuperar clientes e seus dados associados.
    """

    def __init__(
        self,
        cosmos_client: Optional[CosmosDBClient] = None,
    ):
        """
        Inicializa o serviço.

        Args:
            cosmos_client: Cliente Cosmos DB (opcional, usa singleton se não fornecido)
        """
        self._cosmos = cosmos_client or get_cosmos_client()
        logger.info("ClientService inicializado")

    # ============================================
    # CRUD de Clientes
    # ============================================

    async def create_client(
        self,
        name: str,
        document: str,
        document_type: str = "cnpj",
        email: Optional[str] = None,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Client:
        """
        Cria um novo cliente.

        Args:
            name: Nome/Razão Social
            document: CPF ou CNPJ
            document_type: Tipo do documento ('cpf' ou 'cnpj')
            email: E-mail de contato
            phone: Telefone
            address: Endereço
            city: Cidade
            state: UF
            metadata: Metadados adicionais

        Returns:
            Cliente criado
        """
        client = Client(
            name=name,
            document=document,
            document_type=document_type,
            email=email,
            phone=phone,
            address=address,
            city=city,
            state=state,
            metadata=metadata or {},
        )

        logger.info(
            "Criando novo cliente",
            client_id=str(client.id),
            client_name=name,
        )

        await self._cosmos.create_client(client)

        logger.info(
            "Cliente criado com sucesso",
            client_id=str(client.id),
        )

        return client

    async def get_client(
        self,
        client_id: str,
    ) -> Optional[Client]:
        """
        Busca um cliente por ID.

        Args:
            client_id: ID do cliente

        Returns:
            Cliente ou None se não encontrado
        """
        logger.debug("Buscando cliente", client_id=client_id)
        return await self._cosmos.get_client(client_id)

    async def update_client(
        self,
        client_id: str,
        name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        status: Optional[ClientStatus] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[Client]:
        """
        Atualiza um cliente existente.

        Args:
            client_id: ID do cliente
            name: Novo nome (opcional)
            email: Novo e-mail (opcional)
            phone: Novo telefone (opcional)
            address: Novo endereço (opcional)
            city: Nova cidade (opcional)
            state: Nova UF (opcional)
            status: Novo status (opcional)
            metadata: Novos metadados (substitui existentes)

        Returns:
            Cliente atualizado ou None se não encontrado
        """
        # Busca cliente atual
        client = await self._cosmos.get_client(client_id)
        if not client:
            logger.warning("Cliente não encontrado para atualização", client_id=client_id)
            return None

        # Atualiza campos fornecidos
        if name is not None:
            client.name = name
        if email is not None:
            client.email = email
        if phone is not None:
            client.phone = phone
        if address is not None:
            client.address = address
        if city is not None:
            client.city = city
        if state is not None:
            client.state = state
        if status is not None:
            client.status = status
        if metadata is not None:
            client.metadata = metadata

        client.updated_at = datetime.utcnow()

        logger.info(
            "Atualizando cliente",
            client_id=client_id,
        )

        await self._cosmos.update_client(client)

        return client

    async def list_clients(
        self,
        status: Optional[ClientStatus] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[ClientSummary], int, bool]:
        """
        Lista clientes com filtros e paginação.

        Args:
            status: Filtrar por status
            search: Buscar por nome ou documento
            limit: Máximo de resultados
            offset: Pular primeiros N resultados

        Returns:
            Tuple de (lista de resumos, total, has_more)
        """
        logger.debug(
            "Listando clientes",
            status=status,
            search=search,
            limit=limit,
            offset=offset,
        )

        # Converte enum para string se fornecido
        status_str = status.value if status else None

        clients, total = await self._cosmos.list_clients(
            status=status_str,
            search=search,
            limit=limit,
            offset=offset,
        )

        # Converte para ClientSummary
        summaries = [
            ClientSummary(
                id=c.id,
                name=c.name,
                document=c.document,
                document_type=c.document_type,
                status=c.status,
                created_at=c.created_at,
            )
            for c in clients
        ]

        has_more = (offset + len(clients)) < total

        return summaries, total, has_more

    async def delete_client(
        self,
        client_id: str,
        soft_delete: bool = True,
    ) -> bool:
        """
        Remove ou desativa um cliente.

        Args:
            client_id: ID do cliente
            soft_delete: Se True, apenas muda status para INACTIVE

        Returns:
            True se operação bem sucedida
        """
        if soft_delete:
            # Soft delete: muda status para inativo
            client = await self._cosmos.get_client(client_id)
            if not client:
                return False

            client.status = ClientStatus.INACTIVE
            client.updated_at = datetime.utcnow()
            await self._cosmos.update_client(client)

            logger.info(
                "Cliente desativado (soft delete)",
                client_id=client_id,
            )
            return True
        else:
            # Hard delete: remove permanentemente
            deleted = await self._cosmos.delete_client(client_id)
            if deleted:
                logger.info(
                    "Cliente removido permanentemente",
                    client_id=client_id,
                )
            return deleted

    # ============================================
    # Contratos por Cliente
    # ============================================

    async def get_client_contracts(
        self,
        client_id: str,
        status: Optional[DocumentStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ClientContractsResponse:
        """
        Lista contratos de um cliente.

        Args:
            client_id: ID do cliente
            status: Filtrar por status de processamento
            limit: Máximo de resultados
            offset: Pular primeiros N resultados

        Returns:
            Resposta com lista de contratos
        """
        logger.debug(
            "Listando contratos do cliente",
            client_id=client_id,
            status=status,
        )

        # Busca documentos do tipo contrato
        documents = await self._cosmos.list_documents_by_client(
            client_id=client_id,
            document_type=DocumentType.CONTRACT.value,
            status=status,
            limit=limit + 1,  # +1 para verificar has_more
        )

        # Verifica se há mais
        has_more = len(documents) > limit
        if has_more:
            documents = documents[:limit]

        # Converte para ContractSummary
        contracts = [
            ContractSummary(
                id=doc.id,
                filename=doc.filename,
                status=doc.status.value,
                created_at=doc.created_at,
                processed_at=doc.processed_at,
                page_count=None,  # DocumentMetadata não tem esse campo atualmente
            )
            for doc in documents
        ]

        return ClientContractsResponse(
            client_id=client_id,
            contracts=contracts,
            total_count=len(contracts),  # Aproximado, poderia fazer count separado
            has_more=has_more,
        )

    # ============================================
    # Status de Processamento
    # ============================================

    async def get_processing_status(
        self,
        client_id: str,
        include_documents: bool = False,
    ) -> ProcessingStatusResponse:
        """
        Retorna status de processamento dos documentos de um cliente.

        Args:
            client_id: ID do cliente
            include_documents: Se True, inclui lista detalhada

        Returns:
            Status de processamento consolidado
        """
        logger.debug(
            "Obtendo status de processamento",
            client_id=client_id,
        )

        # Busca todos os documentos do cliente
        documents = await self._cosmos.list_documents_by_client(
            client_id=client_id,
            limit=1000,  # Limite alto para pegar todos
        )

        # Conta por status
        status_counts = {
            "uploaded": 0,
            "processing": 0,
            "indexed": 0,
            "failed": 0,
        }

        document_details = []

        for doc in documents:
            status_key = doc.status.value.lower()
            if status_key in status_counts:
                status_counts[status_key] += 1

            if include_documents:
                document_details.append(
                    DocumentProcessingStatus(
                        id=doc.id,
                        filename=doc.filename,
                        document_type=doc.document_type.value,
                        status=doc.status.value,
                        created_at=doc.created_at,
                        updated_at=doc.updated_at,
                        processed_at=doc.processed_at,
                        error_message=doc.error_message,
                    )
                )

        return ProcessingStatusResponse(
            client_id=client_id,
            total_documents=len(documents),
            documents_uploaded=status_counts["uploaded"],
            documents_processing=status_counts["processing"],
            documents_indexed=status_counts["indexed"],
            documents_failed=status_counts["failed"],
            documents=document_details if include_documents else None,
        )

    # ============================================
    # Estatísticas do Cliente
    # ============================================

    async def get_client_stats(
        self,
        client_id: str,
    ) -> Optional[ClientStatsResponse]:
        """
        Retorna estatísticas completas de um cliente.

        Args:
            client_id: ID do cliente

        Returns:
            Estatísticas ou None se cliente não existir
        """
        # Busca cliente
        client = await self._cosmos.get_client(client_id)
        if not client:
            return None

        logger.debug(
            "Obtendo estatísticas do cliente",
            client_id=client_id,
        )

        # Busca estatísticas do Cosmos
        stats = await self._cosmos.get_client_stats(client_id)

        # Busca resumo de custos
        cost_summary = await self._cosmos.get_cost_summary(client_id)

        # Conta documentos pendentes vs prontos
        docs_by_status = stats.get("documents_by_status", {})
        pending = docs_by_status.get("uploaded", 0) + docs_by_status.get("processing", 0)
        ready = docs_by_status.get("indexed", 0)

        return ClientStatsResponse(
            client_id=client_id,
            client_name=client.name,
            total_contracts=stats.get("contract_count", 0),
            total_cost_files=stats.get("cost_file_count", 0),
            documents_pending=pending,
            documents_ready=ready,
            total_conversations=stats.get("conversation_count", 0),
            active_conversations=stats.get("conversation_count", 0),  # Simplificado
            total_cost_records=cost_summary.get("total_records"),
            total_charged_amount=cost_summary.get("total_charged"),
            cost_period_start=cost_summary.get("date_start"),
            cost_period_end=cost_summary.get("date_end"),
        )

    async def get_client_detail(
        self,
        client_id: str,
    ) -> Optional[ClientDetailResponse]:
        """
        Retorna detalhes completos de um cliente com estatísticas.

        Args:
            client_id: ID do cliente

        Returns:
            Detalhes do cliente ou None se não existir
        """
        # Busca cliente
        client = await self._cosmos.get_client(client_id)
        if not client:
            return None

        # Busca estatísticas
        stats = await self._cosmos.get_client_stats(client_id)

        return ClientDetailResponse(
            id=client.id,
            name=client.name,
            document=client.document,
            document_type=client.document_type,
            email=client.email,
            phone=client.phone,
            address=client.address,
            city=client.city,
            state=client.state,
            status=client.status,
            created_at=client.created_at,
            updated_at=client.updated_at,
            metadata=client.metadata,
            contract_count=stats.get("contract_count", 0),
            document_count=stats.get("document_count", 0),
            conversation_count=stats.get("conversation_count", 0),
        )


# ============================================
# Singleton
# ============================================

_client_service: Optional[ClientService] = None


def get_client_service() -> ClientService:
    """
    Retorna instância singleton do ClientService.
    """
    global _client_service
    if _client_service is None:
        _client_service = ClientService()
    return _client_service
