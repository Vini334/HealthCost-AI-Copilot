"""
Serviço de gerenciamento de conversas.

Responsável por:
- Criar e gerenciar conversas
- Adicionar mensagens
- Recuperar histórico
- Gerar títulos automáticos
- Gerenciar contexto de conversas longas
- Integrar com sumarização
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from src.config.logging import get_logger
from src.models.conversations import (
    Conversation,
    ConversationMessage,
    ConversationStatus,
    ConversationSummary,
    MessageRole,
)
from src.storage.cosmos_db import get_cosmos_client, CosmosDBClient
from src.utils.token_counter import TokenCounter, get_token_counter

if TYPE_CHECKING:
    from src.services.conversation_summarizer import ConversationSummarizer

logger = get_logger(__name__)


class ConversationService:
    """
    Serviço para gerenciamento de conversas.

    Encapsula a lógica de negócios para criar, atualizar
    e recuperar conversas do Cosmos DB.

    Inclui gerenciamento de contexto com:
    - Memória de curto prazo (últimas N mensagens)
    - Resumo de conversas longas
    - Referência a mensagens anteriores
    """

    def __init__(
        self,
        cosmos_client: Optional[CosmosDBClient] = None,
        token_counter: Optional[TokenCounter] = None,
    ):
        """
        Inicializa o serviço.

        Args:
            cosmos_client: Cliente Cosmos DB (opcional, usa singleton se não fornecido)
            token_counter: Contador de tokens (opcional, usa singleton se não fornecido)
        """
        self._cosmos = cosmos_client or get_cosmos_client()
        self._token_counter = token_counter or get_token_counter()
        self._summarizer: Optional["ConversationSummarizer"] = None
        logger.info("ConversationService inicializado")

    async def create_conversation(
        self,
        client_id: str,
        contract_id: Optional[str] = None,
        title: Optional[str] = None,
        initial_message: Optional[str] = None,
    ) -> Conversation:
        """
        Cria uma nova conversa.

        Args:
            client_id: ID do cliente
            contract_id: ID do contrato (opcional)
            title: Título da conversa (opcional)
            initial_message: Mensagem inicial do usuário (opcional)

        Returns:
            Conversa criada
        """
        conversation = Conversation(
            client_id=client_id,
            contract_id=contract_id,
            title=title,
        )

        # Se tiver mensagem inicial, adiciona
        if initial_message:
            conversation.add_user_message(initial_message)

            # Se não tiver título, gera automaticamente
            if not title:
                conversation.title = conversation.generate_title()

        logger.info(
            "Criando nova conversa",
            conversation_id=str(conversation.id),
            client_id=client_id,
            contract_id=contract_id,
        )

        await self._cosmos.create_conversation(conversation)

        return conversation

    async def get_conversation(
        self,
        conversation_id: str,
        client_id: str,
    ) -> Optional[Conversation]:
        """
        Busca uma conversa por ID.

        Args:
            conversation_id: ID da conversa
            client_id: ID do cliente

        Returns:
            Conversa ou None se não encontrada
        """
        return await self._cosmos.get_conversation(conversation_id, client_id)

    async def get_or_create_conversation(
        self,
        client_id: str,
        conversation_id: Optional[str] = None,
        contract_id: Optional[str] = None,
    ) -> Conversation:
        """
        Busca uma conversa existente ou cria uma nova.

        Args:
            client_id: ID do cliente
            conversation_id: ID da conversa (opcional)
            contract_id: ID do contrato (opcional)

        Returns:
            Conversa existente ou nova
        """
        # Se tiver conversation_id, tenta buscar
        if conversation_id:
            conversation = await self.get_conversation(conversation_id, client_id)
            if conversation:
                logger.debug(
                    "Conversa existente encontrada",
                    conversation_id=conversation_id,
                )
                return conversation
            else:
                logger.warning(
                    "Conversa não encontrada, criando nova",
                    conversation_id=conversation_id,
                )

        # Cria nova conversa
        return await self.create_conversation(
            client_id=client_id,
            contract_id=contract_id,
        )

    async def add_user_message(
        self,
        conversation: Conversation,
        content: str,
    ) -> ConversationMessage:
        """
        Adiciona uma mensagem do usuário e salva.

        Args:
            conversation: Conversa
            content: Conteúdo da mensagem

        Returns:
            Mensagem criada
        """
        message = conversation.add_user_message(content)

        # Gera título se for a primeira mensagem
        if conversation.message_count == 1 and not conversation.title:
            conversation.title = conversation.generate_title()

        await self._cosmos.update_conversation(conversation)

        logger.debug(
            "Mensagem do usuário adicionada",
            conversation_id=str(conversation.id),
            message_id=str(message.id),
        )

        return message

    async def add_assistant_message(
        self,
        conversation: Conversation,
        content: str,
        execution_id: Optional[str] = None,
        intent: Optional[str] = None,
        agents_invoked: Optional[List[str]] = None,
        sources: Optional[List[Dict[str, Any]]] = None,
        tokens_used: Optional[int] = None,
        execution_time_ms: Optional[float] = None,
    ) -> ConversationMessage:
        """
        Adiciona uma mensagem do assistente e salva.

        Args:
            conversation: Conversa
            content: Conteúdo da resposta
            execution_id: ID da execução
            intent: Intent detectado
            agents_invoked: Agentes acionados
            sources: Fontes citadas
            tokens_used: Tokens consumidos
            execution_time_ms: Tempo de execução

        Returns:
            Mensagem criada
        """
        message = conversation.add_assistant_message(
            content=content,
            execution_id=execution_id,
            intent=intent,
            agents_invoked=agents_invoked,
            sources=sources,
            tokens_used=tokens_used,
            execution_time_ms=execution_time_ms,
        )

        await self._cosmos.update_conversation(conversation)

        logger.debug(
            "Mensagem do assistente adicionada",
            conversation_id=str(conversation.id),
            message_id=str(message.id),
            tokens_used=tokens_used,
        )

        return message

    async def list_conversations(
        self,
        client_id: str,
        contract_id: Optional[str] = None,
        status: Optional[ConversationStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[ConversationSummary], int, bool]:
        """
        Lista conversas de um cliente.

        Args:
            client_id: ID do cliente
            contract_id: Filtrar por contrato (opcional)
            status: Filtrar por status (opcional)
            limit: Máximo de resultados
            offset: Pular primeiros N resultados

        Returns:
            Tuple de (lista de resumos, total, has_more)
        """
        status_value = status.value if status else None

        conversations, total = await self._cosmos.list_conversations_by_client(
            client_id=client_id,
            contract_id=contract_id,
            status=status_value,
            limit=limit,
            offset=offset,
        )

        # Converte para resumos
        summaries = []
        for conv in conversations:
            # Pega preview da última mensagem
            last_message_preview = None
            if conv.messages:
                last_msg = conv.messages[-1]
                last_message_preview = last_msg.content[:100]
                if len(last_msg.content) > 100:
                    last_message_preview += "..."

            summaries.append(
                ConversationSummary(
                    id=conv.id,
                    client_id=conv.client_id,
                    contract_id=conv.contract_id,
                    title=conv.title,
                    status=conv.status,
                    message_count=conv.message_count,
                    created_at=conv.created_at,
                    updated_at=conv.updated_at,
                    last_message_at=conv.last_message_at,
                    last_message_preview=last_message_preview,
                )
            )

        has_more = (offset + len(summaries)) < total

        return summaries, total, has_more

    async def update_conversation_title(
        self,
        conversation_id: str,
        client_id: str,
        title: str,
    ) -> Optional[Conversation]:
        """
        Atualiza o título de uma conversa.

        Args:
            conversation_id: ID da conversa
            client_id: ID do cliente
            title: Novo título

        Returns:
            Conversa atualizada ou None se não encontrada
        """
        conversation = await self.get_conversation(conversation_id, client_id)
        if not conversation:
            return None

        conversation.title = title
        conversation.updated_at = datetime.utcnow()

        await self._cosmos.update_conversation(conversation)

        logger.info(
            "Título da conversa atualizado",
            conversation_id=conversation_id,
            title=title,
        )

        return conversation

    async def archive_conversation(
        self,
        conversation_id: str,
        client_id: str,
    ) -> Optional[Conversation]:
        """
        Arquiva uma conversa.

        Args:
            conversation_id: ID da conversa
            client_id: ID do cliente

        Returns:
            Conversa arquivada ou None se não encontrada
        """
        conversation = await self.get_conversation(conversation_id, client_id)
        if not conversation:
            return None

        conversation.status = ConversationStatus.ARCHIVED
        conversation.updated_at = datetime.utcnow()

        await self._cosmos.update_conversation(conversation)

        logger.info(
            "Conversa arquivada",
            conversation_id=conversation_id,
        )

        return conversation

    async def delete_conversation(
        self,
        conversation_id: str,
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
        return await self._cosmos.delete_conversation(conversation_id, client_id)

    async def delete_message(
        self,
        conversation_id: str,
        client_id: str,
        message_id: str,
    ) -> bool:
        """
        Remove uma mensagem específica de uma conversa.

        Args:
            conversation_id: ID da conversa
            client_id: ID do cliente
            message_id: ID da mensagem a remover

        Returns:
            True se removida, False se não encontrada
        """
        # Buscar conversa
        conversation = await self.get_conversation(conversation_id, client_id)
        if not conversation:
            return False

        # Encontrar e remover a mensagem
        original_count = len(conversation.messages)
        conversation.messages = [
            msg for msg in conversation.messages
            if str(msg.id) != message_id
        ]

        if len(conversation.messages) == original_count:
            # Mensagem não encontrada
            return False

        # Atualizar contagem de mensagens
        conversation.message_count = len(conversation.messages)
        conversation.updated_at = datetime.utcnow()

        # Atualizar título se não houver mais mensagens do usuário
        if conversation.message_count == 0:
            conversation.title = "Conversa vazia"

        # Persistir alterações
        await self._cosmos.update_conversation(conversation)

        logger.info(
            "Mensagem removida",
            conversation_id=conversation_id,
            message_id=message_id,
            remaining_messages=conversation.message_count,
        )

        return True

    def get_messages_for_context(
        self,
        conversation: Conversation,
        max_messages: int = 20,
    ) -> List[Dict[str, str]]:
        """
        Retorna mensagens formatadas para contexto do LLM.

        Args:
            conversation: Conversa
            max_messages: Número máximo de mensagens

        Returns:
            Lista de dicts com role e content
        """
        return conversation.get_messages_for_context(max_messages)

    # ============================================
    # Gerenciamento de Contexto de Conversa
    # ============================================

    def _get_summarizer(self) -> "ConversationSummarizer":
        """Retorna o sumarizador (lazy loading)."""
        if self._summarizer is None:
            from src.services.conversation_summarizer import get_conversation_summarizer
            self._summarizer = get_conversation_summarizer()
        return self._summarizer

    async def get_conversation_context(
        self,
        conversation: Conversation,
        max_tokens: int = 8000,
        max_messages: int = 20,
        include_summary: bool = True,
        auto_summarize: bool = True,
    ) -> Dict[str, Any]:
        """
        Retorna contexto otimizado da conversa para o LLM.

        Combina:
        - Resumo de mensagens antigas (se disponível)
        - Mensagens recentes (memória de curto prazo)
        - Controle de tokens

        Args:
            conversation: Conversa para extrair contexto
            max_tokens: Limite máximo de tokens para o contexto
            max_messages: Limite máximo de mensagens recentes
            include_summary: Se deve incluir resumo de mensagens antigas
            auto_summarize: Se deve gerar resumo automaticamente quando necessário

        Returns:
            Dict com:
            - summary: Resumo de mensagens antigas (se houver)
            - messages: Lista de mensagens recentes formatadas
            - key_entities: Entidades-chave extraídas
            - total_tokens: Total de tokens estimado
            - message_ids: IDs das mensagens incluídas
            - has_summary: Se inclui resumo
        """
        result: Dict[str, Any] = {
            "summary": None,
            "messages": [],
            "key_entities": {},
            "total_tokens": 0,
            "message_ids": [],
            "has_summary": False,
        }

        # Verificar se precisa sumarizar
        summarizer = self._get_summarizer()
        summaries = conversation.get_summaries()

        # Sumarizar automaticamente se necessário
        if auto_summarize and summarizer.needs_summarization(conversation, []):
            try:
                from src.services.conversation_summarizer import ConversationSummary as SummaryModel
                existing = [SummaryModel.from_dict(s) for s in summaries]
                new_summary = await summarizer.summarize_incrementally(
                    conversation=conversation,
                    existing_summaries=existing,
                )
                if new_summary:
                    conversation.add_summary(new_summary.to_dict())
                    await self._cosmos.update_conversation(conversation)
                    summaries = conversation.get_summaries()
                    logger.info(
                        "Resumo gerado automaticamente",
                        conversation_id=str(conversation.id),
                    )
            except Exception as e:
                logger.warning(f"Erro ao gerar resumo automático: {e}")

        # Calcular tokens disponíveis
        available_tokens = max_tokens

        # 1. Incluir resumo se disponível e solicitado
        if include_summary and summaries:
            latest_summary = summaries[-1]
            summary_text = latest_summary.get("summary_text", "")
            summary_tokens = self._token_counter.count_tokens(summary_text)

            # Usar no máximo 30% do budget para resumo
            max_summary_tokens = int(max_tokens * 0.3)
            if summary_tokens <= max_summary_tokens:
                result["summary"] = summary_text
                result["key_entities"] = latest_summary.get("key_entities", {})
                result["has_summary"] = True
                available_tokens -= summary_tokens
                result["total_tokens"] += summary_tokens

        # 2. Obter mensagens recentes (não resumidas)
        last_summarized = conversation.get_last_summary_index()
        recent_messages = conversation.messages[last_summarized:]

        # Formatar mensagens
        formatted_messages = [
            {"role": msg.role.value, "content": msg.content}
            for msg in recent_messages
        ]

        # 3. Truncar mensagens para caber no limite de tokens
        truncated_messages = self._token_counter.truncate_messages_to_fit(
            messages=formatted_messages,
            max_tokens=available_tokens,
            reserve_for_response=0,
            preserve_recent=min(5, len(formatted_messages)),
        )

        # Se truncou, ajustar message_ids
        if len(truncated_messages) < len(recent_messages):
            # Pegar os IDs das mensagens que foram incluídas
            offset = len(recent_messages) - len(truncated_messages)
            included_messages = recent_messages[offset:]
            result["message_ids"] = [str(msg.id) for msg in included_messages]
        else:
            result["message_ids"] = [str(msg.id) for msg in recent_messages]

        # Aplicar limite de mensagens se necessário
        if len(truncated_messages) > max_messages:
            truncated_messages = truncated_messages[-max_messages:]
            result["message_ids"] = result["message_ids"][-max_messages:]

        result["messages"] = truncated_messages
        result["total_tokens"] += self._token_counter.count_messages_tokens(truncated_messages)

        logger.debug(
            "Contexto de conversa preparado",
            conversation_id=str(conversation.id),
            has_summary=result["has_summary"],
            message_count=len(result["messages"]),
            total_tokens=result["total_tokens"],
        )

        return result

    async def get_referenced_messages(
        self,
        conversation: Conversation,
        message_ids: List[str],
        include_context: bool = True,
        context_window: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Recupera mensagens referenciadas com contexto.

        Args:
            conversation: Conversa
            message_ids: IDs das mensagens a recuperar
            include_context: Se deve incluir mensagens ao redor
            context_window: Número de mensagens antes/depois

        Returns:
            Lista de mensagens com contexto
        """
        results = []

        for msg_id_str in message_ids:
            try:
                msg_id = UUID(msg_id_str)
                msg = conversation.get_message_by_id(msg_id)

                if msg is None:
                    continue

                if include_context:
                    context_messages = conversation.get_messages_around(msg_id, context_window)
                    results.append({
                        "target_message": {
                            "id": str(msg.id),
                            "role": msg.role.value,
                            "content": msg.content,
                            "created_at": msg.created_at.isoformat(),
                        },
                        "context": [
                            {
                                "id": str(m.id),
                                "role": m.role.value,
                                "content": m.content,
                            }
                            for m in context_messages
                        ],
                    })
                else:
                    results.append({
                        "id": str(msg.id),
                        "role": msg.role.value,
                        "content": msg.content,
                        "created_at": msg.created_at.isoformat(),
                    })

            except (ValueError, Exception) as e:
                logger.warning(f"Erro ao recuperar mensagem {msg_id_str}: {e}")

        return results

    async def search_in_conversation(
        self,
        conversation: Conversation,
        search_text: str,
        max_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Busca mensagens que contêm um texto específico.

        Args:
            conversation: Conversa
            search_text: Texto a buscar
            max_results: Máximo de resultados

        Returns:
            Lista de mensagens encontradas com índices
        """
        found = conversation.find_messages_by_content(search_text, max_results)

        return [
            {
                "index": idx,
                "id": str(msg.id),
                "role": msg.role.value,
                "content": msg.content[:200] + ("..." if len(msg.content) > 200 else ""),
                "created_at": msg.created_at.isoformat(),
            }
            for idx, msg in found
        ]

    async def force_summarize(
        self,
        conversation: Conversation,
    ) -> Optional[Dict[str, Any]]:
        """
        Força a geração de um resumo da conversa.

        Args:
            conversation: Conversa a resumir

        Returns:
            Dict com o resumo gerado ou None se falhar
        """
        try:
            summarizer = self._get_summarizer()
            summary = await summarizer.summarize_conversation(
                conversation=conversation,
                extract_entities=True,
            )

            summary_dict = summary.to_dict()
            conversation.add_summary(summary_dict)
            await self._cosmos.update_conversation(conversation)

            logger.info(
                "Resumo forçado gerado",
                conversation_id=str(conversation.id),
            )

            return summary_dict

        except Exception as e:
            logger.error(f"Erro ao forçar resumo: {e}")
            return None


# Singleton
_conversation_service: Optional[ConversationService] = None


def get_conversation_service() -> ConversationService:
    """
    Retorna instância singleton do serviço de conversas.
    """
    global _conversation_service
    if _conversation_service is None:
        _conversation_service = ConversationService()
    return _conversation_service
