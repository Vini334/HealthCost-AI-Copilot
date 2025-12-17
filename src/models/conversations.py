"""
Modelos para gerenciamento de conversas.

Define tipos e schemas Pydantic para representar
conversas, mensagens e histórico de chat.

Inclui suporte para:
- Memória de curto prazo (últimas N mensagens)
- Resumos de conversas longas
- Referências a mensagens anteriores
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Papel do autor da mensagem."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ConversationStatus(str, Enum):
    """Status da conversa."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class ConversationMessage(BaseModel):
    """
    Uma mensagem individual em uma conversa.

    Armazena o conteúdo, metadados e informações de execução.
    """

    id: UUID = Field(default_factory=uuid4, description="ID único da mensagem")
    role: MessageRole = Field(..., description="Papel: user, assistant ou system")
    content: str = Field(..., description="Conteúdo da mensagem")

    # Metadados de execução (apenas para mensagens do assistant)
    execution_id: Optional[str] = Field(
        default=None,
        description="ID da execução do agente (se role=assistant)",
    )
    intent: Optional[str] = Field(
        default=None,
        description="Intent detectado (se role=assistant)",
    )
    agents_invoked: Optional[List[str]] = Field(
        default=None,
        description="Agentes acionados (se role=assistant)",
    )
    sources: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Fontes citadas (se role=assistant)",
    )
    tokens_used: Optional[int] = Field(
        default=None,
        description="Tokens consumidos (se role=assistant)",
    )
    execution_time_ms: Optional[float] = Field(
        default=None,
        description="Tempo de execução em ms (se role=assistant)",
    )

    # Referências a mensagens anteriores
    referenced_message_ids: Optional[List[UUID]] = Field(
        default=None,
        description="IDs de mensagens anteriores referenciadas",
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Momento de criação",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "role": "user",
                    "content": "Qual o prazo de carência para cirurgias?",
                },
                {
                    "role": "assistant",
                    "content": "O prazo de carência para cirurgias é de 180 dias...",
                    "intent": "contract_query",
                    "agents_invoked": ["retrieval", "contract_analyst"],
                },
            ]
        }
    }


class Conversation(BaseModel):
    """
    Uma conversa completa com histórico de mensagens.

    A conversa é isolada por client_id e pode estar associada
    a um contrato específico.
    """

    id: UUID = Field(default_factory=uuid4, description="ID único da conversa")
    client_id: str = Field(..., description="ID do cliente (partition key)")
    contract_id: Optional[str] = Field(
        default=None,
        description="ID do contrato associado (opcional)",
    )

    # Metadados
    title: Optional[str] = Field(
        default=None,
        description="Título da conversa (gerado automaticamente ou definido pelo usuário)",
    )
    status: ConversationStatus = Field(
        default=ConversationStatus.ACTIVE,
        description="Status da conversa",
    )

    # Mensagens
    messages: List[ConversationMessage] = Field(
        default_factory=list,
        description="Lista de mensagens da conversa",
    )

    # Contadores
    message_count: int = Field(
        default=0,
        description="Número total de mensagens",
    )
    total_tokens_used: int = Field(
        default=0,
        description="Total de tokens consumidos na conversa",
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Momento de criação",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Última atualização",
    )
    last_message_at: Optional[datetime] = Field(
        default=None,
        description="Momento da última mensagem",
    )

    # Metadados adicionais
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadados adicionais",
    )

    def add_user_message(self, content: str) -> ConversationMessage:
        """
        Adiciona uma mensagem do usuário.

        Args:
            content: Conteúdo da mensagem

        Returns:
            Mensagem criada
        """
        message = ConversationMessage(
            role=MessageRole.USER,
            content=content,
        )
        self.messages.append(message)
        self.message_count += 1
        self.updated_at = datetime.utcnow()
        self.last_message_at = message.created_at
        return message

    def add_assistant_message(
        self,
        content: str,
        execution_id: Optional[str] = None,
        intent: Optional[str] = None,
        agents_invoked: Optional[List[str]] = None,
        sources: Optional[List[Dict[str, Any]]] = None,
        tokens_used: Optional[int] = None,
        execution_time_ms: Optional[float] = None,
    ) -> ConversationMessage:
        """
        Adiciona uma mensagem do assistente.

        Args:
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
        message = ConversationMessage(
            role=MessageRole.ASSISTANT,
            content=content,
            execution_id=execution_id,
            intent=intent,
            agents_invoked=agents_invoked,
            sources=sources,
            tokens_used=tokens_used,
            execution_time_ms=execution_time_ms,
        )
        self.messages.append(message)
        self.message_count += 1
        self.updated_at = datetime.utcnow()
        self.last_message_at = message.created_at

        if tokens_used:
            self.total_tokens_used += tokens_used

        return message

    def get_messages_for_context(self, max_messages: int = 20) -> List[Dict[str, str]]:
        """
        Retorna mensagens formatadas para contexto do LLM.

        Args:
            max_messages: Número máximo de mensagens a retornar

        Returns:
            Lista de dicts com role e content
        """
        # Pega as últimas N mensagens
        recent_messages = self.messages[-max_messages:]

        return [
            {"role": msg.role.value, "content": msg.content}
            for msg in recent_messages
        ]

    def generate_title(self) -> str:
        """
        Gera um título baseado na primeira mensagem do usuário.

        Returns:
            Título gerado (máximo 50 caracteres)
        """
        for msg in self.messages:
            if msg.role == MessageRole.USER:
                # Pega os primeiros 50 caracteres da primeira pergunta
                title = msg.content[:50]
                if len(msg.content) > 50:
                    title += "..."
                return title

        return "Nova conversa"

    # ============================================
    # Métodos de Gerenciamento de Contexto
    # ============================================

    def get_summaries(self) -> List[Dict[str, Any]]:
        """
        Retorna os resumos armazenados na conversa.

        Returns:
            Lista de resumos armazenados no metadata
        """
        return self.metadata.get("summaries", [])

    def add_summary(self, summary: Dict[str, Any]) -> None:
        """
        Adiciona um resumo à conversa.

        Args:
            summary: Dicionário com dados do resumo
        """
        if "summaries" not in self.metadata:
            self.metadata["summaries"] = []
        self.metadata["summaries"].append(summary)
        self.updated_at = datetime.utcnow()

    def get_last_summary_index(self) -> int:
        """
        Retorna o índice da última mensagem resumida.

        Returns:
            Índice da última mensagem resumida ou 0
        """
        summaries = self.get_summaries()
        if not summaries:
            return 0

        last_idx = 0
        for summary in summaries:
            message_range = summary.get("message_range", [0, 0])
            if len(message_range) >= 2:
                last_idx = max(last_idx, message_range[1])

        return last_idx

    def get_unsummarized_messages(self) -> List[ConversationMessage]:
        """
        Retorna mensagens que ainda não foram resumidas.

        Returns:
            Lista de mensagens não resumidas
        """
        last_idx = self.get_last_summary_index()
        return self.messages[last_idx:]

    def get_message_by_id(self, message_id: UUID) -> Optional[ConversationMessage]:
        """
        Busca uma mensagem pelo ID.

        Args:
            message_id: ID da mensagem

        Returns:
            ConversationMessage ou None
        """
        for msg in self.messages:
            if msg.id == message_id:
                return msg
        return None

    def get_message_index(self, message_id: UUID) -> Optional[int]:
        """
        Retorna o índice de uma mensagem pelo ID.

        Args:
            message_id: ID da mensagem

        Returns:
            Índice da mensagem ou None
        """
        for idx, msg in enumerate(self.messages):
            if msg.id == message_id:
                return idx
        return None

    def get_messages_in_range(
        self,
        start_idx: int,
        end_idx: Optional[int] = None,
    ) -> List[ConversationMessage]:
        """
        Retorna mensagens em um intervalo de índices.

        Args:
            start_idx: Índice inicial
            end_idx: Índice final (opcional)

        Returns:
            Lista de mensagens no intervalo
        """
        if end_idx is None:
            return self.messages[start_idx:]
        return self.messages[start_idx:end_idx]

    def get_context_window(
        self,
        include_summary: bool = True,
        max_recent_messages: int = 10,
    ) -> Dict[str, Any]:
        """
        Retorna uma janela de contexto otimizada.

        Combina resumo de mensagens antigas com mensagens recentes.

        Args:
            include_summary: Se deve incluir resumo
            max_recent_messages: Máximo de mensagens recentes

        Returns:
            Dict com 'summary', 'recent_messages', 'message_ids'
        """
        result: Dict[str, Any] = {
            "summary": None,
            "recent_messages": [],
            "message_ids": [],
        }

        # Obter último resumo
        if include_summary:
            summaries = self.get_summaries()
            if summaries:
                # Pegar o resumo mais recente
                latest_summary = summaries[-1]
                result["summary"] = latest_summary.get("summary_text")

        # Obter mensagens recentes (não resumidas)
        last_summarized = self.get_last_summary_index()
        recent_messages = self.messages[last_summarized:]

        # Limitar se necessário
        if len(recent_messages) > max_recent_messages:
            recent_messages = recent_messages[-max_recent_messages:]

        result["recent_messages"] = [
            {"role": msg.role.value, "content": msg.content}
            for msg in recent_messages
        ]
        result["message_ids"] = [msg.id for msg in recent_messages]

        return result

    def find_messages_by_content(
        self,
        search_text: str,
        max_results: int = 5,
    ) -> List[Tuple[int, ConversationMessage]]:
        """
        Busca mensagens que contêm um texto.

        Args:
            search_text: Texto a buscar
            max_results: Máximo de resultados

        Returns:
            Lista de tuplas (índice, mensagem)
        """
        results = []
        search_lower = search_text.lower()

        for idx, msg in enumerate(self.messages):
            if search_lower in msg.content.lower():
                results.append((idx, msg))
                if len(results) >= max_results:
                    break

        return results

    def get_messages_around(
        self,
        message_id: UUID,
        window: int = 2,
    ) -> List[ConversationMessage]:
        """
        Retorna mensagens ao redor de uma mensagem específica.

        Args:
            message_id: ID da mensagem central
            window: Número de mensagens antes e depois

        Returns:
            Lista de mensagens ao redor
        """
        idx = self.get_message_index(message_id)
        if idx is None:
            return []

        start = max(0, idx - window)
        end = min(len(self.messages), idx + window + 1)

        return self.messages[start:end]


# ============================================
# Modelos de API
# ============================================


class ConversationSummary(BaseModel):
    """Resumo de uma conversa para listagem."""

    id: UUID = Field(..., description="ID da conversa")
    client_id: str = Field(..., description="ID do cliente")
    contract_id: Optional[str] = Field(default=None, description="ID do contrato")
    title: Optional[str] = Field(default=None, description="Título da conversa")
    status: ConversationStatus = Field(..., description="Status")
    message_count: int = Field(..., description="Número de mensagens")
    created_at: datetime = Field(..., description="Data de criação")
    updated_at: datetime = Field(..., description="Última atualização")
    last_message_at: Optional[datetime] = Field(
        default=None,
        description="Data da última mensagem",
    )
    last_message_preview: Optional[str] = Field(
        default=None,
        description="Preview da última mensagem (primeiros 100 caracteres)",
    )


class ConversationListResponse(BaseModel):
    """Resposta de listagem de conversas."""

    conversations: List[ConversationSummary] = Field(
        ...,
        description="Lista de conversas",
    )
    total_count: int = Field(..., description="Total de conversas")
    has_more: bool = Field(
        default=False,
        description="Se há mais conversas para paginar",
    )


class ConversationDetailResponse(BaseModel):
    """Resposta com detalhes completos de uma conversa."""

    id: UUID = Field(..., description="ID da conversa")
    client_id: str = Field(..., description="ID do cliente")
    contract_id: Optional[str] = Field(default=None, description="ID do contrato")
    title: Optional[str] = Field(default=None, description="Título")
    status: ConversationStatus = Field(..., description="Status")
    messages: List[ConversationMessage] = Field(..., description="Mensagens")
    message_count: int = Field(..., description="Número de mensagens")
    total_tokens_used: int = Field(..., description="Total de tokens usados")
    created_at: datetime = Field(..., description="Data de criação")
    updated_at: datetime = Field(..., description="Última atualização")


class CreateConversationRequest(BaseModel):
    """Request para criar uma nova conversa."""

    client_id: str = Field(..., description="ID do cliente")
    contract_id: Optional[str] = Field(default=None, description="ID do contrato")
    title: Optional[str] = Field(default=None, description="Título inicial")
    initial_message: Optional[str] = Field(
        default=None,
        description="Mensagem inicial do usuário (opcional)",
    )


class UpdateConversationRequest(BaseModel):
    """Request para atualizar uma conversa."""

    title: Optional[str] = Field(default=None, description="Novo título")
    status: Optional[ConversationStatus] = Field(default=None, description="Novo status")
