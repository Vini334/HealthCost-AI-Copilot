"""
Cliente para Azure Cosmos DB.

Responsável por:
- CRUD de metadados de documentos
- CRUD de registros de custos
- Gerenciamento de conversas e histórico
- Operações isoladas por client_id (partition key)
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Union
from uuid import UUID

from azure.cosmos import CosmosClient, PartitionKey
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from src.config.settings import get_settings
from src.config.logging import get_logger
from src.models.documents import DocumentMetadata, DocumentStatus

logger = get_logger(__name__)


class CosmosDBClient:
    """
    Cliente para operações no Azure Cosmos DB.

    Estrutura do banco:
    - Database: healthcost (configurável)
    - Containers:
      - documents: Metadados de documentos (partition key: client_id)
      - conversations: Histórico de chat (partition key: client_id)
      - clients: Informações de clientes (partition key: id)

    O partition key (chave de partição) é FUNDAMENTAL no Cosmos DB:
    - Determina como os dados são distribuídos fisicamente
    - Queries filtradas por partition key são MUITO mais rápidas
    - Escolhemos client_id para garantir que todos os dados de um cliente
      estejam na mesma partição = queries rápidas + isolamento natural
    """

    # Nome do container para metadados de documentos
    DOCUMENTS_CONTAINER = "documents"

    # Nome do container para registros de custos
    COSTS_CONTAINER = "cost_records"

    def __init__(self) -> None:
        """
        Inicializa o cliente Cosmos DB.

        Conexão via endpoint + key definidos nas variáveis de ambiente.
        """
        settings = get_settings()

        # CosmosClient é o ponto de entrada para o Cosmos DB
        self._client = CosmosClient(
            url=settings.cosmos.endpoint,
            credential=settings.cosmos.key,
        )

        # Nome do database
        self._database_name = settings.cosmos.database

        # Referência ao database
        # get_database_client não faz chamada de rede, só prepara o objeto
        self._database = self._client.get_database_client(self._database_name)

        logger.info(
            "CosmosDBClient inicializado",
            database=self._database_name,
        )

    def _get_documents_container(self):
        """
        Retorna referência ao container de documentos.

        O container é criado automaticamente se não existir.
        """
        # Tenta criar o container (idempotente)
        self._database.create_container_if_not_exists(
            id=self.DOCUMENTS_CONTAINER,
            partition_key=PartitionKey(path="/client_id"),
        )
        return self._database.get_container_client(self.DOCUMENTS_CONTAINER)

    async def create_document_metadata(
        self,
        metadata: DocumentMetadata,
    ) -> DocumentMetadata:
        """
        Cria registro de metadados de um documento.

        Args:
            metadata: Objeto DocumentMetadata com os dados

        Returns:
            Metadados criados (com id confirmado)

        Raises:
            Exception: Se falhar ao criar
        """
        container = self._get_documents_container()

        # Converte o Pydantic model para dict
        # O Cosmos DB espera um dict Python
        item = metadata.model_dump(mode="json")

        # O campo 'id' é obrigatório no Cosmos DB
        # Convertemos UUID para string
        item["id"] = str(metadata.id)

        logger.info(
            "Criando metadados de documento",
            document_id=item["id"],
            client_id=metadata.client_id,
            document_type=metadata.document_type,
        )

        # create_item insere um novo documento
        # Se já existir um com mesmo id + partition key, dá erro
        result = container.create_item(body=item)

        logger.info(
            "Metadados criados com sucesso",
            document_id=result["id"],
        )

        return metadata

    async def get_document_metadata(
        self,
        document_id: Union[str, UUID],
        client_id: str,
    ) -> Optional[DocumentMetadata]:
        """
        Busca metadados de um documento específico.

        Args:
            document_id: ID do documento
            client_id: ID do cliente (partition key)

        Returns:
            DocumentMetadata se encontrado, None caso contrário

        Nota: Precisamos do client_id pois é a partition key.
              Sem ela, a query seria mais lenta (cross-partition).
        """
        container = self._get_documents_container()
        doc_id = str(document_id)

        try:
            # read_item é a forma mais eficiente de buscar um documento
            # quando sabemos id + partition key
            item = container.read_item(
                item=doc_id,
                partition_key=client_id,
            )

            logger.debug("Documento encontrado", document_id=doc_id)

            # Converte dict de volta para Pydantic model
            return DocumentMetadata(**item)

        except CosmosResourceNotFoundError:
            logger.debug("Documento não encontrado", document_id=doc_id)
            return None

    async def update_document_status(
        self,
        document_id: Union[str, UUID],
        client_id: str,
        status: DocumentStatus,
        error_message: Optional[str] = None,
    ) -> Optional[DocumentMetadata]:
        """
        Atualiza o status de processamento de um documento.

        Args:
            document_id: ID do documento
            client_id: ID do cliente
            status: Novo status
            error_message: Mensagem de erro (se status=FAILED)

        Returns:
            Metadados atualizados ou None se não encontrado
        """
        container = self._get_documents_container()
        doc_id = str(document_id)

        try:
            # Primeiro busca o documento atual
            item = container.read_item(item=doc_id, partition_key=client_id)

            # Atualiza os campos
            item["status"] = status.value
            item["updated_at"] = datetime.utcnow().isoformat()

            if status == DocumentStatus.FAILED and error_message:
                item["error_message"] = error_message
            elif status == DocumentStatus.INDEXED:
                # Limpa erro anterior quando processamento tem sucesso
                item["error_message"] = None
                item["processed_at"] = datetime.utcnow().isoformat()

            # replace_item substitui o documento inteiro
            # Precisamos passar o documento completo, não apenas os campos alterados
            result = container.replace_item(item=doc_id, body=item)

            logger.info(
                "Status do documento atualizado",
                document_id=doc_id,
                new_status=status.value,
            )

            return DocumentMetadata(**result)

        except CosmosResourceNotFoundError:
            logger.warning(
                "Documento não encontrado para atualização",
                document_id=doc_id,
            )
            return None

    async def list_documents_by_client(
        self,
        client_id: str,
        document_type: Optional[str] = None,
        status: Optional[DocumentStatus] = None,
        limit: int = 100,
    ) -> list[DocumentMetadata]:
        """
        Lista documentos de um cliente.

        Args:
            client_id: ID do cliente
            document_type: Filtrar por tipo (opcional)
            status: Filtrar por status (opcional)
            limit: Máximo de resultados

        Returns:
            Lista de DocumentMetadata

        Exemplo de uso:
            docs = await cosmos.list_documents_by_client(
                client_id="cliente-123",
                document_type="contract",
                status=DocumentStatus.INDEXED
            )
        """
        container = self._get_documents_container()

        # Monta a query SQL
        # Cosmos DB usa SQL-like syntax para queries
        query = "SELECT * FROM c WHERE c.client_id = @client_id"
        parameters = [{"name": "@client_id", "value": client_id}]

        # Adiciona filtros opcionais
        if document_type:
            query += " AND c.document_type = @document_type"
            parameters.append({"name": "@document_type", "value": document_type})

        if status:
            query += " AND c.status = @status"
            parameters.append({"name": "@status", "value": status.value})

        # Ordena por data de criação (mais recente primeiro)
        query += " ORDER BY c.created_at DESC"

        logger.debug(
            "Executando query de documentos",
            query=query,
            parameters=parameters,
        )

        # query_items retorna um iterator paginado
        # partition_key acelera a query (evita scan em todas partições)
        items = container.query_items(
            query=query,
            parameters=parameters,
            partition_key=client_id,
            max_item_count=limit,
        )

        # Converte cada item para Pydantic model
        documents = [DocumentMetadata(**item) for item in items]

        logger.info(
            "Documentos listados",
            client_id=client_id,
            count=len(documents),
        )

        return documents

    async def delete_document_metadata(
        self,
        document_id: Union[str, UUID],
        client_id: str,
    ) -> bool:
        """
        Remove metadados de um documento.

        Args:
            document_id: ID do documento
            client_id: ID do cliente

        Returns:
            True se removido, False se não existia
        """
        container = self._get_documents_container()
        doc_id = str(document_id)

        try:
            container.delete_item(item=doc_id, partition_key=client_id)
            logger.info("Documento removido", document_id=doc_id)
            return True
        except CosmosResourceNotFoundError:
            logger.warning("Documento não encontrado para remoção", document_id=doc_id)
            return False

    # ============================================================
    # Operações de Registros de Custos
    # ============================================================

    def _get_costs_container(self):
        """
        Retorna referência ao container de registros de custos.

        O container é criado automaticamente se não existir.
        """
        self._database.create_container_if_not_exists(
            id=self.COSTS_CONTAINER,
            partition_key=PartitionKey(path="/client_id"),
        )
        return self._database.get_container_client(self.COSTS_CONTAINER)

    async def create_cost_record(self, record) -> dict:
        """
        Cria um registro de custo no Cosmos DB.

        Args:
            record: CostRecord com os dados

        Returns:
            Registro criado

        Raises:
            Exception: Se falhar ao criar
        """
        # Import local para evitar circular import
        from src.models.costs import CostRecord

        container = self._get_costs_container()

        # Converte o Pydantic model para dict
        item = record.model_dump(mode="json")

        # O campo 'id' é obrigatório no Cosmos DB
        item["id"] = str(record.id)

        # Converte Decimal para float (Cosmos não suporta Decimal)
        if "charged_amount" in item:
            item["charged_amount"] = float(item["charged_amount"])
        if "paid_amount" in item:
            item["paid_amount"] = float(item["paid_amount"])

        logger.debug(
            "Criando registro de custo",
            record_id=item["id"],
            client_id=record.client_id,
        )

        result = container.create_item(body=item)
        return result

    async def get_cost_records_by_document(
        self,
        document_id: Union[str, UUID],
        client_id: str,
        limit: int = 1000,
    ) -> list[dict]:
        """
        Busca registros de custos de um documento específico.

        Args:
            document_id: ID do documento de origem
            client_id: ID do cliente (partition key)
            limit: Máximo de registros

        Returns:
            Lista de registros de custos
        """
        container = self._get_costs_container()
        doc_id = str(document_id)

        query = """
            SELECT * FROM c
            WHERE c.client_id = @client_id
            AND c.document_id = @document_id
            ORDER BY c.service_date DESC
        """
        parameters = [
            {"name": "@client_id", "value": client_id},
            {"name": "@document_id", "value": doc_id},
        ]

        items = container.query_items(
            query=query,
            parameters=parameters,
            partition_key=client_id,
            max_item_count=limit,
        )

        records = list(items)
        logger.debug(
            "Registros de custos encontrados",
            document_id=doc_id,
            count=len(records),
        )

        return records

    async def get_cost_records_by_client(
        self,
        client_id: str,
        contract_id: Optional[str] = None,
        date_start: Optional[date] = None,
        date_end: Optional[date] = None,
        category: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[dict]:
        """
        Busca registros de custos de um cliente.

        Args:
            client_id: ID do cliente
            contract_id: Filtrar por contrato (opcional)
            date_start: Data inicial (opcional)
            date_end: Data final (opcional)
            category: Filtrar por categoria (opcional)
            limit: Máximo de registros
            offset: Pular primeiros N registros

        Returns:
            Lista de registros de custos
        """
        container = self._get_costs_container()

        query = "SELECT * FROM c WHERE c.client_id = @client_id"
        parameters = [{"name": "@client_id", "value": client_id}]

        if contract_id:
            query += " AND c.contract_id = @contract_id"
            parameters.append({"name": "@contract_id", "value": contract_id})

        if date_start:
            query += " AND c.service_date >= @date_start"
            parameters.append({"name": "@date_start", "value": date_start.isoformat()})

        if date_end:
            query += " AND c.service_date <= @date_end"
            parameters.append({"name": "@date_end", "value": date_end.isoformat()})

        if category:
            query += " AND c.category = @category"
            parameters.append({"name": "@category", "value": category})

        query += " ORDER BY c.service_date DESC"
        query += f" OFFSET {offset} LIMIT {limit}"

        logger.debug(
            "Query de registros de custos",
            query=query,
            parameters=parameters,
        )

        items = container.query_items(
            query=query,
            parameters=parameters,
            partition_key=client_id,
        )

        records = list(items)
        logger.info(
            "Registros de custos listados",
            client_id=client_id,
            count=len(records),
        )

        return records

    async def get_cost_summary(
        self,
        client_id: str,
        contract_id: Optional[str] = None,
    ) -> dict:
        """
        Retorna resumo agregado dos custos de um cliente.

        Args:
            client_id: ID do cliente
            contract_id: Filtrar por contrato (opcional)

        Returns:
            Dict com totais e agregações
        """
        container = self._get_costs_container()

        # Query de agregação
        query = """
            SELECT
                COUNT(1) as total_records,
                SUM(c.charged_amount) as total_charged,
                SUM(c.paid_amount) as total_paid,
                MIN(c.service_date) as date_start,
                MAX(c.service_date) as date_end
            FROM c
            WHERE c.client_id = @client_id
        """
        parameters = [{"name": "@client_id", "value": client_id}]

        if contract_id:
            query += " AND c.contract_id = @contract_id"
            parameters.append({"name": "@contract_id", "value": contract_id})

        items = container.query_items(
            query=query,
            parameters=parameters,
            partition_key=client_id,
        )

        result = list(items)
        if result:
            return result[0]

        return {
            "total_records": 0,
            "total_charged": 0,
            "total_paid": 0,
            "date_start": None,
            "date_end": None,
        }

    async def get_cost_by_category(
        self,
        client_id: str,
        contract_id: Optional[str] = None,
    ) -> list[dict]:
        """
        Retorna custos agregados por categoria.

        Args:
            client_id: ID do cliente
            contract_id: Filtrar por contrato (opcional)

        Returns:
            Lista de agregações por categoria
        """
        container = self._get_costs_container()

        query = """
            SELECT
                c.category,
                COUNT(1) as total_records,
                SUM(c.charged_amount) as total_charged,
                SUM(c.paid_amount) as total_paid
            FROM c
            WHERE c.client_id = @client_id
        """
        parameters = [{"name": "@client_id", "value": client_id}]

        if contract_id:
            query += " AND c.contract_id = @contract_id"
            parameters.append({"name": "@contract_id", "value": contract_id})

        query += " GROUP BY c.category"

        items = container.query_items(
            query=query,
            parameters=parameters,
            partition_key=client_id,
        )

        return list(items)

    async def delete_cost_records_by_document(
        self,
        document_id: Union[str, UUID],
        client_id: str,
    ) -> int:
        """
        Remove todos os registros de custos de um documento.

        Args:
            document_id: ID do documento
            client_id: ID do cliente

        Returns:
            Número de registros removidos
        """
        container = self._get_costs_container()
        doc_id = str(document_id)

        # Primeiro, busca todos os registros do documento
        query = """
            SELECT c.id FROM c
            WHERE c.client_id = @client_id
            AND c.document_id = @document_id
        """
        parameters = [
            {"name": "@client_id", "value": client_id},
            {"name": "@document_id", "value": doc_id},
        ]

        items = container.query_items(
            query=query,
            parameters=parameters,
            partition_key=client_id,
        )

        deleted_count = 0
        for item in items:
            try:
                container.delete_item(item=item["id"], partition_key=client_id)
                deleted_count += 1
            except Exception as e:
                logger.warning(
                    "Erro ao remover registro de custo",
                    record_id=item["id"],
                    error=str(e),
                )

        logger.info(
            "Registros de custos removidos",
            document_id=doc_id,
            deleted_count=deleted_count,
        )

        return deleted_count

    # ============================================================
    # Operações de Conversas
    # ============================================================

    # Nome do container para conversas
    CONVERSATIONS_CONTAINER = "conversations"

    def _get_conversations_container(self):
        """
        Retorna referência ao container de conversas.

        O container é criado automaticamente se não existir.
        """
        self._database.create_container_if_not_exists(
            id=self.CONVERSATIONS_CONTAINER,
            partition_key=PartitionKey(path="/client_id"),
        )
        return self._database.get_container_client(self.CONVERSATIONS_CONTAINER)

    async def create_conversation(self, conversation) -> dict:
        """
        Cria uma nova conversa.

        Args:
            conversation: Objeto Conversation

        Returns:
            Conversa criada (dict)

        Raises:
            Exception: Se falhar ao criar
        """
        container = self._get_conversations_container()

        # Converte o Pydantic model para dict
        item = conversation.model_dump(mode="json")

        # O campo 'id' é obrigatório no Cosmos DB
        item["id"] = str(conversation.id)

        logger.info(
            "Criando conversa",
            conversation_id=item["id"],
            client_id=conversation.client_id,
        )

        result = container.create_item(body=item)

        logger.info(
            "Conversa criada com sucesso",
            conversation_id=result["id"],
        )

        return result

    async def get_conversation(
        self,
        conversation_id: Union[str, UUID],
        client_id: str,
    ):
        """
        Busca uma conversa por ID.

        Args:
            conversation_id: ID da conversa
            client_id: ID do cliente (partition key)

        Returns:
            Conversation se encontrado, None caso contrário
        """
        # Import local para evitar circular import
        from src.models.conversations import Conversation

        container = self._get_conversations_container()
        conv_id = str(conversation_id)

        try:
            item = container.read_item(
                item=conv_id,
                partition_key=client_id,
            )

            logger.debug("Conversa encontrada", conversation_id=conv_id)
            return Conversation(**item)

        except CosmosResourceNotFoundError:
            logger.debug("Conversa não encontrada", conversation_id=conv_id)
            return None

    async def update_conversation(self, conversation) -> dict:
        """
        Atualiza uma conversa existente.

        Args:
            conversation: Objeto Conversation atualizado

        Returns:
            Conversa atualizada (dict)

        Raises:
            CosmosResourceNotFoundError: Se a conversa não existir
        """
        container = self._get_conversations_container()

        # Converte o Pydantic model para dict
        item = conversation.model_dump(mode="json")
        item["id"] = str(conversation.id)

        logger.debug(
            "Atualizando conversa",
            conversation_id=item["id"],
            message_count=conversation.message_count,
        )

        result = container.replace_item(
            item=item["id"],
            body=item,
        )

        logger.info(
            "Conversa atualizada",
            conversation_id=result["id"],
        )

        return result

    async def list_conversations_by_client(
        self,
        client_id: str,
        contract_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list, int]:
        """
        Lista conversas de um cliente.

        Args:
            client_id: ID do cliente
            contract_id: Filtrar por contrato (opcional)
            status: Filtrar por status (opcional)
            limit: Máximo de resultados
            offset: Pular primeiros N resultados

        Returns:
            Tuple de (lista de conversas, total)
        """
        # Import local para evitar circular import
        from src.models.conversations import Conversation

        container = self._get_conversations_container()

        # Query para contagem total
        count_query = "SELECT VALUE COUNT(1) FROM c WHERE c.client_id = @client_id"
        count_params = [{"name": "@client_id", "value": client_id}]

        # Query principal
        query = """
            SELECT * FROM c
            WHERE c.client_id = @client_id
        """
        parameters = [{"name": "@client_id", "value": client_id}]

        if contract_id:
            query += " AND c.contract_id = @contract_id"
            parameters.append({"name": "@contract_id", "value": contract_id})
            count_query += " AND c.contract_id = @contract_id"
            count_params.append({"name": "@contract_id", "value": contract_id})

        if status:
            query += " AND c.status = @status"
            parameters.append({"name": "@status", "value": status})
            count_query += " AND c.status = @status"
            count_params.append({"name": "@status", "value": status})

        query += " ORDER BY c.updated_at DESC"
        query += f" OFFSET {offset} LIMIT {limit}"

        logger.debug(
            "Query de conversas",
            query=query,
            parameters=parameters,
        )

        # Executa contagem
        count_result = list(container.query_items(
            query=count_query,
            parameters=count_params,
            partition_key=client_id,
        ))
        total = count_result[0] if count_result else 0

        # Executa query principal
        items = container.query_items(
            query=query,
            parameters=parameters,
            partition_key=client_id,
        )

        conversations = [Conversation(**item) for item in items]

        logger.info(
            "Conversas listadas",
            client_id=client_id,
            count=len(conversations),
            total=total,
        )

        return conversations, total

    async def delete_conversation(
        self,
        conversation_id: Union[str, UUID],
        client_id: str,
    ) -> bool:
        """
        Remove uma conversa.

        Args:
            conversation_id: ID da conversa
            client_id: ID do cliente

        Returns:
            True se removida, False se não existia
        """
        container = self._get_conversations_container()
        conv_id = str(conversation_id)

        try:
            container.delete_item(item=conv_id, partition_key=client_id)
            logger.info("Conversa removida", conversation_id=conv_id)
            return True
        except CosmosResourceNotFoundError:
            logger.warning(
                "Conversa não encontrada para remoção",
                conversation_id=conv_id,
            )
            return False

    async def add_message_to_conversation(
        self,
        conversation_id: Union[str, UUID],
        client_id: str,
        message,
    ):
        """
        Adiciona uma mensagem a uma conversa existente.

        Args:
            conversation_id: ID da conversa
            client_id: ID do cliente
            message: ConversationMessage a adicionar

        Returns:
            Conversa atualizada ou None se não encontrada
        """
        # Busca a conversa
        conversation = await self.get_conversation(conversation_id, client_id)
        if not conversation:
            return None

        # Adiciona a mensagem
        conversation.messages.append(message)
        conversation.message_count += 1
        conversation.last_message_at = message.created_at

        if message.tokens_used:
            conversation.total_tokens_used += message.tokens_used

        # Atualiza updated_at
        from datetime import datetime
        conversation.updated_at = datetime.utcnow()

        # Salva
        await self.update_conversation(conversation)

        return conversation

    # ============================================================
    # Operações de Clientes
    # ============================================================

    # Nome do container para clientes
    CLIENTS_CONTAINER = "clients"

    def _get_clients_container(self):
        """
        Retorna referência ao container de clientes.

        O container é criado automaticamente se não existir.
        Partition key é /client_id (igual ao id do cliente).
        """
        self._database.create_container_if_not_exists(
            id=self.CLIENTS_CONTAINER,
            partition_key=PartitionKey(path="/client_id"),
        )
        return self._database.get_container_client(self.CLIENTS_CONTAINER)

    async def create_client(self, client) -> dict:
        """
        Cria um novo cliente.

        Args:
            client: Objeto Client

        Returns:
            Cliente criado (dict)

        Raises:
            Exception: Se falhar ao criar
        """
        container = self._get_clients_container()

        # Converte o Pydantic model para dict
        item = client.model_dump(mode="json")

        # O campo 'id' é obrigatório no Cosmos DB
        item["id"] = str(client.id)

        # O campo 'client_id' é a partition key do container
        # Deve ser igual ao id para clientes
        item["client_id"] = str(client.id)

        logger.info(
            "Criando cliente",
            client_id=item["id"],
            client_name=client.name,
        )

        result = container.create_item(body=item)

        logger.info(
            "Cliente criado com sucesso",
            client_id=result["id"],
        )

        return result

    async def get_client(self, client_id: Union[str, UUID]):
        """
        Busca um cliente por ID.

        Args:
            client_id: ID do cliente

        Returns:
            Client se encontrado, None caso contrário
        """
        # Import local para evitar circular import
        from src.models.clients import Client

        container = self._get_clients_container()
        c_id = str(client_id)

        try:
            # Usa query cross-partition para compatibilidade com containers
            # que podem ter sido criados com partition key diferente
            query = "SELECT * FROM c WHERE c.id = @client_id"
            parameters = [{"name": "@client_id", "value": c_id}]

            items = list(container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True,
            ))

            if items:
                logger.debug("Cliente encontrado", client_id=c_id)
                return Client(**items[0])

            logger.debug("Cliente não encontrado", client_id=c_id)
            return None

        except Exception as e:
            logger.warning(
                "Erro ao buscar cliente",
                client_id=c_id,
                error=str(e),
            )
            return None

    async def update_client(self, client) -> dict:
        """
        Atualiza um cliente existente.

        Args:
            client: Objeto Client atualizado

        Returns:
            Cliente atualizado (dict)

        Raises:
            CosmosResourceNotFoundError: Se o cliente não existir
        """
        container = self._get_clients_container()

        # Converte o Pydantic model para dict
        item = client.model_dump(mode="json")
        item["id"] = str(client.id)

        # Atualiza updated_at
        item["updated_at"] = datetime.utcnow().isoformat()

        logger.debug(
            "Atualizando cliente",
            client_id=item["id"],
            client_name=client.name,
        )

        result = container.replace_item(
            item=item["id"],
            body=item,
        )

        logger.info(
            "Cliente atualizado",
            client_id=result["id"],
        )

        return result

    async def list_clients(
        self,
        status: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list, int]:
        """
        Lista clientes com filtros e paginação.

        Args:
            status: Filtrar por status (active, inactive, suspended)
            search: Busca por nome ou documento
            limit: Máximo de resultados
            offset: Pular primeiros N resultados

        Returns:
            Tuple de (lista de clientes, total)
        """
        # Import local para evitar circular import
        from src.models.clients import Client

        container = self._get_clients_container()

        # Query base
        query = "SELECT * FROM c WHERE 1=1"
        parameters = []

        # Filtro por status
        if status:
            query += " AND c.status = @status"
            parameters.append({"name": "@status", "value": status})

        # Busca por nome ou documento
        if search:
            query += " AND (CONTAINS(LOWER(c.name), @search) OR CONTAINS(c.document, @search))"
            parameters.append({"name": "@search", "value": search.lower()})

        # Query de contagem
        count_query = query.replace("SELECT *", "SELECT VALUE COUNT(1)")

        # Ordenação e paginação
        query += " ORDER BY c.created_at DESC"
        query += f" OFFSET {offset} LIMIT {limit}"

        logger.debug(
            "Query de clientes",
            query=query,
            parameters=parameters,
        )

        # Executa contagem (cross-partition para clientes)
        count_result = list(container.query_items(
            query=count_query,
            parameters=parameters,
            enable_cross_partition_query=True,
        ))
        total = count_result[0] if count_result else 0

        # Executa query principal
        items = container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True,
        )

        clients = [Client(**item) for item in items]

        logger.info(
            "Clientes listados",
            count=len(clients),
            total=total,
        )

        return clients, total

    async def delete_client(self, client_id: Union[str, UUID]) -> bool:
        """
        Remove um cliente.

        Args:
            client_id: ID do cliente

        Returns:
            True se removido, False se não existia

        Nota: Esta operação não remove documentos e conversas associadas.
              Para remoção completa, use ClientService.delete_client_with_data()
        """
        container = self._get_clients_container()
        c_id = str(client_id)

        try:
            # Partition key é /client_id (que tem o mesmo valor do id)
            container.delete_item(item=c_id, partition_key=c_id)
            logger.info("Cliente removido", client_id=c_id)
            return True
        except CosmosResourceNotFoundError:
            logger.warning(
                "Cliente não encontrado para remoção",
                client_id=c_id,
            )
            return False

    async def get_client_stats(self, client_id: str) -> dict:
        """
        Retorna estatísticas de um cliente.

        Args:
            client_id: ID do cliente

        Returns:
            Dict com contagens de documentos, conversas, custos
        """
        stats = {
            "contract_count": 0,
            "cost_file_count": 0,
            "document_count": 0,
            "conversation_count": 0,
            "documents_by_status": {},
        }

        # Conta documentos por tipo e status
        docs_container = self._get_documents_container()
        doc_query = """
            SELECT c.document_type, c.status, COUNT(1) as count
            FROM c
            WHERE c.client_id = @client_id
            GROUP BY c.document_type, c.status
        """
        doc_params = [{"name": "@client_id", "value": client_id}]

        doc_items = docs_container.query_items(
            query=doc_query,
            parameters=doc_params,
            partition_key=client_id,
        )

        for item in doc_items:
            doc_type = item.get("document_type", "unknown")
            doc_status = item.get("status", "unknown")
            count = item.get("count", 0)

            stats["document_count"] += count

            if doc_type == "contract":
                stats["contract_count"] += count
            elif doc_type == "cost_data":
                stats["cost_file_count"] += count

            if doc_status not in stats["documents_by_status"]:
                stats["documents_by_status"][doc_status] = 0
            stats["documents_by_status"][doc_status] += count

        # Conta conversas
        conv_container = self._get_conversations_container()
        conv_query = "SELECT VALUE COUNT(1) FROM c WHERE c.client_id = @client_id"
        conv_params = [{"name": "@client_id", "value": client_id}]

        conv_result = list(conv_container.query_items(
            query=conv_query,
            parameters=conv_params,
            partition_key=client_id,
        ))
        stats["conversation_count"] = conv_result[0] if conv_result else 0

        logger.debug(
            "Estatísticas do cliente",
            client_id=client_id,
            stats=stats,
        )

        return stats


# Singleton
_cosmos_client: Optional[CosmosDBClient] = None


def get_cosmos_client() -> CosmosDBClient:
    """
    Retorna instância singleton do cliente Cosmos DB.
    """
    global _cosmos_client
    if _cosmos_client is None:
        _cosmos_client = CosmosDBClient()
    return _cosmos_client
